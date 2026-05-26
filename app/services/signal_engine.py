"""
Multi-Factor Signal Engine — 专业多因子股票/ETF 信号引擎.

Architecture:
  Stage 1: Data resolution (kline ambiguity + non-trading day detection)
  Stage 2: Technical indicators (pure functions)
  Stage 3: Factor evaluators (independent assessments)
  Stage 4: Rule-based decision tree (confluence, not weighted sum)
  Stage 5: Output + backward compatibility mapping

Philosophy: 每个买卖信号必须有明确的多因子确认，不用手工加权打分。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime, date
import math
import time

from app.services.stock_service import StockService


# =============================================================================
# Section 1: Data Models
# =============================================================================

@dataclass
class KlineBar:
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: Optional[datetime] = None


@dataclass
class ResolvedData:
    """Result of kline ambiguity resolution — definitive data for analysis."""
    bars: List[KlineBar]
    current_price: float
    yesterday_close: float         # last COMPLETED bar's close
    is_trading_day: bool
    closes: List[float]            # completed closes + [current_price] if trading
    volumes: List[float]           # completed volumes
    last_completed_close: float    # closes[-1] of completed bars


@dataclass
class PositionInfo:
    has_position: bool
    cost: Optional[float] = None
    quantity: Optional[int] = None
    initial_capital: float = 2000.0
    profit_rate: Optional[float] = None
    position_ratio: float = 0.0
    rise_from_low_pct: float = 999.0
    is_low_position: bool = False
    is_high_position: bool = False
    cooldown_remaining: int = 0
    cumulative_return: Optional[float] = None


@dataclass
class IndicatorSet:
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal_line: Optional[float] = None
    macd_histogram: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_mid: Optional[float] = None
    bollinger_bandwidth: Optional[float] = None
    bollinger_position: Optional[float] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    weekly_trend: str = "NEUTRAL"
    consecutive_up_days: int = 0


@dataclass
class FactorResult:
    trend: str = "NEUTRAL"
    trend_strength: float = 50.0
    trend_level: str = "NEUTRAL"
    momentum: str = "NEUTRAL"
    volume: str = "NORMAL"
    volatility: str = "NORMAL"
    market_filter: str = "CAUTION"
    risk_level: str = "MEDIUM"
    details: dict = field(default_factory=dict)


@dataclass
class SignalResult:
    action: str = "HOLD"
    buy_signal: bool = False
    sell_signal: bool = False
    ai_signal: str = "HOLD"
    ai_confidence: float = 0.5
    ai_risk_level: str = "MEDIUM"
    signal_quality: str = "LOW_CONFIDENCE"
    reason: str = ""
    decision_factors: List[str] = field(default_factory=list)
    signal_score: float = 50.0
    buy_conditions: List[Tuple[str, bool, str]] = field(default_factory=list)
    sell_triggers: List[Tuple[str, str, str]] = field(default_factory=list)
    dynamic_stop_price: Optional[float] = None
    dynamic_stop_loss_pct: Optional[float] = None
    stop_loss_triggered: bool = False
    suggested_position_size: Optional[float] = None


# =============================================================================
# Section 2: Pure Indicator Functions (stateless, testable)
# =============================================================================

def _ma(values: list, period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema(values: list, period: int) -> Optional[float]:
    """Exponential Moving Average (EMA)."""
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    result = sum(values[:period]) / period
    for v in values[period:]:
        result = v * k + result * (1 - k)
    return result


def _ema_series(values: list, period: int) -> List[float]:
    """Compute full EMA series starting from index period-1."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    result = [seed]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def rsi_wilder(closes: list, period: int = 14) -> Optional[float]:
    """RSI with Wilder's smoothing (professional standard)."""
    if len(closes) < period + 1:
        return None
    # First average gain/loss = SMA of first 'period' changes
    changes = [closes[i] - closes[i - 1] for i in range(1, period + 1)]
    avg_gain = sum(max(c, 0) for c in changes) / period
    avg_loss = sum(abs(min(c, 0)) for c in changes) / period
    # Wilder's smoothing for remaining
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0)) / period
        avg_loss = (avg_loss * (period - 1) + abs(min(change, 0))) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd_full(closes: list, fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute MACD line, signal line, and histogram using EMA series."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast_series = _ema_series(closes, fast)
    ema_slow_series = _ema_series(closes, slow)
    # Align: MACD = EMA(fast) - EMA(slow) for each index where both exist
    offset = slow - fast
    macd_values = []
    for i in range(len(ema_slow_series)):
        fast_val = ema_fast_series[offset + i]
        slow_val = ema_slow_series[i]
        macd_values.append(fast_val - slow_val)
    macd_line = macd_values[-1]
    signal_series = _ema_series(macd_values, signal)
    if not signal_series:
        return macd_line, None, None
    signal_line = signal_series[-1]
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0):
    """Bollinger Bands: upper, lower, mid, bandwidth, %B position."""
    if len(closes) < period:
        return None, None, None, None, None
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    bandwidth = (upper - lower) / mid if mid != 0 else 0.0
    if upper != lower:
        position = (closes[-1] - lower) / (upper - lower)
    else:
        position = 0.5
    return upper, lower, mid, bandwidth, position


def atr(klines: List[KlineBar], period: int = 14) -> Optional[float]:
    """ATR with Wilder's smoothing."""
    if len(klines) <= period:
        return None
    true_ranges = []
    for i in range(1, len(klines)):
        tr = max(
            klines[i].high - klines[i].low,
            abs(klines[i].high - klines[i - 1].close),
            abs(klines[i].low - klines[i - 1].close)
        )
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    # First ATR = SMA of first 'period' TR values
    atr_val = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def compute_volume_ratio(volumes: list, is_trading_day: bool) -> float:
    """Volume ratio: reference / avg of previous 5 completed bars."""
    if len(volumes) < 6:
        return 0.0
    # If today is trading, last volume entry may be incomplete
    if is_trading_day:
        avg_5 = sum(volumes[-6:-1]) / 5
        ref = volumes[-1] if volumes[-1] > 0 else 0
    else:
        avg_5 = sum(volumes[-6:-1]) / 5
        ref = volumes[-1]
    return ref / avg_5 if avg_5 > 0 else 0.0


def count_consecutive_up(resolved: ResolvedData) -> int:
    """Count consecutive up days including today if applicable."""
    closes = resolved.closes
    if len(closes) < 2:
        return 0
    count = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] > closes[i - 1]:
            count += 1
        else:
            break
    return count


def count_ma_below_days(closes: list, period: int = 20, max_days: int = 10) -> int:
    """Count consecutive days where close < MA(period), backward from most recent."""
    count = 0
    for end_idx in range(len(closes), period - 1, -1):
        ma = _ma(closes, period)
        ma_at_point = sum(closes[end_idx - period:end_idx]) / period if end_idx >= period else None
        if ma_at_point is None or closes[end_idx - 1] >= ma_at_point:
            break
        count += 1
        if count >= max_days:
            break
    return count


