"""做T监测：个股实时买卖点信号"""
import threading
import time
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import get_db
from app.models.models import EtfWatch
from app.services.etf_signal_service import EtfSignalService
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/ttrade", tags=["ttrade"])

# Intraday signal cache (per symbol, short TTL to avoid hammering EastMoney)
_intraday_cache = {}
_intraday_cache_ttl = 3  # seconds (shorter than frontend 5s refresh to avoid stale data)
_intraday_cache_lock = threading.Lock()


@router.get("/holdings")
def get_holdings(db: Session = Depends(get_db)):
    """返回持仓中（quantity > 0）的股票列表，用于做T选择"""
    items = db.query(EtfWatch).filter(
        EtfWatch.quantity > 0,
        EtfWatch.enabled == True,
    ).order_by(EtfWatch.symbol).all()
    return [
        {
            "symbol": i.symbol,
            "name": i.name or i.symbol,
            "market": i.market or "CN",
            "cost": float(i.cost) if i.cost else None,
            "quantity": i.quantity,
            "instrument_type": i.instrument_type or "ETF",
        }
        for i in items
    ]


@router.get("/signal/{symbol}")
def get_ttrade_signal(symbol: str, market: str = "CN", db: Session = Depends(get_db)):
    """
    获取单只股票的做T信号（实时计算）。
    如果有持仓数据（etf_watch 中 cost/quantity），会传入信号引擎以计算盈亏参考。
    """
    # Look up holdings for cost/quantity context
    watch = db.query(EtfWatch).filter(EtfWatch.symbol == symbol.upper()).first()
    cost = float(watch.cost) if watch and watch.cost else None
    quantity = watch.quantity if watch and watch.quantity else None

    try:
        result = EtfSignalService.calculate_etf_signals(
            symbol.upper(), market,
            cost=cost, quantity=quantity,
            initial_capital=2000.0,
            last_stop_loss_date=None,
            template_name="CORE",
            instrument_type=watch.instrument_type if watch else "STOCK",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"信号计算失败: {e}")

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # Resolve stock name
    name = symbol.upper()
    if watch and watch.name:
        name = watch.name
    else:
        try:
            info = StockService.get_stock_info(symbol, market)
            name = info.get("name") or name
        except Exception:
            pass

    # Determine summary recommendation
    action = result.get("action", "HOLD")
    if "BUY" in str(action).upper() and not str(action).upper().startswith("SELL"):
        recommendation = "buy"
        rec_label = "买点"
    elif "SELL" in str(action).upper():
        recommendation = "sell"
        rec_label = "卖点"
    else:
        recommendation = "hold"
        rec_label = "观望"

    return {
        "symbol": symbol.upper(),
        "name": name,
        "market": market,
        # 持仓信息
        "cost": cost,
        "quantity": quantity,
        # 核心信号
        "recommendation": recommendation,
        "recommendation_label": rec_label,
        "action": action,
        "action_detail": result.get("reason", ""),
        # 实时价格
        "current_price": result.get("current_price"),
        "daily_return": result.get("change_pct"),
        # 均线
        "ma5": result.get("ma5"),
        "ma10": result.get("ma10"),
        "ma20": result.get("ma20"),
        # 趋势
        "trend": result.get("trend"),
        "trend_strength": result.get("trend_strength"),
        "trend_level": result.get("trend_level"),
        # 技术指标
        "rsi": result.get("rsi"),
        "rsi_signal": result.get("rsi_signal"),
        "macd": result.get("macd"),
        "macd_signal": result.get("macd_signal"),
        "macd_histogram": result.get("macd_histogram"),
        "volume_ratio": result.get("volume_ratio"),
        "volume_signal": result.get("volume_signal"),
        # 布林带
        "bollinger_upper": result.get("bollinger_upper"),
        "bollinger_lower": result.get("bollinger_lower"),
        "bollinger_mid": result.get("bollinger_mid"),
        "bollinger_position": result.get("bollinger_position"),
        # 突破与回调
        "breakout": result.get("breakout"),
        "breakout_strength": result.get("breakout_strength"),
        "breakout_quality": result.get("breakout_quality"),
        "pullback": result.get("pullback"),
        # 风险
        "risk_score": result.get("risk_score"),
        "sentiment": result.get("sentiment"),
        "signal_quality": result.get("signal_quality"),
        # 评分
        "buy_score": result.get("buy_score"),
        "sell_score": result.get("sell_score"),
        "signal_score": result.get("signal_score"),
        # 做T参考位
        "support_level": result.get("bollinger_lower"),
        "resistance_level": result.get("bollinger_upper"),
        "atr": result.get("atr"),
        "atr_pct": result.get("atr_pct"),
        "suggested_position_size": result.get("suggested_position_size"),
        # 周线
        "weekly_trend": result.get("weekly_trend"),
        "is_trading_day": result.get("is_trading_day"),
    }


