from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import threading

from app.models import get_db
from app.models.models import EtfWatch, EtfSignal
from app.schemas.schemas import (
    EtfWatchCreate, EtfWatchResponse,
    EtfSignalResponse, EtfSignalWithMeta, MessageResponse
)
from app.services.etf_signal_service import EtfSignalService
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

# 并行线程池，最大同时计算 15 个 ETF 信号
_etf_executor = ThreadPoolExecutor(max_workers=15)

# ETF signals cache
_cache = {"data": None, "timestamp": 0}
_CACHE_TTL = 20  # seconds
_cache_lock = threading.Lock()
_computing = False

_EXTENDED_SIGNAL_FIELDS = [
    "signal_score", "buy_score", "sell_score", "risk_score",
    "trend_score", "volume_score", "momentum_score", "position_score", "score_breakdown",
    "trend_strength", "trend_level", "rsi", "rsi_signal", "atr", "atr_pct",
    "dynamic_stop_price", "dynamic_stop_loss_pct", "stop_loss_triggered",
    "market_symbol", "market_trend", "market_filter", "market_score", "market_reason",
    "market_rsi", "market_trend_strength", "breakout_strength", "breakout_quality",
    "position_ratio", "max_position_ratio", "can_add_position",
    "ai_summary", "ai_signal", "ai_confidence", "ai_risk_level",
    "decision_factors", "technical_snapshot",
    "instrument_type", "strategy_profile", "breakout_score",
]


def _extended_signal_fields(result: dict) -> dict:
    return {key: result.get(key) for key in _EXTENDED_SIGNAL_FIELDS}


# ----- Watch list -----

@router.get("/watch", response_model=List[EtfWatchResponse])
def list_etf_watch(db: Session = Depends(get_db)):
    """获取所有关注的 ETF 列表"""
    return db.query(EtfWatch).order_by(EtfWatch.created_at.desc()).all()


@router.post("/watch", response_model=EtfWatchResponse)
def add_etf_watch(data: EtfWatchCreate, db: Session = Depends(get_db)):
    """添加 ETF 到关注列表"""
    existing = db.query(EtfWatch).filter(EtfWatch.symbol == data.symbol.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail="ETF 已在关注列表中")

    name = data.name
    try:
        info = StockService.get_stock_info(data.symbol, data.market or "CN")
        name = info.get("name") or name
    except Exception:
        pass

    etf = EtfWatch(
        symbol=data.symbol.upper(),
        name=name or data.symbol,
        market=data.market or "CN",
        enabled=data.enabled if data.enabled is not None else True,
        initial_capital=data.initial_capital or 2000.0,
        cost=data.cost,
        quantity=data.quantity,
        instrument_type=data.instrument_type or "ETF",
    )
    db.add(etf)
    db.commit()
    db.refresh(etf)
    return etf