def compute_weekly_trend(symbol: str, market: str) -> str:
    """Check macro weekly trend using ~25-day and ~50-day MAs on daily data."""
    try:
        raw = StockService.get_price_history_with_volume(symbol, market, days=120)
        closes = [d.get("close", d["price"]) for d in raw]
        ma25 = _ma(closes, 25)
        ma50 = _ma(closes, 50)
        if ma25 is None or ma50 is None:
            return "NEUTRAL"
        current = closes[-1]
        if ma25 > ma50 and current > ma25:
            return "UP"
        elif ma25 < ma50 and current < ma25:
            return "DOWN"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"


# =============================================================================
# Section 3: K-Line Data Resolution
# =============================================================================

def resolve_kline_ambiguity(
    raw_klines: list,
    current_price: float,
    current_time: Optional[datetime] = None
) -> ResolvedData:
    """
    Determine whether the last kline bar represents today or yesterday.
    Uses timestamp + price comparison to handle all edge cases.
    """
    if not raw_klines:
        raise ValueError("Empty kline data")

    current_time = current_time or datetime.now()
    today = current_time.date()

    # Parse into structured bars
    bars = []
    for d in raw_klines:
        ts = d.get("timestamp")
        bars.append(KlineBar(
            open=float(d.get("open", d.get("price", 0))),
            high=float(d.get("high", d.get("price", 0))),
            low=float(d.get("low", d.get("price", 0))),
            close=float(d.get("close", d["price"])),
            volume=float(d.get("volume", 0)),
            timestamp=ts
        ))

    last_bar = bars[-1]
    last_bar_date = last_bar.timestamp.date() if last_bar.timestamp else None
    if last_bar.close > 0:
        price_diff_pct = abs(current_price - last_bar.close) / last_bar.close * 100
    else:
        price_diff_pct = 100.0

    # CASE 1: Last bar timestamp IS today — API returned today's bar
    if last_bar_date == today:
        yesterday_close = bars[-2].close if len(bars) >= 2 else last_bar.close
        completed_bars = bars[:-1]
        completed_closes = [b.close for b in completed_bars]
        completed_volumes = [b.volume for b in completed_bars]
        if price_diff_pct > 0.1:
            # Price moving = active trading
            closes = completed_closes + [current_price]
            volumes = completed_volumes + [last_bar.volume]
            is_trading_day = True
        else:
            # Market closed, today's bar is complete
            closes = [b.close for b in bars]
            volumes = [b.volume for b in bars]
            is_trading_day = True
    else:
        # CASE 2: Last bar is yesterday or older
        yesterday_close = last_bar.close
        completed_closes = [b.close for b in bars]
        completed_volumes = [b.volume for b in bars]
        if price_diff_pct > 0.1:
            # Price moved from last close — today IS trading
            closes = completed_closes + [current_price]
            volumes = completed_volumes + [0]  # no volume data yet
            is_trading_day = True
        else:
            # No price movement — likely non-trading day
            closes = completed_closes
            volumes = completed_volumes
            is_trading_day = (
                today.weekday() < 5
                and 9 <= current_time.hour < 17
                and last_bar_date is not None
                and (today - last_bar_date).days <= 3
            )

    return ResolvedData(
        bars=bars,
        current_price=current_price,
        yesterday_close=yesterday_close,
        is_trading_day=is_trading_day,
        closes=closes,
        volumes=volumes,
        last_completed_close=bars[-1].close if last_bar_date != today else (
            bars[-2].close if len(bars) >= 2 else bars[-1].close
        ),
    )


# =============================================================================
# Section 4: Market Filter (沪深300 reference)
# =============================================================================

_market_cache = {"data": None, "timestamp": 0}
_MARKET_SYMBOL = "000300"
_MARKET_CACHE_TTL = 60


def get_market_filter() -> dict:
    """Fetch 沪深300 data and determine market regime. Cached 60s."""
    global _market_cache
    now = time.time()
    if _market_cache["data"] is not None and now - _market_cache["timestamp"] < _MARKET_CACHE_TTL:
        return _market_cache["data"]

    try:
        raw = StockService.get_price_history_with_volume(_MARKET_SYMBOL, "CN", days=35)
        closes = [d.get("close", d["price"]) for d in raw]
        if len(closes) < 25:
            raise ValueError("沪深300数据不足")
        ma5 = _ma(closes, 5)
        ma20 = _ma(closes, 20)
        current = closes[-1]
        rsi = rsi_wilder(closes)
        # Simple trend strength for market
        if ma5 and ma20:
            if ma5 > ma20 and current > ma20:
                strength = 65.0
            elif current > ma20:
                strength = 55.0
            elif ma5 < ma20 and current < ma20:
                strength = 30.0
            else:
                strength = 45.0
        else:
            strength = 50.0

        if rsi is not None and rsi > 78:
            strength -= 8
        elif rsi is not None and rsi < 25:
            strength -= 5
        strength = max(0, min(100, strength))

        if current < ma20 and strength < 42:
            market_filter = "BLOCK"
            reason = "沪深300低于MA20且趋势偏弱"
        elif current < ma20 or strength < 50:
            market_filter = "CAUTION"
            reason = "沪深300趋势一般，降低买入权重"
        else:
            market_filter = "PASS"
            reason = "沪深300趋势过滤通过"

        data = {
            "market_symbol": _MARKET_SYMBOL,
            "market_trend": "UP" if strength >= 55 else "DOWN" if strength < 45 else "NEUTRAL",
            "market_filter": market_filter,
            "market_score": round(strength, 1),
            "market_reason": reason,
            "market_rsi": round(rsi, 2) if rsi is not None else None,
            "market_trend_strength": round(strength, 1),
            "market_trend_level": "UP" if strength >= 58 else "DOWN" if strength < 43 else "NEUTRAL",
        }
    except Exception as e:
        data = {
            "market_symbol": _MARKET_SYMBOL,
            "market_trend": "NEUTRAL",
            "market_filter": "CAUTION",
            "market_score": 50.0,
            "market_reason": f"沪深300过滤数据不可用: {e}",
            "market_rsi": None,
            "market_trend_strength": 50.0,
            "market_trend_level": "NEUTRAL",
        }

    _market_cache = {"data": data, "timestamp": now}
    return data


# =============================================================================
# Section 5: Factor Evaluators
# =============================================================================