@router.get("/intraday/{symbol}")
def get_intraday_signal(symbol: str, market: str = "CN", req_date: Optional[str] = None, db: Session = Depends(get_db)):
    """
    获取日内做T信号（基于分钟级分时数据）。
    返回日线趋势 + 日内信号 + 指标 + 分钟K线数据。

    Query params:
        req_date: optional date in YYYY-MM-DD format for historical review.
                  When provided, returns signal_markers for chart annotation.
    """
    from app.services.intraday_engine import (
        resolve_intraday_data, compute_intraday_indicators,
        evaluate_intraday_factors, IntradayDecisionEngine,
        replay_intraday_signals,
    )

    # Parse target date
    target_date = None
    if req_date:
        try:
            target_date = datetime.strptime(req_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="date格式须为 YYYY-MM-DD")

    # Short cache for today's data to avoid hammering EastMoney every 5s
    if target_date is None:
        cache_key = f"{symbol.upper()}:{market}"
        with _intraday_cache_lock:
            entry = _intraday_cache.get(cache_key)
            if entry and (time.time() - entry["ts"]) < _intraday_cache_ttl:
                return entry["data"]

    # Look up holdings
    watch = db.query(EtfWatch).filter(EtfWatch.symbol == symbol.upper()).first()
    cost = float(watch.cost) if watch and watch.cost else None
    quantity = watch.quantity if watch and watch.quantity else None
    has_position = quantity is not None and quantity > 0

    # Step 1: Get daily trend context
    daily_trend = "NEUTRAL"
    daily_trend_strength = 50.0
    daily_action = "HOLD"
    prev_close = None

    try:
        daily_result = EtfSignalService.calculate_etf_signals(
            symbol.upper(), market,
            cost=cost, quantity=quantity,
            initial_capital=2000.0,
            last_stop_loss_date=None,
            template_name="CORE",
            instrument_type=watch.instrument_type if watch else "STOCK",
        )
        if "error" not in daily_result:
            daily_trend = daily_result.get("trend", "NEUTRAL")
            daily_trend_strength = daily_result.get("trend_strength", 50.0)
            daily_action = daily_result.get("action", "HOLD")
            # Derive prev_close from yesterday_close
            prev_close = daily_result.get("current_price", None)
            if prev_close and daily_result.get("change_pct") is not None:
                # Approximate prev_close from current + change_pct
                change_pct = daily_result["change_pct"]
                if change_pct != 0:
                    prev_close = daily_result["current_price"] / (1 + change_pct / 100)
    except Exception:
        pass

    # Step 2: Get real-time price (for today) or use bar data (for historical)
    name = symbol.upper()
    current_price = None
    try:
        info = StockService.get_stock_info(symbol, market)
        current_price = info.get("current_price")
        name = info.get("name") or name
    except Exception:
        pass

    # Step 3: Fetch intraday 5-min klines
    beg_param = target_date.strftime("%Y%m%d") if target_date else None
    try:
        raw_bars = StockService.get_intraday_klines(symbol, market, klt=5, limit=100, beg=beg_param)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分钟K线失败: {e}")

    # For historical dates: derive price from kline data (override real-time)
    if target_date and raw_bars:
        current_price = float(raw_bars[-1]["close"])
        if prev_close is None:
            prev_close = float(raw_bars[0].get("open", current_price))

    if current_price is None:
        raise HTTPException(status_code=500, detail="无法获取实时价格")

    if prev_close is None:
        prev_close = current_price

    # Step 4: Resolve intraday data
    resolved = resolve_intraday_data(raw_bars, current_price, prev_close, target_date=target_date)

    # Step 5: Compute indicators (opening range = first 6 bars for 30 min in 5-min kline)
    ind = compute_intraday_indicators(resolved, opening_range_bars=6)

    # Step 6: Evaluate factors
    factors = evaluate_intraday_factors(ind, resolved)

    # Step 7: Decision
    signal = IntradayDecisionEngine.decide(
        daily_trend, daily_trend_strength, daily_action,
        factors, ind, resolved, has_position,
    )

    # Step 7b: Replay for historical dates to find buy/sell markers
    signal_markers = []
    if target_date and resolved.bars_today:
        signal_markers = replay_intraday_signals(
            bars=resolved.bars_today,
            prev_close=prev_close,
            target_date=target_date,
            daily_trend=daily_trend,
            daily_trend_strength=daily_trend_strength,
            daily_action=daily_action,
            has_position=has_position,
        )

    # Step 8: Build response
    bars_for_client = [
        {
            "time": b.timestamp.strftime("%H:%M"),
            "open": round(b.open, 4 if b.open < 1 else 3),
            "high": round(b.high, 4 if b.high < 1 else 3),
            "low": round(b.low, 4 if b.low < 1 else 3),
            "close": round(b.close, 4 if b.close < 1 else 3),
            "price": round(b.close, 4 if b.close < 1 else 3),
            "volume": int(b.volume),
        }
        for b in resolved.bars_today[-240:]  # Full day's bars
    ]

    # Get name from watch
    if watch and watch.name:
        name = watch.name

    result = {
        "symbol": symbol.upper(),
        "name": name,
        "market": market,
        "cost": cost,
        "quantity": quantity,
        "has_position": has_position,
        "daily_trend": daily_trend,
        "daily_trend_strength": daily_trend_strength,
        "daily_action": daily_action,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "is_market_open": resolved.is_market_open,
        "bar_count": resolved.bar_count,
        "prev_close": round(prev_close, 3) if prev_close else None,
        "current_price": round(current_price, 3),
        "intraday": {
            "action": signal.action,
            "signal_type": {
                "BREAKOUT": "突破",
                "VWAP_REVERSAL": "VWAP回归",
                "RSI_EXTREME": "RSI极端",
                "MICRO_TREND": "分时趋势",
                "VOLUME_SURGE": "放量",
            }.get(signal.signal_type, signal.signal_type),
            "confidence": round(signal.confidence, 2),
            "quality": {
                "HIGH_CONFIDENCE": "高置信",
                "NORMAL": "普通",
                "LOW_CONFIDENCE": "低置信",
            }.get(signal.quality, signal.quality),
            "reason": signal.reason,
            "support_level": round(signal.support_level, 4) if signal.support_level else None,
            "resistance_level": round(signal.resistance_level, 4) if signal.resistance_level else None,
            "stop_loss": round(signal.stop_loss, 4) if signal.stop_loss else None,
            "vwap": round(signal.vwap, 4) if signal.vwap else None,
            "price_vs_vwap_pct": round(signal.price_vs_vwap_pct, 2) if signal.price_vs_vwap_pct is not None else None,
            "intraday_trend": signal.intraday_trend,
        },
        "indicators": {
            "vwap": round(ind.vwap, 4) if ind.vwap else None,
            "price_vs_vwap_pct": round(ind.price_vs_vwap_pct, 2) if ind.price_vs_vwap_pct is not None else None,
            "intra_ma5": round(ind.intra_ma5, 4) if ind.intra_ma5 else None,
            "intra_ma10": round(ind.intra_ma10, 4) if ind.intra_ma10 else None,
            "intra_ma20": round(ind.intra_ma20, 4) if ind.intra_ma20 else None,
            "intra_ma60": round(ind.intra_ma60, 4) if ind.intra_ma60 else None,
            "intra_rsi_14": round(ind.intra_rsi_14, 2) if ind.intra_rsi_14 is not None else None,
            "intra_rsi_7": round(ind.intra_rsi_7, 2) if ind.intra_rsi_7 is not None else None,
            "volume_ratio": round(ind.volume_ratio, 2) if ind.volume_ratio is not None else None,
            "opening_range_high": round(ind.opening_range_high, 4) if ind.opening_range_high else None,
            "opening_range_low": round(ind.opening_range_low, 4) if ind.opening_range_low else None,
            "session_return_pct": round(ind.session_return_pct, 2) if ind.session_return_pct is not None else None,
            "range_pct": round(ind.range_pct, 2) if ind.range_pct is not None else None,
            "cumulative_volume": int(ind.cumulative_volume),
            "consecutive_up_bars": ind.consecutive_up_bars,
            "consecutive_down_bars": ind.consecutive_down_bars,
        },
        "factors": {
            "vwap_signal": factors.vwap_signal,
            "range_signal": factors.range_signal,
            "momentum_signal": factors.momentum_signal,
            "volume_signal": factors.volume_signal,
            "rsi_signal": factors.rsi_signal,
            "micro_trend": factors.micro_trend,
        },
        "bars": bars_for_client,
        "signal_markers": signal_markers,
    }

    # Cache today's data briefly to avoid hammering EastMoney
    if target_date is None:
        with _intraday_cache_lock:
            _intraday_cache[cache_key] = {"data": result, "ts": time.time()}

    return result
