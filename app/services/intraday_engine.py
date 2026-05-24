"""
Intraday T-Trade Signal Engine — 日内分时做T信号引擎.

Architecture (mirrors signal_engine.py):
  Stage 1: Data resolution (parse minute klines + market hours detection)
  Stage 2: Technical indicators (pure functions on minute data)
  Stage 3: Factor evaluators (VWAP, opening range, micro-trend, volume, RSI)
  Stage 4: Rule-based decision tree (signal priority + daily trend filter)
  Stage 5: Output

Philosophy: 日线趋势给方向，分时信号给时机。多次做T，每次独立决策。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime, date, time
import math


# =============================================================================
# Section 1: Data Models
# =============================================================================

@dataclass
class IntradayBar:
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime


@dataclass
class IntradayResolvedData:
    bars: List[IntradayBar]
    bars_today: List[IntradayBar]
    current_price: float
    prev_close: float
    today_open: Optional[float]
    bar_count: int
    is_market_open: bool
    closes: List[float]
    volumes: List[float]
    high_of_day: float
    low_of_day: float


@dataclass
class IntradayIndicatorSet:
    vwap: Optional[float] = None
    intra_ma5: Optional[float] = None
    intra_ma10: Optional[float] = None
    intra_ma20: Optional[float] = None
    intra_ma60: Optional[float] = None
    intra_rsi_7: Optional[float] = None
    intra_rsi_14: Optional[float] = None
    volume_ratio: Optional[float] = None
    opening_range_high: Optional[float] = None
    opening_range_low: Optional[float] = None
    price_vs_vwap_pct: Optional[float] = None
    session_return_pct: Optional[float] = None
    range_pct: Optional[float] = None
    cumulative_volume: float = 0.0
    avg_bar_volume: Optional[float] = None
    consecutive_up_bars: int = 0
    consecutive_down_bars: int = 0


@dataclass
class IntradayFactorResult:
    vwap_signal: str = "NEUTRAL"
    range_signal: str = "NEUTRAL"
    momentum_signal: str = "NEUTRAL"
    volume_signal: str = "NORMAL"
    rsi_signal: str = "NEUTRAL"
    micro_trend: str = "NEUTRAL"
    details: dict = field(default_factory=dict)


@dataclass
class IntradaySignalResult:
    action: str = "HOLD"
    signal_type: str = "NONE"
    confidence: float = 0.0
    quality: str = "LOW_CONFIDENCE"
    reason: str = ""
    vwap: Optional[float] = None
    price_vs_vwap_pct: Optional[float] = None
    intraday_trend: str = "NEUTRAL"
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    stop_loss: Optional[float] = None
    instruments: Optional[IntradayIndicatorSet] = None
    factors: Optional[IntradayFactorResult] = None


# =============================================================================
# Section 2: Pure Indicator Functions
# =============================================================================

def _ma(values: list, period: int) -> Optional[float]:
    if len(values) < period or len(values) == 0:
        return None
    return sum(values[-period:]) / period


def compute_vwap(bars: List[IntradayBar]) -> Optional[float]:
    """Cumulative Volume-Weighted Average Price."""
    total_pv = 0.0
    total_v = 0.0
    for b in bars:
        typical = (b.high + b.low + b.close) / 3
        total_pv += typical * b.volume
        total_v += b.volume
    if total_v == 0:
        return None
    return total_pv / total_v


def intraday_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """RSI with Wilder's smoothing on minute-level closes."""
    if len(closes) < period + 1:
        return None
    changes = [closes[i] - closes[i - 1] for i in range(1, period + 1)]
    avg_gain = sum(max(c, 0) for c in changes) / period
    avg_loss = sum(abs(min(c, 0)) for c in changes) / period
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + abs(min(change, 0))) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def compute_volume_profile(volumes: List[float], recent_bars: int = 5) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compare recent volume to overall average. Returns (avg_all, recent_avg, volume_ratio)."""
    if len(volumes) < recent_bars + 1:
        return None, None, None
    avg_all = sum(volumes) / len(volumes) if volumes else 1.0
    if avg_all == 0:
        return None, None, None
    recent_avg = sum(volumes[-recent_bars:]) / recent_bars
    volume_ratio = recent_avg / avg_all
    return avg_all, recent_avg, volume_ratio


def compute_opening_range(bars: List[IntradayBar], first_n_minutes: int = 30) -> Tuple[Optional[float], Optional[float]]:
    """Find high/low of the first N minutes of trading (A-share: 9:30-10:00)."""
    if len(bars) < first_n_minutes:
        return None, None
    opening_bars = bars[:first_n_minutes]
    range_high = max(b.high for b in opening_bars)
    range_low = min(b.low for b in opening_bars)
    return range_high, range_low


def count_consecutive_bars(closes: List[float]) -> Tuple[int, int]:
    """Count consecutive up/down bars from the most recent."""
    if len(closes) < 2:
        return 0, 0
    up = down = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            up += 1
        else:
            break
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            down += 1
        else:
            break
    return up, down


# =============================================================================
# Section 3: Intraday Resolution
# =============================================================================

A_MARKET_OPEN = time(9, 30)
A_MARKET_CLOSE = time(15, 0)
A_MARKET_LUNCH_START = time(11, 30)
A_MARKET_LUNCH_END = time(13, 0)


def _is_a_market_open(now: datetime = None) -> bool:
    """Check if A-share market is currently in trading session."""
    if now is None:
        now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    if A_MARKET_OPEN <= t <= A_MARKET_LUNCH_START:
        return True
    if A_MARKET_LUNCH_END <= t <= A_MARKET_CLOSE:
        return True
    return False


def resolve_intraday_data(
    raw_bars: list,
    current_price: float,
    prev_close: float,
    now: datetime = None,
    target_date: date = None,
) -> IntradayResolvedData:
    """Parse raw API dicts into IntradayResolvedData."""
    if now is None:
        now = datetime.now()
    today = target_date if target_date is not None else now.date()

    bars = []
    for d in raw_bars:
        ts = d.get("timestamp")
        if ts is None:
            continue
        bars.append(IntradayBar(
            open=float(d.get("open", d.get("close", 0))),
            high=float(d.get("high", d.get("close", 0))),
            low=float(d.get("low", d.get("close", 0))),
            close=float(d.get("close", 0)),
            volume=float(d.get("volume", 0)),
            timestamp=ts if isinstance(ts, datetime) else ts,
        ))

    # Filter to target date
    bars_today = [b for b in bars if b.timestamp.date() == today]

    # If no matching bars, try: all bars might be from the same date, use them
    if not bars_today and bars:
        bar_date = bars[-1].timestamp.date()
        if bar_date == today:
            bars_today = bars[-240:]  # at most one day

    if target_date is not None:
        is_market_open = len(bars_today) > 0  # has data = was a trading day
    else:
        is_market_open = _is_a_market_open(now)

    closes = [b.close for b in bars_today]
    volumes = [b.volume for b in bars_today]

    today_open = bars_today[0].open if bars_today else None
    bar_count = len(bars_today)

    cp = current_price if current_price else prev_close
    high_of_day = max(b.high for b in bars_today) if bars_today else cp
    low_of_day = min(b.low for b in bars_today) if bars_today else cp

    return IntradayResolvedData(
        bars=bars,
        bars_today=bars_today,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        bar_count=bar_count,
        is_market_open=is_market_open,
        closes=closes,
        volumes=volumes,
        high_of_day=high_of_day,
        low_of_day=low_of_day,
    )


# =============================================================================
# Section 4: Indicator Computation
# =============================================================================

def compute_intraday_indicators(resolved: IntradayResolvedData, opening_range_bars: int = 6) -> IntradayIndicatorSet:
    """Compute all intraday indicators from resolved data.

    Args:
        resolved: resolved intraday data
        opening_range_bars: number of bars for opening range (6 for 5-min = 30min, 30 for 1-min)
    """
    ind = IntradayIndicatorSet()
    closes = resolved.closes
    volumes = resolved.volumes

    if not closes:
        return ind  # No data available, return empty indicator set

    ind.vwap = compute_vwap(resolved.bars_today)
    ind.intra_ma5 = _ma(closes, 5)
    ind.intra_ma10 = _ma(closes, 10)
    ind.intra_ma20 = _ma(closes, 20)
    ind.intra_ma60 = _ma(closes, 60) if len(closes) >= 60 else _ma(closes, len(closes))
    ind.intra_rsi_14 = intraday_rsi(closes, 14)
    ind.intra_rsi_7 = intraday_rsi(closes, 7)

    avg_vol, _, vol_ratio = compute_volume_profile(volumes)
    ind.avg_bar_volume = avg_vol
    ind.volume_ratio = vol_ratio

    ind.opening_range_high, ind.opening_range_low = compute_opening_range(resolved.bars_today, opening_range_bars)

    if ind.vwap and resolved.current_price and ind.vwap > 0:
        ind.price_vs_vwap_pct = (resolved.current_price - ind.vwap) / ind.vwap * 100

    if resolved.today_open and resolved.today_open > 0:
        ind.session_return_pct = (resolved.current_price - resolved.today_open) / resolved.today_open * 100

    if resolved.prev_close > 0:
        ind.range_pct = (resolved.high_of_day - resolved.low_of_day) / resolved.prev_close * 100

    ind.cumulative_volume = sum(volumes)
    up, down = count_consecutive_bars(closes)
    ind.consecutive_up_bars = up
    ind.consecutive_down_bars = down

    return ind


# =============================================================================
# Section 5: Factor Evaluation
# =============================================================================

def evaluate_intraday_factors(
    ind: IntradayIndicatorSet,
    resolved: IntradayResolvedData,
) -> IntradayFactorResult:
    """Evaluate intraday-specific factors."""
    factors = IntradayFactorResult()

    # VWAP signal
    if ind.price_vs_vwap_pct is not None:
        if ind.price_vs_vwap_pct > 0.4:
            factors.vwap_signal = "ABOVE_VWAP"
        elif ind.price_vs_vwap_pct < -0.4:
            factors.vwap_signal = "BELOW_VWAP"
        else:
            factors.vwap_signal = "AT_VWAP"

    # Opening range
    if ind.opening_range_high and ind.opening_range_low and ind.opening_range_high > ind.opening_range_low:
        if resolved.current_price > ind.opening_range_high:
            factors.range_signal = "BREAKOUT_UP"
        elif resolved.current_price < ind.opening_range_low:
            factors.range_signal = "BREAKOUT_DOWN"
        else:
            factors.range_signal = "INSIDE_RANGE"

    # Micro-trend (MA5 vs MA20 on minute closes)
    if ind.intra_ma5 is not None and ind.intra_ma20 is not None:
        if ind.intra_ma5 > ind.intra_ma20:
            factors.micro_trend = "UP"
        elif ind.intra_ma5 < ind.intra_ma20:
            factors.micro_trend = "DOWN"
    elif ind.intra_ma5 is not None and resolved.current_price:
        factors.micro_trend = "UP" if resolved.current_price > ind.intra_ma5 else "DOWN"

    # Momentum (from RSI)
    if ind.intra_rsi_14 is not None:
        if ind.intra_rsi_14 >= 55:
            factors.momentum_signal = "BULLISH"
        elif ind.intra_rsi_14 <= 40:
            factors.momentum_signal = "BEARISH"

    # Volume
    if ind.volume_ratio is not None:
        if ind.volume_ratio > 2.0:
            factors.volume_signal = "SURGE"
        elif ind.volume_ratio > 1.3:
            factors.volume_signal = "ELEVATED"
        elif ind.volume_ratio < 0.5:
            factors.volume_signal = "DROP"

    # RSI extremes
    if ind.intra_rsi_14 is not None:
        if ind.intra_rsi_14 < 30:
            factors.rsi_signal = "OVERSOLD"
        elif ind.intra_rsi_14 > 75:
            factors.rsi_signal = "OVERBOUGHT"

    return factors


# =============================================================================
# Section 6: Intraday Decision Engine
# =============================================================================

class IntradayDecisionEngine:
    """Rule-based intraday decision engine.

    Daily trend provides DIRECTIONAL BIAS:
      - Daily UP: prefer T_BUY on dips, allow T_SELL on overbought spikes
      - Daily DOWN: prefer T_SELL on rallies, suppress T_BUY
      - Daily NEUTRAL: symmetric but higher thresholds
      - Daily SELL_ALL active: suppress all buys entirely
    """

    @staticmethod
    def decide(
        daily_trend: str,
        daily_trend_strength: float,
        daily_action: str,
        factors: IntradayFactorResult,
        ind: IntradayIndicatorSet,
        resolved: IntradayResolvedData,
        has_position: bool,
    ) -> IntradaySignalResult:
        result = IntradaySignalResult()
        result.instruments = ind
        result.factors = factors
        result.vwap = ind.vwap
        result.price_vs_vwap_pct = ind.price_vs_vwap_pct
        result.intraday_trend = factors.micro_trend

        # Guard: insufficient data (need at least 15 bars = 15 min with 1-min kline)
        if resolved.bar_count < 15:
            result.action = "HOLD"
            result.reason = f"日内数据不足 ({resolved.bar_count} 分钟)"
            result.quality = "LOW_CONFIDENCE"
            return result

        # Guard: market closed
        if not resolved.is_market_open:
            result.action = "HOLD"
            result.reason = "非交易时段"
            result.quality = "LOW_CONFIDENCE"
            return result

        # Set support/resistance from VWAP and opening range
        IntradayDecisionEngine._set_levels(result, resolved, ind)

        # Collect candidate signals
        signals = []
        daily_up = daily_trend == "UP"
        daily_down = daily_trend == "DOWN"
        daily_sell_all = "SELL_ALL" in str(daily_action).upper()

        # ---- Signal 1: Opening range breakout (highest confidence) ----
        within_opening_hour = resolved.bar_count <= 60  # first 60 min with 1-min bars

        if within_opening_hour and factors.range_signal == "BREAKOUT_UP" and factors.volume_signal in ("SURGE", "ELEVATED"):
            if not daily_sell_all:
                signals.append(("BREAKOUT", "T_BUY", 0.82,
                    f"开盘放量突破 {ind.opening_range_high:.3f}"))
        elif within_opening_hour and factors.range_signal == "BREAKOUT_DOWN" and factors.volume_signal in ("SURGE", "ELEVATED"):
            signals.append(("BREAKOUT", "T_SELL", 0.80,
                f"开盘放量跌破 {ind.opening_range_low:.3f}"))

        # ---- Signal 2: VWAP reversion with daily trend context ----
        if factors.vwap_signal in ("BELOW_VWAP", "ABOVE_VWAP") and ind.price_vs_vwap_pct is not None:
            pct_off = abs(ind.price_vs_vwap_pct)
            is_below = factors.vwap_signal == "BELOW_VWAP"

            if daily_up and is_below and pct_off > 0.5:
                signals.append(("VWAP_REVERSAL", "T_BUY", min(0.75, 0.55 + pct_off * 0.15),
                    f"日内跌至VWAP下方 {pct_off:.1f}%, 日线上升趋势, 逢低买入"))
            elif daily_up and not is_below and pct_off > 1.0 and has_position:
                signals.append(("VWAP_REVERSAL", "T_SELL", 0.60,
                    f"日内涨至VWAP上方 {pct_off:.1f}%, 日线上升趋势, 高位减仓"))

            elif daily_down and not is_below and pct_off > 0.5:
                signals.append(("VWAP_REVERSAL", "T_SELL", min(0.75, 0.55 + pct_off * 0.15),
                    f"日内涨至VWAP上方 {pct_off:.1f}%, 日线下降趋势, 逢高卖出"))

            elif not daily_up and not daily_down and pct_off > 1.2:
                action = "T_BUY" if is_below else "T_SELL"
                signals.append(("VWAP_REVERSAL", action, min(0.65, 0.50 + pct_off * 0.1),
                    f"大幅偏离VWAP {pct_off:.1f}%, 均值回归"))

        # ---- Signal 3: RSI extremes ----
        if factors.rsi_signal == "OVERSOLD" and not daily_sell_all:
            if daily_down:
                # In downtrend, oversold can still bounce but weak confidence
                signals.append(("RSI_EXTREME", "T_BUY", 0.50,
                    f"分钟RSI {ind.intra_rsi_14:.1f} 超卖, 短线反弹(逆趋势,低置信度)"))
            else:
                signals.append(("RSI_EXTREME", "T_BUY", 0.65,
                    f"分钟RSI {ind.intra_rsi_14:.1f} 超卖, 短线反弹"))
        elif factors.rsi_signal == "OVERBOUGHT":
            if not daily_up and has_position:
                signals.append(("RSI_EXTREME", "T_SELL", 0.60,
                    f"分钟RSI {ind.intra_rsi_14:.1f} 超买, 短线回调"))

        # ---- Signal 4: Micro-trend + momentum ----
        if factors.micro_trend == "UP" and factors.momentum_signal == "BULLISH" and not daily_sell_all:
            signals.append(("MICRO_TREND", "T_BUY", 0.55, "分时多头排列"))
        elif factors.micro_trend == "DOWN" and factors.momentum_signal == "BEARISH" and has_position:
            signals.append(("MICRO_TREND", "T_SELL", 0.55, "分时空头排列"))

        # ---- Signal 5: Volume surge with direction ----
        if factors.volume_signal == "SURGE":
            if factors.micro_trend == "UP" and not daily_sell_all:
                signals.append(("VOLUME_SURGE", "T_BUY", 0.60, "放量拉升"))
            elif factors.micro_trend == "DOWN" and has_position:
                signals.append(("VOLUME_SURGE", "T_SELL", 0.60, "放量下跌"))

        # ---- Combine ----
        if not signals:
            result.action = "HOLD"
            pct_str = f"{ind.price_vs_vwap_pct:+.1f}%" if ind.price_vs_vwap_pct is not None else ""
            result.reason = f"无明确日内信号 (VWAP {pct_str})" if pct_str else "无明确日内信号"
            result.quality = "LOW_CONFIDENCE"
            result.confidence = 0.3
            return result

        # Pick highest confidence signal
        signals.sort(key=lambda x: x[2], reverse=True)
        best = signals[0]

        result.action = best[1]
        result.signal_type = best[0]
        result.confidence = best[2]
        result.reason = best[3]

        # Quality based on confidence
        if result.confidence >= 0.75:
            result.quality = "HIGH_CONFIDENCE"
        elif result.confidence >= 0.55:
            result.quality = "NORMAL"
        else:
            result.quality = "LOW_CONFIDENCE"

        # Set stop loss for buy signals
        if result.action == "T_BUY":
            # Stop just below VWAP or intraday support
            candidates = [v for v in [ind.vwap, ind.intra_ma20, ind.opening_range_low] if v is not None]
            if candidates:
                ref = min(candidates)
                result.stop_loss = round(ref * 0.996, 4)
        elif result.action == "T_SELL" and has_position:
            # Stop (for short covering) just above VWAP or intraday resistance
            candidates = [v for v in [ind.vwap, ind.intra_ma20, ind.opening_range_high] if v is not None]
            if candidates:
                ref = max(candidates)
                result.stop_loss = round(ref * 1.004, 4)

        return result

    @staticmethod
    def _set_levels(result: IntradaySignalResult, resolved: IntradayResolvedData, ind: IntradayIndicatorSet):
        """Set support/resistance levels for the signal."""
        price = resolved.current_price
        support_candidates = []
        resistance_candidates = []

        if ind.opening_range_low:
            support_candidates.append(ind.opening_range_low)
            resistance_candidates.append(ind.opening_range_high)
        if ind.vwap:
            if price < ind.vwap:
                resistance_candidates.append(ind.vwap)
            else:
                support_candidates.append(ind.vwap)
        if ind.intra_ma20:
            if price < ind.intra_ma20:
                resistance_candidates.append(ind.intra_ma20)
            else:
                support_candidates.append(ind.intra_ma20)

        if support_candidates:
            result.support_level = max(s for s in support_candidates if s < price) if any(s < price for s in support_candidates) else min(support_candidates)
        if resistance_candidates:
            result.resistance_level = min(r for r in resistance_candidates if r > price) if any(r > price for r in resistance_candidates) else max(resistance_candidates)


# =============================================================================
# Section 7: Historical Replay — walk through each bar to find signal points
# =============================================================================

def replay_intraday_signals(
    bars: List[IntradayBar],
    prev_close: float,
    target_date: date,
    daily_trend: str,
    daily_trend_strength: float,
    daily_action: str,
    has_position: bool,
    min_bars: int = 15,
) -> List[dict]:
    """Replay the intraday decision engine bar-by-bar to find all signal points.

    Returns list of marker dicts with bar_index, time, action, signal_type, etc.
    Deduplicates consecutive same-type signals.
    """
    if len(bars) < min_bars:
        return []

    markers = []
    last_action = "HOLD"

    for i in range(min_bars, len(bars) + 1):
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

        ind = compute_intraday_indicators(resolved, opening_range_bars=30)
        factors = evaluate_intraday_factors(ind, resolved)
        signal = IntradayDecisionEngine.decide(
            daily_trend, daily_trend_strength, daily_action,
            factors, ind, resolved, has_position,
        )

        if signal.action != last_action and signal.action in ("T_BUY", "T_SELL"):
            bar = bars[i - 1]
            type_cn = {
                "BREAKOUT": "突破",
                "VWAP_REVERSAL": "VWAP回归",
                "RSI_EXTREME": "RSI极端",
                "MICRO_TREND": "分时趋势",
                "VOLUME_SURGE": "放量",
            }.get(signal.signal_type, signal.signal_type)
            markers.append({
                "bar_index": i - 1,
                "time": bar.timestamp.strftime("%H:%M"),
                "action": signal.action,
                "signal_type": type_cn,
                "confidence": round(signal.confidence, 2),
                "price": round(bar.close, 4 if bar.close < 1 else 3),
                "reason": signal.reason,
            })
            last_action = signal.action

    return markers