def evaluate_trend(indicators: IndicatorSet, resolved: ResolvedData) -> dict:
    """Evaluate trend strength and direction."""
    score = 50.0
    if indicators.ma5 and indicators.ma10 and indicators.ma20:
        # MA alignment
        if indicators.ma5 > indicators.ma10 > indicators.ma20:
            score += 22
        elif indicators.ma5 < indicators.ma10 < indicators.ma20:
            score -= 22
        else:
            score += 4 if indicators.ma5 > indicators.ma20 else -4

        # Price vs MAs
        if resolved.current_price > indicators.ma5 > indicators.ma10:
            score += 12
        elif resolved.current_price < indicators.ma5 < indicators.ma10:
            score -= 12

        # Distance from MA20
        if indicators.ma20 > 0:
            distance = (resolved.current_price - indicators.ma20) / indicators.ma20
            score += max(-18, min(18, distance * 400))

    # 5-day return
    if len(resolved.closes) >= 6 and resolved.closes[-6] > 0:
        five_day_return = (resolved.current_price - resolved.closes[-6]) / resolved.closes[-6]
        score += max(-14, min(14, five_day_return * 220))

    # Weekly trend modifier
    if indicators.weekly_trend == "UP":
        score += 5
    elif indicators.weekly_trend == "DOWN":
        score -= 10

    score = round(max(0, min(100, score)), 1)

    if score >= 75:
        level = "STRONG_UP"
        trend = "UP"
    elif score >= 58:
        level = "UP"
        trend = "UP"
    elif score >= 43:
        level = "NEUTRAL"
        trend = "NEUTRAL" if 45 <= score < 55 else ("UP" if score >= 50 else "DOWN")
    elif score >= 28:
        level = "DOWN"
        trend = "DOWN"
    else:
        level = "STRONG_DOWN"
        trend = "DOWN"

    # Check pullback (price close to MA10 or MA20 while above MA20)
    ma10_dist = abs(resolved.current_price - indicators.ma10) / indicators.ma10 if indicators.ma10 else 1
    ma20_dist = abs(resolved.current_price - indicators.ma20) / indicators.ma20 if indicators.ma20 else 1
    pullback = (ma10_dist < 0.02 or ma20_dist < 0.025) and resolved.current_price >= (indicators.ma20 or 0)

    return {"trend": trend, "trend_strength": score, "trend_level": level, "pullback": pullback}


def evaluate_momentum(indicators: IndicatorSet, resolved: ResolvedData) -> str:
    """Evaluate momentum as BULLISH/BEARISH/NEUTRAL."""
    if indicators.rsi is None:
        return "NEUTRAL"

    # RSI assessment
    if 50 <= indicators.rsi <= 70:
        rsi_bullish = True
    elif 35 <= indicators.rsi < 50:
        rsi_bullish = False  # neutral-bearish
    elif indicators.rsi > 70:
        rsi_bullish = True   # strong but watch for overbought
    else:
        rsi_bullish = False  # oversold

    # MACD assessment
    macd_bullish = False
    if indicators.macd_line is not None and indicators.macd_signal_line is not None:
        if indicators.macd_line > indicators.macd_signal_line and (
            indicators.macd_histogram is None or indicators.macd_histogram > 0
        ):
            macd_bullish = True

    # Confluence
    if rsi_bullish and macd_bullish:
        return "BULLISH"
    elif not rsi_bullish and not macd_bullish:
        return "BEARISH"
    elif rsi_bullish and not macd_bullish:
        return "BULLISH"  # RSI leads, MACD may follow
    else:
        return "BEARISH"


def evaluate_volume(indicators: IndicatorSet, resolved: ResolvedData) -> str:
    """Evaluate volume-price relationship."""
    is_up_day = resolved.current_price > resolved.yesterday_close
    is_down_day = resolved.current_price < resolved.yesterday_close
    vr = indicators.volume_ratio or 1.0

    if is_up_day and vr > 1.5:
        return "ACCUMULATION"
    elif is_up_day and vr < 0.7:
        return "WEAK_UP"
    elif is_down_day and vr > 1.5:
        return "DISTRIBUTION"
    elif is_down_day and vr < 0.7:
        return "WEAK_DOWN"
    elif vr > 2.5 and abs(resolved.current_price - resolved.yesterday_close) / max(resolved.yesterday_close, 0.01) < 0.005:
        return "CHURN"
    return "NORMAL"


def evaluate_position(
    resolved: ResolvedData,
    cost: Optional[float],
    quantity: Optional[int],
    initial_capital: float,
    max_position_ratio: float,
    cooldown_remaining: int,
    last_stop_loss_date,
    cooldown_days: int,
    consecutive_up_days: int = 0,
) -> PositionInfo:
    """Build PositionInfo from raw inputs."""
    has_position = cost is not None and cost > 0 and quantity is not None and quantity > 0
    profit_rate = (resolved.current_price - float(cost)) / float(cost) if has_position else None
    position_value = resolved.current_price * quantity if has_position else 0
    position_ratio = position_value / initial_capital if initial_capital > 0 else 0

    # Rise from 20d low
    if len(resolved.closes) >= 20:
        low_20 = min(resolved.closes[-20:])
        rise_from_low_pct = (resolved.current_price - low_20) / low_20 * 100 if low_20 > 0 else 999.0
    else:
        rise_from_low_pct = 999.0

    is_low_position = rise_from_low_pct <= 8
    is_high_position = consecutive_up_days >= 3 and resolved.current_price > (_ma(resolved.closes, 20) or 0)

    cumulative_return = ((resolved.current_price - float(cost)) / float(cost) * 100) if has_position else None

    return PositionInfo(
        has_position=has_position,
        cost=cost,
        quantity=quantity,
        initial_capital=initial_capital,
        profit_rate=profit_rate,
        position_ratio=position_ratio,
        rise_from_low_pct=rise_from_low_pct,
        is_low_position=is_low_position,
        is_high_position=is_high_position,
        cooldown_remaining=cooldown_remaining,
        cumulative_return=cumulative_return,
    )


def compute_stop_loss(
    position: PositionInfo,
    indicators: IndicatorSet,
    resolved: ResolvedData,
    profile: dict,
) -> Tuple[Optional[float], Optional[float], bool]:
    """Compute dynamic stop loss. Returns (stop_price, stop_loss_pct, triggered)."""
    if not position.has_position:
        return None, None, False

    cost = float(position.cost)
    stop_loss_param = profile.get("stop_loss", -0.05)
    fixed_stop = cost * (1 + stop_loss_param)

    # ATR-based trailing stop: recent 20d high - 2*ATR
    atr_val = indicators.atr
    if atr_val and len(resolved.bars) >= 20:
        recent_high = max(b.high for b in resolved.bars[-20:])
        atr_stop = recent_high - 2 * atr_val
        dynamic_stop = max(fixed_stop, atr_stop) if atr_stop else fixed_stop
    else:
        dynamic_stop = fixed_stop

    stop_loss_pct = ((dynamic_stop - cost) / cost * 100) if cost > 0 else None
    # FIXED: stop loss triggers on price alone, no market/trend gate
    triggered = resolved.current_price <= dynamic_stop

    return dynamic_stop, stop_loss_pct, triggered


# =============================================================================
# Section 6: Rule-Based Decision Tree
# =============================================================================

