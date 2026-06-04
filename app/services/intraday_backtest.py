"""
Intraday T-Trade Backtest — 用历史 K 线回放日内做T信号，统计胜率与收益.

Reuses intraday_engine.py:
  - resolve_intraday_data
  - compute_intraday_indicators
  - evaluate_intraday_factors
  - IntradayDecisionEngine
  - replay_intraday_signals

For each requested trading day, we:
  1. Fetch 1m/5m kline history for that day (EastMoney `push2his` with beg=YYYYMMDD)
  2. Walk forward bar-by-bar, calling the decision engine
  3. For each T_BUY/T_SELL signal, look forward `holding_period` bars to compute
     max gain / max drawdown / exit price / win-loss result
  4. Aggregate into summary stats + a sample list (capped) for the UI
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple

from app.services.intraday_engine import (
    IntradayBar,
    IntradayResolvedData,
    compute_intraday_indicators,
    evaluate_intraday_factors,
    IntradayDecisionEngine,
)
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

_backtest_executor = ThreadPoolExecutor(max_workers=8)


# =============================================================================
# Section 1: Per-signal outcome model
# =============================================================================

@dataclass
class SignalOutcome:
    date: str
    time: str
    action: str
    signal_type: str
    confidence: float
    entry_price: float
    exit_price_N: Optional[float]  # close at bar + holding_period, or None
    max_gain: float               # 买入：max close - entry; 卖出：entry - min close
    max_drawdown: float           # 买入：min close - entry; 卖出：entry - max close
    result: str                   # "win" / "loss" / "breakeven"
    return_pct: float             # 持有期内的实际涨跌 (entry -> exit)
    reason: str
    daily_trend: str
    daily_strength: float


def _classify_result(action: str, return_pct: float) -> str:
    """Classify a signal's outcome as win/loss/breakeven.

    For T_BUY: positive return_pct = win.
    For T_SELL: negative return_pct = win (price dropped as expected).
    Threshold: |return_pct| < 0.05% considered breakeven.
    """
    if action == "T_BUY":
        effective = return_pct
    else:  # T_SELL
        effective = -return_pct
    if abs(effective) < 0.05:
        return "breakeven"
    return "win" if effective > 0 else "loss"


# =============================================================================
# Section 2: Single-day replay
# =============================================================================

def _resolve_daily_trend(
    symbol: str,
    market: str,
    target_date: date,
    intraday_bars: List[IntradayBar],
) -> Tuple[str, float, str]:
    """Best-effort daily trend classification using last bar's close vs previous close.

    For backtest purposes we keep it simple:
      - Compute change_pct = (close - prev_close) / prev_close * 100
      - Map to trend via thresholds: >+0.5 UP, <-0.5 DOWN, else NEUTRAL
    Strength is the absolute change_pct clamped to 0-100.
    Action: HOD/SOD for monotonic moves, else HOLD.
    """
    if not intraday_bars:
        return "NEUTRAL", 50.0, "HOLD"

    # Approximate prev_close from first 5-min bar's open (closest to yesterday's close)
    first_open = intraday_bars[0].open
    last_close = intraday_bars[-1].close
    if first_open <= 0:
        return "NEUTRAL", 50.0, "HOLD"

    change_pct = (last_close - first_open) / first_open * 100
    if change_pct > 0.5:
        trend = "UP"
    elif change_pct < -0.5:
        trend = "DOWN"
    else:
        trend = "NEUTRAL"

    strength = min(100.0, abs(change_pct) * 20 + 30)
    action = "HOLD"
    return trend, strength, action


def _replay_day(
    symbol: str,
    market: str,
    target_date: date,
    klt: int,
    holding_period: int,
    opening_range_bars: int,
) -> Tuple[List[SignalOutcome], Dict[str, int]]:
    """Replay a single trading day, returning all signal outcomes + counts."""
    # Fetch raw klines for the day
    beg_str = target_date.strftime("%Y%m%d")
    try:
        raw = StockService.get_intraday_klines(
            symbol, market, klt=klt, limit=240, beg=beg_str,
        )
    except Exception as e:
        logger.warning("backtest fetch failed for %s %s: %s", symbol, beg_str, e)
        return [], {}

    if not raw:
        return [], {}

    # Filter to bars on target_date only (EastMoney may return adjacent days)
    bars: List[IntradayBar] = []
    for d in raw:
        ts = d.get("timestamp")
        if ts is None:
            continue
        bar_date = ts.date() if isinstance(ts, datetime) else datetime.strptime(ts, "%Y-%m-%d %H:%M").date()
        if bar_date != target_date:
            continue
        bars.append(IntradayBar(
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d.get("volume", 0)),
            timestamp=ts,
        ))

    if len(bars) < 6:
        return [], {}

    # Use first bar's open as prev_close approximation
    prev_close = bars[0].open
    daily_trend, daily_strength, daily_action = _resolve_daily_trend(
        symbol, market, target_date, bars,
    )

    outcomes: List[SignalOutcome] = []
    counts: Dict[str, int] = {"buy_signals": 0, "sell_signals": 0, "hold_bars": 0}
    last_action = "HOLD"
    last_action_bar = -999  # bar index of last recorded signal
    # Dedup: track (bar_idx, action) pairs already recorded so the inner
    # has_pos loop can't double-record the same signal at the same bar.
    recorded_keys: set = set()
    # Cooldown: a signal in the OPPOSITE direction must be at least COOLDOWN_BARS
    # away from the previous one, unless confidence > COOLDOWN_OVERRIDE_CONF.
    # This kills the BUY↔SELL alternation spam (e.g. 2026-05-13 had 61 signals).
    COOLDOWN_BARS = 5
    COOLDOWN_OVERRIDE_CONF = 0.80

    # Walk forward from bar 3 (need 3+ bars for indicators) to len-1
    # We look at each bar as the "current" bar
    for i in range(3, len(bars) + 1):
        slice_bars = bars[:i]
        closes = [b.close for b in slice_bars]
        volumes = [b.volume for b in slice_bars]
        cp = closes[-1]
        high_of_day = max(b.high for b in slice_bars)
        low_of_day = min(b.low for b in slice_bars)
        today_open = slice_bars[0].open

        resolved = IntradayResolvedData(
            bars=slice_bars,
            bars_today=slice_bars,
            current_price=cp,
            prev_close=prev_close,
            today_open=today_open,
            bar_count=len(slice_bars),
            is_market_open=True,
            closes=closes,
            volumes=volumes,
            high_of_day=high_of_day,
            low_of_day=low_of_day,
        )

        ind = compute_intraday_indicators(resolved, opening_range_bars=opening_range_bars)
        factors = evaluate_intraday_factors(ind, resolved)

        # Test BOTH "has_position=True" (for SELL) and "has_position=False" (for BUY)
        # to capture all signals the engine could produce for this user
        for has_pos in (False, True):
            signal = IntradayDecisionEngine.decide(
                daily_trend, daily_strength, daily_action,
                factors, ind, resolved, has_pos,
            )
            if signal.action not in ("T_BUY", "T_SELL"):
                continue
            # Dedup: never record the same (bar, action) twice across the two
            # has_pos iterations. The engine often returns the same T_BUY/T_SELL
            # regardless of has_pos, so the inner loop would otherwise double up.
            key = (i, signal.action)
            if key in recorded_keys:
                continue
            recorded_keys.add(key)
            # Cooldown: opposite-direction signals must be >= COOLDOWN_BARS away
            # from the previous recorded signal, unless confidence is very high.
            if last_action != "HOLD" and signal.action != last_action:
                bars_since = i - last_action_bar
                if bars_since < COOLDOWN_BARS and signal.confidence < COOLDOWN_OVERRIDE_CONF:
                    continue
            # Compute forward outcomes
            entry_price = bars[i - 1].close
            forward_bars = bars[i - 1: i - 1 + holding_period + 1]  # current + N
            if len(forward_bars) < 2:
                continue

            exit_price = forward_bars[-1].close
            if signal.action == "T_BUY":
                max_close = max(b.close for b in forward_bars)
                min_close = min(b.close for b in forward_bars)
                max_gain = max_close - entry_price
                max_drawdown = min_close - entry_price
            else:  # T_SELL
                max_close = max(b.close for b in forward_bars)
                min_close = min(b.close for b in forward_bars)
                max_gain = entry_price - min_close  # for sell, gain = drop
                max_drawdown = entry_price - max_close  # for sell, drawdown = rally

            return_pct = (exit_price - entry_price) / entry_price * 100 if entry_price else 0.0
            result = _classify_result(signal.action, return_pct)

            bar_ts = bars[i - 1].timestamp
            signal_type_cn = {
                "BREAKOUT": "突破",
                "VWAP_REVERSAL": "VWAP回归",
                "RSI_EXTREME": "RSI极端",
                "MICRO_TREND": "分时趋势",
                "VOLUME_SURGE": "放量",
            }.get(signal.signal_type, signal.signal_type)

            outcomes.append(SignalOutcome(
                date=target_date.strftime("%Y-%m-%d"),
                time=bar_ts.strftime("%H:%M"),
                action=signal.action,
                signal_type=signal_type_cn,
                confidence=round(signal.confidence, 2),
                entry_price=round(entry_price, 4 if entry_price < 1 else 3),
                exit_price_N=round(exit_price, 4 if exit_price < 1 else 3),
                max_gain=round(max_gain, 4 if abs(max_gain) < 1 else 3),
                max_drawdown=round(max_drawdown, 4 if abs(max_drawdown) < 1 else 3),
                result=result,
                return_pct=round(return_pct, 2),
                reason=signal.reason,
                daily_trend=daily_trend,
                daily_strength=round(daily_strength, 1),
            ))
            if signal.action == "T_BUY":
                counts["buy_signals"] += 1
            else:
                counts["sell_signals"] += 1
            last_action = signal.action
            last_action_bar = i

    return outcomes, counts


# =============================================================================
# Section 3: Main backtest API
# =============================================================================

def _trading_day_candidates(end_date: date, n: int) -> List[date]:
    """Generate N candidate trading days, walking back from end_date.

    Skips weekends. Holiday detection happens implicitly via the API returning
    no data for those days.
    """
    candidates: List[date] = []
    d = end_date
    while len(candidates) < n * 2 and (end_date - d).days < (n * 3 + 5):
        if d.weekday() < 5:  # Mon-Fri
            candidates.append(d)
        d -= timedelta(days=1)
        if len(candidates) >= n * 2 + 10:
            break
    return candidates[: n * 2 + 10]  # over-fetch to filter empty days


def run_backtest(
    symbol: str,
    market: str = "CN",
    days: int = 20,
    klt: int = 5,
    holding_period: int = 10,
) -> dict:
    """Run a T-trade signal backtest over the last N trading days.

    Args:
        symbol: stock/ETF symbol
        market: market code (CN only for now)
        days: number of trading days to backtest (max 60)
        klt: kline granularity — 1=1min, 5=5min
        holding_period: how many bars forward to evaluate each signal

    Returns:
        {
          "summary": {...aggregate stats...},
          "samples": [SignalOutcome dicts, capped at 200],
          "days_analyzed": int,
          "params": {symbol, days, klt, holding_period}
        }
    """
    symbol = symbol.upper().strip()
    if klt not in (1, 5):
        klt = 5
    if days < 1 or days > 60:
        days = max(1, min(60, days))
    if holding_period < 1 or holding_period > 60:
        holding_period = max(1, min(60, holding_period))

    opening_range_bars = 6 if klt == 5 else 30  # 30 min total for both

    # Generate candidate dates
    today = date.today()
    candidates = _trading_day_candidates(today, days)

    # Fetch all days in parallel
    all_outcomes: List[SignalOutcome] = []
    total_counts: Dict[str, int] = {"buy_signals": 0, "sell_signals": 0, "hold_bars": 0}
    days_with_data = 0

    futures = {
        _backtest_executor.submit(
            _replay_day, symbol, market, d, klt, holding_period, opening_range_bars,
        ): d
        for d in candidates
    }
    for fut in as_completed(futures):
        try:
            outcomes, counts = fut.result(timeout=30)
        except Exception as e:
            logger.warning("backtest day replay failed: %s", e)
            continue
        if outcomes:
            days_with_data += 1
            all_outcomes.extend(outcomes)
            for k, v in counts.items():
                total_counts[k] = total_counts.get(k, 0) + v
        if days_with_data >= days:
            # Don't wait for remaining futures — they'll finish in background
            # but we've gathered enough days.
            pass

    # Sort by date+time
    all_outcomes.sort(key=lambda o: (o.date, o.time))

    # Aggregate stats — split by T_BUY and T_SELL
    buy_outcomes = [o for o in all_outcomes if o.action == "T_BUY"]
    sell_outcomes = [o for o in all_outcomes if o.action == "T_SELL"]

    def _agg(outcomes: List[SignalOutcome]) -> dict:
        if not outcomes:
            return {
                "count": 0,
                "winrate": None,
                "avg_return": None,
                "avg_max_gain": None,
                "avg_max_drawdown": None,
            }
        wins = sum(1 for o in outcomes if o.result == "win")
        total = len(outcomes)
        return {
            "count": total,
            "winrate": round(wins / total * 100, 1) if total else None,
            "avg_return": round(sum(o.return_pct for o in outcomes) / total, 3),
            "avg_max_gain": round(sum(o.max_gain for o in outcomes) / total, 4),
            "avg_max_drawdown": round(sum(o.max_drawdown for o in outcomes) / total, 4),
        }

    summary = {
        "total_signals": len(all_outcomes),
        "buy_signals": len(buy_outcomes),
        "sell_signals": len(sell_outcomes),
        "buy_stats": _agg(buy_outcomes),
        "sell_stats": _agg(sell_outcomes),
    }

    # Group by signal type for breakdown
    by_type: Dict[str, Dict[str, Any]] = {}
    for o in all_outcomes:
        st = o.signal_type
        if st not in by_type:
            by_type[st] = {"count": 0, "wins": 0, "avg_return": 0.0}
        by_type[st]["count"] += 1
        if o.result == "win":
            by_type[st]["wins"] += 1
        by_type[st]["avg_return"] += o.return_pct
    for st, v in by_type.items():
        if v["count"] > 0:
            v["winrate"] = round(v["wins"] / v["count"] * 100, 1)
            v["avg_return"] = round(v["avg_return"] / v["count"], 3)
    summary["by_signal_type"] = by_type

    # Cap samples to 200 for response size
    samples_capped = [asdict(o) for o in all_outcomes[:200]]

    return {
        "symbol": symbol,
        "market": market,
        "days_analyzed": days_with_data,
        "days_requested": days,
        "klt": klt,
        "holding_period": holding_period,
        "summary": summary,
        "samples": samples_capped,
        "timestamp": datetime.now().isoformat(),
    }