@router.patch("/watch/{symbol}", response_model=EtfWatchResponse)
def update_etf_holdings(symbol: str, data: EtfWatchCreate, db: Session = Depends(get_db)):
    """更新 ETF 持仓成本和股数"""
    etf = db.query(EtfWatch).filter(EtfWatch.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF 未找到")
    if data.cost is not None:
        etf.cost = data.cost
    if data.quantity is not None:
        etf.quantity = data.quantity
    if data.template_name is not None:
        etf.template_name = data.template_name
    if data.instrument_type is not None:
        etf.instrument_type = data.instrument_type
    db.commit()
    db.refresh(etf)
    # Invalidate signals cache so next request gets fresh data
    from app.api.etf import _cache_lock, _cache
    with _cache_lock:
        _cache["data"] = None
        _cache["timestamp"] = 0
    return etf


@router.delete("/watch/{symbol}", response_model=MessageResponse)
def remove_etf_watch(symbol: str, db: Session = Depends(get_db)):
    """从关注列表移除 ETF"""
    etf = db.query(EtfWatch).filter(EtfWatch.symbol == symbol.upper()).first()
    if not etf:
        raise HTTPException(status_code=404, detail="ETF 未找到")
    db.delete(etf)
    db.commit()
    # Invalidate signals cache so next request gets fresh data
    from app.api.etf import _cache_lock, _cache
    with _cache_lock:
        _cache["data"] = None
        _cache["timestamp"] = 0
    return MessageResponse(message=f"ETF {symbol} 已从关注列表移除")


# ----- Signals -----

@router.get("/signals/{symbol}", response_model=EtfSignalWithMeta)
def get_etf_signal(symbol: str, market: str = "CN", db: Session = Depends(get_db)):
    """
    获取单个 ETF 的最新交易信号（实时计算）。
    返回格式见 EtfSignalWithMeta。
    """
    # 先尝试从数据库读取最新信号（当天）
    today = datetime.now().date()
    etf = db.query(EtfWatch).filter(EtfWatch.symbol == symbol.upper()).first()
    saved_signal = None
    if etf:
        saved_signal = db.query(EtfSignal).filter(
            EtfSignal.etf_watch_id == etf.id,
            EtfSignal.signal_date >= datetime.combine(today, datetime.min.time())
        ).order_by(EtfSignal.signal_date.desc()).first()

    # 实时计算（总是最新的）
    cost = float(etf.cost) if etf and etf.cost else None
    quantity = etf.quantity if etf and etf.quantity else None
    initial_capital = float(etf.initial_capital) if etf and etf.initial_capital else 2000.0
    last_stop_loss = etf.last_stop_loss_date if etf else None
    template_name = etf.template_name if etf else "CORE"
    instrument_type = etf.instrument_type if etf else "ETF"
    try:
        result = EtfSignalService.calculate_etf_signals(
            symbol.upper(), market,
            cost=cost, quantity=quantity, initial_capital=initial_capital,
            last_stop_loss_date=last_stop_loss,
            template_name=template_name,
            instrument_type=instrument_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"信号计算失败: {e}")

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    # 尝试获取 ETF 名称
    name = symbol
    if etf and etf.name:
        name = etf.name
    else:
        try:
            info = StockService.get_stock_info(symbol, market)
            name = info.get("name") or name
        except Exception:
            pass

    # 尝试获取 ETF 名称
    name = symbol
    if etf and etf.name:
        name = etf.name
    else:
        try:
            info = StockService.get_stock_info(symbol, market)
            name = info.get("name") or name
        except Exception:
            pass

    # SELL_ALL 后：写入止损日期（不再自动清空持仓）
    if etf and result.get("action") == "SELL_ALL":
        from datetime import date as date_cls
        etf.last_stop_loss_date = date_cls.today()
        db.commit()

    response = EtfSignalWithMeta(
        symbol=symbol.upper(),
        name=name,
        trend=result["trend"],
        pullback=result["pullback"],
        sentiment=result["sentiment"],
        buy_signal=result["buy_signal"],
        sell_signal=result["sell_signal"],
        action=result["action"],
        volume_ratio=result["volume_ratio"],
        consecutive_up_days=result["consecutive_up_days"],
        cumulative_return=result.get("cumulative_return"),
        ma5=result.get("ma5"),
        ma10=result.get("ma10"),
        ma20=result.get("ma20"),
        current_price=result.get("current_price"),
        daily_return=result.get("change_pct"),
        volume_signal=result.get("volume_signal"),
        breakout=result.get("breakout"),
        reason=result.get("reason"),
        cost=float(etf.cost) if etf and etf.cost else None,
        quantity=etf.quantity if etf and etf.quantity else None,
        initial_capital=float(etf.initial_capital) if etf and etf.initial_capital else 2000.0,
        profit_loss=round((result.get("current_price") - float(etf.cost)) * etf.quantity, 2) if etf and etf.cost and etf.quantity else None,
        profit_loss_pct=round((result.get("current_price") - float(etf.cost)) / float(etf.cost) * 100, 2) if etf and etf.cost else None,
        profit_rate=result.get("profit_rate"),
        ma20_below_days=result.get("ma20_below_days"),
        breakout_confirm=result.get("breakout_confirm"),
        cooldown_days=result.get("cooldown_days"),
        template_name=result.get("template_name"),
        params=result.get("params"),
        is_low_position=result.get("is_low_position"),
        is_high_position=result.get("is_high_position"),
        rise_from_low_pct=result.get("rise_from_low_pct"),
        signal_date=datetime.now(),
        calculated_at=datetime.now(),
        **_extended_signal_fields(result),
    )

    return response


@router.get("/signals", response_model=List[EtfSignalWithMeta])
def list_etf_signals(db: Session = Depends(get_db)):
    """
    批量获取所有关注 ETF 的最新信号（实时计算，带 20 秒缓存）。
    """
    now = time.time()

    # Fast path: return cached data if valid
    with _cache_lock:
        if _cache["data"] is not None and (now - _cache["timestamp"]) < _CACHE_TTL:
            return _cache["data"]

    # Slow path: compute if not already computing
    global _computing
    if _computing:
        # Another thread is computing, wait for it
        while _computing:
            time.sleep(0.1)
        with _cache_lock:
            if _cache["data"] is not None:
                return _cache["data"]
        return []

    _computing = True
    try:
        # Double-check cache after acquiring lock
        with _cache_lock:
            if _cache["data"] is not None and (now - _cache["timestamp"]) < _CACHE_TTL:
                return _cache["data"]

        watch_list = db.query(EtfWatch).filter(EtfWatch.enabled == True).order_by(EtfWatch.id).all()
        results = []
        to_calc = []

        for etf in watch_list:
            cost = float(etf.cost) if etf.cost else None
            quantity = etf.quantity
            initial_capital = float(etf.initial_capital) if etf.initial_capital else 2000.0
            last_stop_loss = etf.last_stop_loss_date
            template_name = etf.template_name or "CORE"
            instrument_type = etf.instrument_type or "ETF"
            to_calc.append((etf, cost, quantity, initial_capital, last_stop_loss, template_name, instrument_type))

        # 并行计算所有 ETF 信号
        def calc_one(args):
            etf, cost, quantity, initial_capital, last_stop_loss, template_name, instrument_type = args
            try:
                return EtfSignalService.calculate_etf_signals(
                    etf.symbol, etf.market,
                    cost=cost, quantity=quantity, initial_capital=initial_capital,
                    last_stop_loss_date=last_stop_loss,
                    template_name=template_name,
                    instrument_type=instrument_type,
                ), etf
            except Exception:
                return None

        futures = [_etf_executor.submit(calc_one, args) for args in to_calc]
        # 按提交顺序收集（as_completed 不保证顺序），最后按原顺序拼接
        results_dict = {}  # idx -> (result, etf)
        for idx, future in enumerate(futures):
            res = future.result()
            if res is None:
                continue
            result, etf = res
            if "error" in result:
                continue
            results_dict[idx] = (result, etf)

        for idx in sorted(results_dict.keys()):
            result, etf = results_dict[idx]
            results.append(EtfSignalWithMeta(
                symbol=etf.symbol,
                name=etf.name or etf.symbol,
                trend=result["trend"],
                pullback=result["pullback"],
                sentiment=result["sentiment"],
                buy_signal=result["buy_signal"],
                sell_signal=result["sell_signal"],
                action=result["action"],
                volume_ratio=result["volume_ratio"],
                consecutive_up_days=result["consecutive_up_days"],
                cumulative_return=result.get("cumulative_return"),
                ma5=result.get("ma5"),
                ma10=result.get("ma10"),
                ma20=result.get("ma20"),
                current_price=result.get("current_price"),
                daily_return=result.get("change_pct"),
                volume_signal=result.get("volume_signal"),
                breakout=result.get("breakout"),
                reason=result.get("reason"),
                cost=float(etf.cost) if etf.cost else None,
                quantity=etf.quantity,
                profit_loss=round((result.get("current_price") - float(etf.cost)) * etf.quantity, 2) if etf.cost and etf.quantity else None,
                profit_loss_pct=round((result.get("current_price") - float(etf.cost)) / float(etf.cost) * 100, 2) if etf.cost else None,
                profit_rate=result.get("profit_rate"),
                ma20_below_days=result.get("ma20_below_days"),
                breakout_confirm=result.get("breakout_confirm"),
                cooldown_days=result.get("cooldown_days"),
                template_name=result.get("template_name"),
                params=result.get("params"),
                is_low_position=result.get("is_low_position"),
                is_high_position=result.get("is_high_position"),
                rise_from_low_pct=result.get("rise_from_low_pct"),
                signal_date=datetime.now(),
                calculated_at=datetime.now(),
                **_extended_signal_fields(result),
            ))

        # SELL_ALL 后：写入止损日期（不再清空持仓，避免误触发后数据丢失）
        for idx in sorted(results_dict.keys()):
            result, etf = results_dict[idx]
            if result.get("action") == "SELL_ALL":
                from datetime import date as date_cls
                etf.last_stop_loss_date = date_cls.today()
                # 注意：不再自动清空持仓，由人工判断是否卖出
                db.commit()

        # Update cache
        with _cache_lock:
            _cache["data"] = results
            _cache["timestamp"] = time.time()

        return results
    finally:
        _computing = False


@router.get("/positions", response_model=List[dict])
def list_positions(db: Session = Depends(get_db)):
    """
    持仓实时行情（不做缓存，每次实时请求腾讯接口）。
    只返回 quantity > 0 的持仓，返回：
    - symbol, name, current_price, daily_return, cost, quantity, profit_loss
    """
    watch_list = db.query(EtfWatch).filter(
        EtfWatch.enabled == True,
        EtfWatch.quantity != None,
        EtfWatch.quantity > 0
    ).order_by(EtfWatch.id).all()

    results = []
    for etf in watch_list:
        price_info = None
        try:
            price_info = StockService.get_stock_info(etf.symbol, etf.market or "CN")
        except Exception:
            pass

        current_price = price_info.get("current_price") if price_info else None
        previous_price = price_info.get("previous_price") if price_info else None
        daily_return = None
        if current_price and previous_price:
            daily_return = round((current_price - previous_price) / previous_price * 100, 2)

        cost = float(etf.cost) if etf.cost else None
        quantity = etf.quantity
        profit_loss = None
        if cost and quantity and current_price:
            profit_loss = round((current_price - cost) * quantity, 2)

        results.append({
            "symbol": etf.symbol,
            "name": etf.name or etf.symbol,
            "current_price": current_price,
            "daily_return": daily_return,
            "cost": cost,
            "quantity": quantity,
            "profit_loss": profit_loss,
        })

    return results


@router.post("/signals/refresh-all", response_model=MessageResponse)
def refresh_all_signals(db: Session = Depends(get_db)):
    """
    刷新所有关注 ETF 的信号并写入数据库（供收盘后定时任务调用）。
    """
    watch_list = db.query(EtfWatch).filter(EtfWatch.enabled == True).all()
    saved = 0
    today = datetime.combine(datetime.now().date(), datetime.min.time())

    for etf in watch_list:
        try:
            result = EtfSignalService.calculate_etf_signals(etf.symbol, etf.market)
        except Exception:
            continue
        if "error" in result:
            continue

        # 删除当天旧信号（避免重复）
        db.query(EtfSignal).filter(
            EtfSignal.etf_watch_id == etf.id,
            EtfSignal.signal_date >= today
        ).delete()

        sig = EtfSignal(
            etf_watch_id=etf.id,
            signal_date=datetime.now(),
            trend=result["trend"],
            pullback=result["pullback"],
            sentiment=result["sentiment"],
            buy_signal=result["buy_signal"],
            sell_signal=result["sell_signal"],
            action=result["action"],
            volume_ratio=result.get("volume_ratio"),
            consecutive_up_days=result.get("consecutive_up_days", 0),
            cumulative_return=result.get("cumulative_return"),
        )
        db.add(sig)
        saved += 1

    db.commit()
    return MessageResponse(message=f"已刷新 {saved} 只 ETF 的信号")