class RuleEngine:
    """Rule-based decision engine — signals by confluence, not weighted sum."""

    @staticmethod
    def decide(
        factors: FactorResult,
        indicators: IndicatorSet,
        resolved: ResolvedData,
        position: PositionInfo,
        profile: dict,
        instrument_type: str,
        market_data: dict,
    ) -> SignalResult:
        """Main decision entry point."""
        result = SignalResult()
        result.factors = factors
        result.dynamic_stop_price, result.dynamic_stop_loss_pct, result.stop_loss_triggered = \
            compute_stop_loss(position, indicators, resolved, profile)

        # ---- Step 1: Emergency Exits ----
        emergency = RuleEngine._check_emergency_exits(resolved, position, indicators, profile)
        if emergency:
            result.action = emergency["action"]
            result.sell_signal = True
            result.buy_signal = False
            result.ai_signal = "SELL"
            result.reason = emergency["reason"]
            result.signal_quality = "HIGH_CONFIDENCE"
            result.decision_factors.append(emergency["reason"])
            result.ai_confidence = 0.95
            result.ai_risk_level = "HIGH"
            result.sell_triggers = [(emergency["type"], emergency["action"], emergency["reason"])]
            result.signal_score = 10.0
            return result

        # ---- Step 2 & 3: Position-aware logic ----
        if position.has_position:
            # Step 2a: Sell signals (only if holding)
            sell_result = RuleEngine._evaluate_sell(factors, indicators, resolved, position, profile)
            if sell_result["has_signal"]:
                result.action = sell_result["action"]
                result.sell_signal = True
                result.buy_signal = False
                result.ai_signal = sell_result["ai_signal"]
                result.reason = sell_result["reason"]
                result.decision_factors = sell_result["factors"]
                result.sell_triggers = sell_result["triggers"]
                result.signal_quality = sell_result["quality"]
                result.ai_confidence = sell_result["confidence"]
                result.ai_risk_level = factors.risk_level
                result.signal_score = max(5.0, min(40.0, 40.0 - len(sell_result["triggers"]) * 10))
                return result

            # Step 2b: No sell — evaluate ADD or HOLD
            add_result = RuleEngine._evaluate_add(factors, indicators, resolved, position, profile, instrument_type, market_data)
            if add_result["can_add"]:
                result.action = add_result["action"]
                result.buy_signal = True
                result.sell_signal = False
                result.ai_signal = "ADD"
                result.reason = add_result["reason"]
                result.decision_factors = add_result["factors"]
                result.signal_quality = add_result["quality"]
                result.ai_confidence = add_result["confidence"]
                result.ai_risk_level = factors.risk_level
                result.signal_score = add_result["score"]
            else:
                result.action = "HOLD"
                result.reason = f"持仓中，趋势{factors.trend}，动量{factors.momentum}，暂不操作"
                result.decision_factors = [
                    f"趋势: {factors.trend}({factors.trend_level})",
                    f"动量: {factors.momentum}",
                    f"量能: {factors.volume}",
                    f"波动率: {factors.volatility}",
                    f"市场过滤: {factors.market_filter}",
                ]
                result.signal_quality = "NORMAL"
                result.ai_confidence = 0.6
                result.signal_score = 50.0
            return result

        # ---- Step 3: No Position — evaluate BUY ----
        buy_result = RuleEngine._evaluate_buy(factors, indicators, resolved, position, profile, instrument_type, market_data)
        if buy_result["can_buy"]:
            result.action = buy_result["action"]
            result.buy_signal = True
            result.sell_signal = False
            result.ai_signal = "BUY"
            result.reason = buy_result["reason"]
            result.decision_factors = buy_result["factors"]
            result.buy_conditions = buy_result["conditions"]
            result.signal_quality = buy_result["quality"]
            result.ai_confidence = buy_result["confidence"]
            result.ai_risk_level = factors.risk_level
            result.signal_score = buy_result["score"]
            result.suggested_position_size = RuleEngine._suggest_position_size(
                profile, position, indicators, resolved
            )
        else:
            result.action = "HOLD"
            result.reason = buy_result["reason"]
            result.decision_factors = buy_result["factors"]
            result.buy_conditions = buy_result["conditions"]
            result.signal_quality = "LOW_CONFIDENCE"
            result.ai_confidence = 0.4
            result.signal_score = max(20.0, min(45.0, buy_result.get("score", 35)))

        return result

    @staticmethod
    def _check_emergency_exits(resolved, position, indicators, profile) -> Optional[dict]:
        triggers = []

        # Stop loss (no market/trend gate)
        stop_price, _, stop_triggered = compute_stop_loss(position, indicators, resolved, profile)
        if stop_triggered:
            triggers.append({
                "type": "STOP_LOSS",
                "action": "SELL_ALL",
                "reason": f"止损触发: 当前价 {resolved.current_price:.3f} <= 止损价 {stop_price:.3f}"
            })

        # Max drawdown > 8%
        if position.has_position and position.profit_rate is not None and position.profit_rate <= -0.08:
            triggers.append({
                "type": "MAX_DRAWDOWN",
                "action": "SELL_ALL",
                "reason": f"最大回撤触发: 亏损 {abs(position.profit_rate)*100:.1f}%"
            })

        return triggers[0] if triggers else None

    @staticmethod
    def _evaluate_sell(factors, indicators, resolved, position, profile) -> dict:
        triggers = []
        factors_list = []

        # a. Trend breakdown: price < MA20 for 3+ consecutive days
        if indicators.ma20 and resolved.current_price < indicators.ma20:
            below_days = count_ma_below_days(resolved.closes, 20, 10)
            if below_days >= 3:
                triggers.append(("TREND_BREAK", "SELL_ALL",
                                f"价格连续 {below_days} 天低于 MA20({indicators.ma20:.3f})"))
                factors_list.append(f"趋势破位: 连续 {below_days} 天低于 MA20")

        # b. Death cross: MA5 < MA20
        if indicators.ma5 and indicators.ma20 and indicators.ma5 < indicators.ma20:
            # Only if this is a recent cross (MA5 was >= MA20 recently)
            triggers.append(("DEATH_CROSS", "SELL_ALL",
                            f"MA5({indicators.ma5:.3f}) 下穿 MA20({indicators.ma20:.3f})"))
            factors_list.append(f"死叉: MA5({indicators.ma5:.3f}) < MA20({indicators.ma20:.3f})")

        # c. Overheat blow-off: RSI > 80 + declining volume
        if indicators.rsi is not None and indicators.rsi > 80 and indicators.volume_ratio is not None and indicators.volume_ratio < 0.8:
            triggers.append(("OVERHEAT_BLOWOFF", "SELL_PARTIAL",
                            f"RSI {indicators.rsi:.1f} > 80 且缩量，可能冲顶"))
            factors_list.append(f"过热放空: RSI {indicators.rsi:.1f}, 量比 {indicators.volume_ratio:.2f}")

        # d. Distribution: high-volume down pattern
        if factors.volume == "DISTRIBUTION":
            triggers.append(("DISTRIBUTION", "SELL_PARTIAL",
                            "放量下跌，可能有主力出货"))
            factors_list.append("放量下跌出货信号")

        # e. Take profit + weakening momentum
        if position.has_position and position.profit_rate is not None:
            take_profit = profile.get("take_profit", 0.08)
            if position.profit_rate >= take_profit and factors.momentum != "BULLISH":
                triggers.append(("TAKE_PROFIT", "SELL_PARTIAL",
                                f"止盈 {position.profit_rate*100:.1f}% 达标且动量衰减"))
                factors_list.append(f"止盈: 收益 {position.profit_rate*100:.1f}%, 动量 {factors.momentum}")

        # f. RSI overheat (for partial sell, shared by ETF/STOCK)
        if position.has_position and indicators.rsi is not None and indicators.rsi > 80 and indicators.consecutive_up_days >= 3:
            triggers.append(("RSI_OVERHEAT", "SELL_PARTIAL",
                            f"RSI {indicators.rsi:.1f} 过热 + 连涨 {indicators.consecutive_up_days}天"))
            factors_list.append(f"RSI 过热: {indicators.rsi:.1f}, 连涨 {indicators.consecutive_up_days} 天")

        if not triggers:
            return {"has_signal": False}

        # Determine dominant action from triggers
        if any(t[1] == "SELL_ALL" for t in triggers):
            action = "SELL_ALL"
            ai_signal = "SELL"
        else:
            action = "SELL_PARTIAL"
            ai_signal = "REDUCE"

        primary_reason = triggers[0][2]
        quality = "HIGH_CONFIDENCE" if len(triggers) >= 2 else "NORMAL"
        confidence = min(0.95, 0.7 + len(triggers) * 0.1)

        return {
            "has_signal": True,
            "action": action,
            "ai_signal": ai_signal,
            "reason": primary_reason,
            "factors": factors_list,
            "triggers": triggers,
            "quality": quality,
            "confidence": confidence,
        }

    @staticmethod
    def _evaluate_buy(factors, indicators, resolved, position, profile, instrument_type, market_data) -> dict:
        """Evaluate buy conditions. ALL must be met."""
        conditions = []
        factors_list = []

        # Condition 1: Trend — at minimum MA5 > MA20 and price above MA20
        trend_ok = False
        if indicators.ma5 and indicators.ma10 and indicators.ma20:
            if indicators.ma5 > indicators.ma10 > indicators.ma20:
                trend_ok = True
            elif indicators.ma5 > indicators.ma20 and resolved.current_price > indicators.ma20:
                trend_ok = True
        if trend_ok:
            conditions.append(("TREND", True, f"多头排列: MA5>{'>' if indicators.ma5 and indicators.ma10 and indicators.ma5 > indicators.ma10 else ''}MA10>{'>' if indicators.ma10 and indicators.ma20 and indicators.ma10 > indicators.ma20 else ''}MA20"))
            factors_list.append(f"趋势确认: {factors.trend_level}")
        else:
            msg = f"趋势不足: {factors.trend_level}" if factors.trend != "UP" else "趋势接近但未确认多头排列"
            conditions.append(("TREND", False, msg))

        # Condition 2: Momentum — RSI 35-70 OR MACD bullish
        rsi_ok = indicators.rsi is not None and 35 <= indicators.rsi <= 70
        macd_ok = (
            indicators.macd_line is not None
            and indicators.macd_signal_line is not None
            and indicators.macd_line > indicators.macd_signal_line
            and indicators.macd_histogram is not None
            and indicators.macd_histogram > 0
        )
        momentum_ok = rsi_ok or macd_ok
        if momentum_ok:
            parts = []
            if rsi_ok:
                parts.append(f"RSI {indicators.rsi:.1f}")
            if macd_ok:
                parts.append("MACD 多头")
            conditions.append(("MOMENTUM", True, ", ".join(parts)))
            factors_list.append(f"动量确认: {', '.join(parts)}")
        else:
            msg = f"RSI {indicators.rsi:.1f} (需35-70)" if indicators.rsi is not None else "RSI 数据不足"
            conditions.append(("MOMENTUM", False, msg))

        # Condition 3: Volume — no distribution
        volume_ok = factors.volume not in ("DISTRIBUTION",)
        if volume_ok:
            conditions.append(("VOLUME", True, f"量能正常 ({factors.volume})"))
            factors_list.append(f"量能: {factors.volume}")
        else:
            conditions.append(("VOLUME", False, f"放量下跌风险 ({factors.volume})"))

        # Condition 4: Market — not BLOCK
        market_ok = factors.market_filter != "BLOCK"
        if market_ok:
            conditions.append(("MARKET", True, f"市场过滤: {factors.market_filter}"))
            factors_list.append(f"市场: {factors.market_filter}")
        else:
            conditions.append(("MARKET", False, "市场阻断: 沪深300弱势"))

        # Condition 5: Position zone — rise from low 8%-25%
        rise = position.rise_from_low_pct
        if 8 <= rise <= 25:
            position_ok = True
            msg = f"距低点 {rise:.1f}% (理想区间 8-25%)"
        elif rise < 8:
            position_ok = False
            msg = f"距低点仅 {rise:.1f}% (太早，需确认反弹)"
        else:
            position_ok = True  # > 25% is high but acceptable with strong trend
            msg = f"距低点 {rise:.1f}% (高位，需强趋势配合)"
        conditions.append(("POSITION", position_ok, msg))
        factors_list.append(msg)

        # Condition 6: Cooldown
        cooldown_ok = position.cooldown_remaining <= 0
        if cooldown_ok:
            conditions.append(("COOLDOWN", True, "无冷却期"))
        else:
            conditions.append(("COOLDOWN", False, f"冷却期剩余 {position.cooldown_remaining} 天"))

        met_count = sum(1 for _, ok, _ in conditions if ok)
        total = len(conditions)
        all_met = met_count == total

        if all_met and factors.trend == "UP" and factors.momentum == "BULLISH":
            quality = "HIGH_CONFIDENCE"
            confidence = 0.85
        elif all_met:
            quality = "NORMAL"
            confidence = 0.75
        elif met_count >= total - 1:
            quality = "LOW_CONFIDENCE"
            confidence = 0.55
        else:
            return {"can_buy": False, "reason": f"买入条件不满足 ({met_count}/{total})", "conditions": conditions, "factors": factors_list, "score": met_count * 15, "quality": "LOW_CONFIDENCE", "confidence": max(0.2, met_count / total)}

        # Determine buy action
        buy_ratio = profile.get("buy_ratio", 0.3)
        if market_data.get("market_filter") == "CAUTION":
            buy_ratio *= 0.7
        if factors.volatility in ("HIGH", "VERY_HIGH"):
            buy_ratio *= 0.7

        action = f"BUY_{int(buy_ratio * 100)}"
        reason = f"买入信号: {met_count}/{total} 条件满足 (质量: {quality})"
        score = 50.0 + met_count * 8 - (1 if market_data.get("market_filter") == "CAUTION" else 0) * 10

        return {
            "can_buy": True,
            "action": action,
            "reason": reason,
            "conditions": conditions,
            "factors": factors_list,
            "score": min(100.0, score),
            "quality": quality,
            "confidence": confidence,
        }

    @staticmethod
    def _evaluate_add(factors, indicators, resolved, position, profile, instrument_type, market_data) -> dict:
        """Evaluate whether to add to existing position."""
        if position.cooldown_remaining > 0:
            return {"can_add": False, "reason": f"冷却期剩余 {position.cooldown_remaining} 天"}
        if factors.market_filter == "BLOCK":
            return {"can_add": False, "reason": "市场阻断，不加仓"}
        if position.profit_rate is None:
            return {"can_add": False, "reason": "无盈亏数据"}
        if position.profit_rate < profile.get("add_profit_threshold", 0.02):
            return {"can_add": False, "reason": f"盈利 {position.profit_rate*100:.1f}% 未达加仓阈值"}

        can_add_position = position.position_ratio < profile.get("max_position_ratio", 0.8)
        if not can_add_position:
            return {"can_add": False, "reason": "仓位已达上限"}

        # Different ADD thresholds by instrument type
        if instrument_type == "STOCK":
            trend_min = 72
        else:
            trend_min = 65

        trend_strong = factors.trend_strength >= trend_min
        momentum_ok = factors.momentum == "BULLISH"
        volume_ok = factors.volume not in ("DISTRIBUTION",)

        met = sum([trend_strong, momentum_ok, volume_ok])

        if met >= 2 and factors.trend == "UP":
            add_ratio = profile.get("add_ratio", 0.4)
            if market_data.get("market_filter") == "CAUTION":
                add_ratio *= 0.7
            action = f"ADD_{int(add_ratio * 100)}"
            quality = "HIGH_CONFIDENCE" if met == 3 else "NORMAL"
            return {
                "can_add": True,
                "action": action,
                "reason": f"加仓: {met}/3 条件满足, 盈利 {position.profit_rate*100:.1f}%",
                "factors": [
                    f"趋势强度: {factors.trend_strength:.0f} (需≥{trend_min})",
                    f"动量: {factors.momentum}",
                    f"量能: {factors.volume}",
                ],
                "quality": quality,
                "confidence": 0.65 + met * 0.1,
                "score": 60.0 + met * 12,
            }

        return {"can_add": False, "reason": f"加仓条件不满足 ({met}/3)", "factors": [], "score": 40.0}

    @staticmethod
    def _suggest_position_size(profile, position, indicators, resolved) -> Optional[float]:
        """Suggest position size in currency units, volatility-adjusted."""
        if not resolved.current_price or resolved.current_price <= 0:
            return None

        atr_pct = indicators.atr_pct
        if atr_pct is None:
            vol_factor = 1.0
        elif atr_pct < 1:
            vol_factor = 1.0
        elif atr_pct < 3:
            vol_factor = 1.0
        elif atr_pct < 5:
            vol_factor = 0.7
        else:
            vol_factor = 0.5

        max_capital = position.initial_capital * profile.get("max_position_ratio", 0.8)
        return round(max_capital * vol_factor, 2)


# =============================================================================
# Section 7: Pipeline Coordinator
# =============================================================================

class SignalEngine:
    """Main entry point — coordinates all stages and returns a flat dict."""

    PROFILES = {
        "CONSERVATIVE": {
            "max_position_ratio": 0.5, "stop_loss": -0.04, "take_profit": 0.06,
            "buy_ratio": 0.2, "add_ratio": 0.2, "volume_threshold": 2.0,
            "breakout_confirm_days": 2, "cooldown_days": 3,
            "add_profit_threshold": 0.03, "sell_partial_profit": 0.04,
        },
        "MODERATE": {
            "max_position_ratio": 0.7, "stop_loss": -0.05, "take_profit": 0.08,
            "buy_ratio": 0.3, "add_ratio": 0.4, "volume_threshold": 1.5,
            "breakout_confirm_days": 1, "cooldown_days": 2,
            "add_profit_threshold": 0.02, "sell_partial_profit": 0.05,
        },
        "AGGRESSIVE": {
            "max_position_ratio": 0.8, "stop_loss": -0.06, "take_profit": 0.10,
            "buy_ratio": 0.4, "add_ratio": 0.5, "volume_threshold": 1.2,
            "breakout_confirm_days": 1, "cooldown_days": 1,
            "add_profit_threshold": 0.02, "sell_partial_profit": 0.06,
        },
    }

    # Compatibility mapping: old template names → new profile names
    TEMPLATE_MAP = {"CORE": "MODERATE", "THEME": "CONSERVATIVE"}
    DEFAULT_PROFILE = "MODERATE"

    @staticmethod
    def calculate(
        symbol: str,
        market: str = "CN",
        cost: float = None,
        quantity: int = None,
        initial_capital: float = 2000.0,
        last_stop_loss_date=None,
        template_name: str = None,
        instrument_type: str = "ETF",
    ) -> dict:
        """
        Main signal calculation pipeline.
        Returns a flat dict backward-compatible with EtfSignalWithMeta.
        """
        # Resolve profile
        profile_name = SignalEngine.TEMPLATE_MAP.get(template_name, template_name or SignalEngine.DEFAULT_PROFILE)
        if profile_name not in SignalEngine.PROFILES:
            profile_name = SignalEngine.DEFAULT_PROFILE
        profile = SignalEngine.PROFILES[profile_name]

        # Stage 1: Fetch data
        try:
            raw = StockService.get_price_history_with_volume(symbol, market, days=35)
        except Exception as e:
            return {"error": f"获取行情数据失败: {e}"}
        if len(raw) < 25:
            return {"error": "数据不足（需要至少 25 个交易日）"}

        # Real-time price
        try:
            info = StockService.get_stock_info(symbol, market)
            current_price = info.get("current_price", raw[-1].get("close", raw[-1]["price"])) or raw[-1].get("close", raw[-1]["price"])
            change_pct = info.get("price_change_percent")
        except Exception:
            current_price = raw[-1].get("close", raw[-1]["price"])
            change_pct = None

        # Stage 1b: Resolve kline ambiguity
        resolved = resolve_kline_ambiguity(raw, current_price)

        # Stage 1c: Weekly trend
        weekly = compute_weekly_trend(symbol, market)

        # Stage 2: Calculate indicators
        closes_all = resolved.closes
        changed_closes_all = [d.get("close", d["price"]) for d in raw]  # original for change_pct fallback

        ind = IndicatorSet()
        ind.ma5 = _ma(closes_all, 5)
        ind.ma10 = _ma(closes_all, 10)
        ind.ma20 = _ma(closes_all, 20)
        ind.rsi = rsi_wilder(closes_all)
        ind.macd_line, ind.macd_signal_line, ind.macd_histogram = macd_full(closes_all)
        ind.bollinger_upper, ind.bollinger_lower, ind.bollinger_mid, ind.bollinger_bandwidth, ind.bollinger_position = bollinger_bands(closes_all)
        ind.atr = atr(resolved.bars)
        ind.atr_pct = (ind.atr / resolved.current_price * 100) if ind.atr and resolved.current_price else None
        ind.volume_ratio = compute_volume_ratio(resolved.volumes, resolved.is_trading_day)
        ind.weekly_trend = weekly
        ind.consecutive_up_days = count_consecutive_up(resolved)

        # Stage 3: Factor evaluations
        market_data = get_market_filter()
        trend_info = evaluate_trend(ind, resolved)

        factors = FactorResult()
        factors.trend = trend_info["trend"]
        factors.trend_strength = trend_info["trend_strength"]
        factors.trend_level = trend_info["trend_level"]
        factors.momentum = evaluate_momentum(ind, resolved)
        factors.volume = evaluate_volume(ind, resolved)

        # Volatility assessment
        if ind.bollinger_bandwidth is not None:
            if ind.bollinger_bandwidth < 0.05:
                factors.volatility = "LOW"
            elif ind.bollinger_bandwidth < 0.15:
                factors.volatility = "NORMAL"
            elif ind.bollinger_bandwidth < 0.25:
                factors.volatility = "HIGH"
            else:
                factors.volatility = "VERY_HIGH"
        if ind.atr_pct is not None and ind.atr_pct > 5:
            factors.volatility = "VERY_HIGH"

        factors.market_filter = market_data["market_filter"]

        # Risk assessment
        risk_score = 20.0
        rsi = ind.rsi
        if rsi is not None and rsi > 80:
            risk_score += 20
        if factors.volume == "DISTRIBUTION":
            risk_score += 25
        if ind.consecutive_up_days >= 4:
            risk_score += 15
        if resolved.current_price < (ind.ma20 or 0):
            risk_score += 15
        if market_data["market_filter"] == "BLOCK":
            risk_score += 20
        elif market_data["market_filter"] == "CAUTION":
            risk_score += 8
        if factors.volatility in ("HIGH",):
            risk_score += 10
        elif factors.volatility in ("VERY_HIGH",):
            risk_score += 18
        risk_score = min(100.0, risk_score)
        if risk_score >= 70:
            factors.risk_level = "HIGH"
        elif risk_score >= 45:
            factors.risk_level = "MEDIUM"
        else:
            factors.risk_level = "LOW"
        factors.details["risk_score"] = risk_score

        # Cooldown
        cooldown_days = profile.get("cooldown_days", 2)
        cooldown_remaining = 0
        if last_stop_loss_date:
            days_since = (date.today() - last_stop_loss_date).days
            cooldown_remaining = max(0, cooldown_days - days_since)

        # Position
        position = evaluate_position(
            resolved, cost, quantity, initial_capital,
            profile.get("max_position_ratio", 0.8),
            cooldown_remaining, last_stop_loss_date, cooldown_days,
            consecutive_up_days=ind.consecutive_up_days,
        )

        # Stage 4: Decision
        result = RuleEngine.decide(factors, ind, resolved, position, profile, instrument_type, market_data)

        # Change pct fallback
        if change_pct is None and len(changed_closes_all) >= 2:
            change_pct = (resolved.current_price - resolved.yesterday_close) / resolved.yesterday_close * 100

        # Breakout details
        breakout_info = _compute_breakout(resolved, ind)
        sentiment = "OVERHEAT" if ((ind.rsi is not None and ind.rsi > 70) or (abs(change_pct or 0) > 3) or ind.consecutive_up_days >= 4) else "NORMAL"

        rsi_signal_str = "NEUTRAL"
        if ind.rsi is not None:
            if ind.rsi < 35:
                rsi_signal_str = "OVERSOLD"
            elif ind.rsi > 70:
                rsi_signal_str = "OVERBOUGHT"

        # Build backward-compatible flat dict
        ma20_below = count_ma_below_days(closes_all, 20, 10)

        profit_loss = None
        profit_loss_pct = None
        if position.has_position:
            profit_loss = round((resolved.current_price - float(cost)) * quantity, 2)
            profit_loss_pct = round((resolved.current_price - float(cost)) / float(cost) * 100, 2)

        # Composite signal_score for backward compat
        if result.buy_signal:
            backward_score = result.signal_score
        elif result.sell_signal:
            backward_score = result.signal_score
        else:
            backward_score = 50.0
        # Adjust for market
        if market_data["market_filter"] == "CAUTION":
            backward_score -= 5
        elif market_data["market_filter"] == "BLOCK":
            backward_score -= 15
        backward_score = max(0, min(100, backward_score))

        d = {
            # Core trend fields
            "trend": factors.trend,
            "trend_strength": factors.trend_strength,
            "trend_level": factors.trend_level,
            "pullback": trend_info.get("pullback", False),
            "sentiment": sentiment,
            "volume_signal": factors.volume,

            # Breakout
            "breakout": breakout_info["breakout"],
            "breakout_confirm": breakout_info["breakout_confirm"],
            "breakout_strength": breakout_info["breakout_strength"],
            "breakout_quality": breakout_info["breakout_quality"],

            # Position
            "is_low_position": position.is_low_position,
            "is_high_position": position.is_high_position,
            "rise_from_low_pct": round(position.rise_from_low_pct, 2),

            # Action / signals
            "action": result.action,
            "reason": result.reason,
            "buy_signal": result.buy_signal,
            "sell_signal": result.sell_signal,

            # Volume
            "volume_ratio": ind.volume_ratio,
            "consecutive_up_days": ind.consecutive_up_days,
            "ma20_below_days": ma20_below,
            "cooldown_days": position.cooldown_remaining,

            # MAs
            "ma5": round(ind.ma5, 3) if ind.ma5 else None,
            "ma10": round(ind.ma10, 3) if ind.ma10 else None,
            "ma20": round(ind.ma20, 3) if ind.ma20 else None,
            "current_price": round(resolved.current_price, 3),
            "change_pct": round(change_pct or 0, 2),

            # RSI
            "rsi": round(ind.rsi, 2) if ind.rsi is not None else None,
            "rsi_signal": rsi_signal_str,

            # ATR / Stop
            "atr": round(ind.atr, 4) if ind.atr else None,
            "atr_pct": round(ind.atr_pct, 2) if ind.atr_pct is not None else None,
            "dynamic_stop_price": round(result.dynamic_stop_price, 3) if result.dynamic_stop_price else None,
            "dynamic_stop_loss_pct": round(result.dynamic_stop_loss_pct, 2) if result.dynamic_stop_loss_pct is not None else None,
            "stop_loss_triggered": result.stop_loss_triggered,

            # === NEW: MACD ===
            "macd": round(ind.macd_line, 4) if ind.macd_line else None,
            "macd_signal": round(ind.macd_signal_line, 4) if ind.macd_signal_line else None,
            "macd_histogram": round(ind.macd_histogram, 4) if ind.macd_histogram is not None else None,

            # === NEW: Bollinger Bands ===
            "bollinger_upper": round(ind.bollinger_upper, 3) if ind.bollinger_upper else None,
            "bollinger_lower": round(ind.bollinger_lower, 3) if ind.bollinger_lower else None,
            "bollinger_mid": round(ind.bollinger_mid, 3) if ind.bollinger_mid else None,
            "bollinger_bandwidth": round(ind.bollinger_bandwidth, 4) if ind.bollinger_bandwidth is not None else None,
            "bollinger_position": round(ind.bollinger_position, 3) if ind.bollinger_position is not None else None,

            # === NEW: Weekly trend ===
            "weekly_trend": ind.weekly_trend,

            # === NEW: Signal quality ===
            "signal_quality": result.signal_quality,

            # === NEW: Suggested position size ===
            "suggested_position_size": result.suggested_position_size,

            # === NEW: Trading day flag ===
            "is_trading_day": resolved.is_trading_day,

            # === FIXED: Cumulative return ===
            "cumulative_return": round(position.cumulative_return, 2) if position.cumulative_return is not None else None,

            # Breakout details
            "prev_high": round(breakout_info["prev_high"], 3) if breakout_info.get("prev_high") else None,
            "prev_low": round(breakout_info["prev_low"], 3) if breakout_info.get("prev_low") else None,

            # Position details
            "position_size": quantity,
            "avg_cost": round(float(cost), 3) if cost else None,
            "profit_rate": round(position.profit_rate, 4) if position.profit_rate is not None else None,
            "profit_loss": profit_loss,
            "profit_loss_pct": profit_loss_pct,
            "position_ratio": round(position.position_ratio, 4),
            "max_position_ratio": profile.get("max_position_ratio", 0.8),
            "can_add_position": position.position_ratio < profile.get("max_position_ratio", 0.8),

            # Market
            "market_symbol": market_data["market_symbol"],
            "market_trend": market_data["market_trend"],
            "market_filter": market_data["market_filter"],
            "market_score": market_data["market_score"],
            "market_reason": market_data["market_reason"],
            "market_rsi": market_data["market_rsi"],
            "market_trend_strength": market_data["market_trend_strength"],

            # AI fields
            "ai_summary": f"{symbol.upper()} {result.ai_signal}: 质量={result.signal_quality}, 风险={result.ai_risk_level}, {result.reason}",
            "ai_signal": result.ai_signal,
            "ai_confidence": result.ai_confidence,
            "ai_risk_level": result.ai_risk_level,
            "decision_factors": result.decision_factors,

            # Scoring (backward compat)
            "signal_score": round(backward_score, 1),
            "buy_score": round(max(0, min(100, 50.0 + sum(1 for _, ok, _ in result.buy_conditions if ok) * 8)), 1) if result.buy_conditions else 50.0,
            "sell_score": round(min(100.0, risk_score), 1),
            "risk_score": round(risk_score, 1),
            "trend_score": factors.trend_strength,
            "volume_score": 78.0 if factors.volume == "ACCUMULATION" else 25.0 if factors.volume == "DISTRIBUTION" else 50.0,
            "momentum_score": 75.0 if factors.momentum == "BULLISH" else 35.0 if factors.momentum == "BEARISH" else 50.0,
            "position_score": 70.0 if position.is_low_position else 30.0 if position.is_high_position else 50.0,
            "score_breakdown": {
                "trend_score": factors.trend_strength,
                "volume_score": 78.0 if factors.volume == "ACCUMULATION" else 25.0 if factors.volume == "DISTRIBUTION" else 50.0,
                "momentum_score": 75.0 if factors.momentum == "BULLISH" else 35.0 if factors.momentum == "BEARISH" else 50.0,
                "position_score": 70.0 if position.is_low_position else 30.0 if position.is_high_position else 50.0,
                "market_score": market_data["market_score"],
                "risk_score": risk_score,
            },
            "technical_snapshot": {
                "ma5": ind.ma5, "ma10": ind.ma10, "ma20": ind.ma20,
                "rsi": ind.rsi, "atr": ind.atr, "atr_pct": ind.atr_pct,
                "volume_ratio": ind.volume_ratio,
                "trend_strength": factors.trend_strength,
                "breakout_quality": breakout_info["breakout_quality"],
                "market_filter": market_data["market_filter"],
                "macd_histogram": ind.macd_histogram,
                "bollinger_position": ind.bollinger_position,
                "bollinger_bandwidth": ind.bollinger_bandwidth,
                "weekly_trend": ind.weekly_trend,
            },

            # Template
            "template_name": template_name or SignalEngine.DEFAULT_PROFILE,
            "params": profile,
            "instrument_type": instrument_type,
            "strategy_profile": "ETF_TREND" if instrument_type == "ETF" else "STOCK_BREAKOUT",
            "breakout_score": breakout_info.get("breakout_score", 50.0),
        }

        return d


def _compute_breakout(resolved: ResolvedData, ind: IndicatorSet) -> dict:
    """Compute breakout metrics for backward compatibility."""
    bars = resolved.bars
    if len(bars) < 3:
        return {"breakout": False, "breakout_confirm": False, "breakout_strength": 0.0,
                "breakout_quality": "NONE", "prev_high": None, "prev_low": None, "breakout_score": 50.0}

    prev = bars[-2]
    prev_high = prev.high
    prev_low = prev.low
    breakout = resolved.current_price > prev_high if prev_high else False
    breakout_strength = ((resolved.current_price - prev_high) / prev_high * 100) if breakout and prev_high else 0.0

    confirmed = True
    for offset in range(2, min(4, len(bars))):
        curr = bars[-offset]
        prior = bars[-offset - 1]
        close_val = curr.close
        prior_high = prior.high
        if close_val is None or prior_high is None or close_val <= prior_high:
            confirmed = False
            break

    vr = ind.volume_ratio or 0
    if breakout and confirmed and vr >= 1.5:
        quality = "VOLUME_CONFIRMED"
    elif breakout and confirmed:
        quality = "CONFIRMED"
    elif breakout:
        quality = "WEAK"
    else:
        quality = "NONE"

    breakout_score = {"VOLUME_CONFIRMED": 85.0, "CONFIRMED": 72.0, "WEAK": 55.0, "NONE": 50.0}.get(quality, 50.0)

    return {
        "breakout": breakout,
        "breakout_confirm": breakout and confirmed,
        "breakout_strength": round(breakout_strength, 2),
        "breakout_quality": quality,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "breakout_score": breakout_score,
    }
