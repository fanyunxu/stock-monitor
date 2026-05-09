from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class StockBase(BaseModel):
    symbol: str
    name: Optional[str] = None
    market: Optional[str] = "CN"


class StockCreate(StockBase):
    pass


class StockResponse(StockBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StockWithPrice(StockResponse):
    current_price: Optional[float] = None
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None


class AlertRuleBase(BaseModel):
    stock_id: int
    # 类型: rise(趋势上涨) / fall(趋势下跌) / above(价格高于) / below(价格低于)
    alert_type: str
    threshold_percent: float = 0.0
    days: int = 1
    # 价格突破告警的目标价格
    target_price: Optional[float] = None
    enabled: bool = True
    # 续警阈值（%）：首次预警后，价格再波动超过此阈值则续警，默认为 1
    followup_threshold: Optional[float] = 1.0


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    alert_type: Optional[str] = None
    threshold_percent: Optional[float] = None
    cooldown_minutes: Optional[int] = 0
    days: Optional[int] = None
    target_price: Optional[float] = None
    enabled: Optional[bool] = None
    followup_threshold: Optional[float] = None


class AlertRuleResponse(AlertRuleBase):
    id: int
    created_at: datetime
    stock_symbol: Optional[str] = None
    stock_name: Optional[str] = None

    class Config:
        from_attributes = True


class AlertLogResponse(BaseModel):
    id: int
    stock_id: int
    alert_rule_id: int
    triggered_price: float
    triggered_at: datetime
    acknowledged: bool
    stock_symbol: Optional[str] = None
    stock_name: Optional[str] = None
    market: Optional[str] = None
    alert_type: Optional[str] = None
    threshold_percent: Optional[float] = None
    cooldown_minutes: Optional[int] = 0
    days: Optional[int] = None
    target_price: Optional[float] = None
    # 是否为续警
    is_followup: Optional[bool] = False

    class Config:
        from_attributes = True


class PriceHistoryResponse(BaseModel):
    id: int
    stock_id: int
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


class StockPriceResponse(BaseModel):
    symbol: str
    name: str
    current_price: float
    previous_price: Optional[float] = None
    price_change: Optional[float] = None
    price_change_percent: Optional[float] = None
    market: str
    timestamp: datetime


# ========== ETF Signal Schemas ==========

class EtfWatchBase(BaseModel):
    symbol: str
    name: Optional[str] = None
    market: Optional[str] = "CN"
    enabled: Optional[bool] = True
    initial_capital: Optional[float] = 2000.0
    cost: Optional[float] = None
    quantity: Optional[int] = None
    template_name: Optional[str] = "CORE"


class EtfWatchCreate(EtfWatchBase):
    pass


class EtfWatchResponse(EtfWatchBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class EtfSignalResponse(BaseModel):
    id: int
    etf_watch_id: int
    signal_date: datetime
    trend: str
    pullback: bool
    sentiment: str
    buy_signal: bool
    sell_signal: bool
    action: Optional[str] = None
    volume_ratio: Optional[float] = None
    consecutive_up_days: int
    cumulative_return: Optional[float] = None
    created_at: datetime
    # 扩展字段（从计算结果附加）
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    current_price: Optional[float] = None
    daily_return: Optional[float] = None

    class Config:
        from_attributes = True


class EtfSignalWithMeta(BaseModel):
    """ETF 信号 + 附加元信息（用于列表展示）"""
    id: Optional[int] = None
    symbol: str
    name: Optional[str] = None
    trend: str
    pullback: bool
    sentiment: str
    buy_signal: bool
    sell_signal: bool
    action: Optional[str] = None
    volume_ratio: Optional[float] = None
    consecutive_up_days: int
    cumulative_return: Optional[float] = None
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    current_price: Optional[float] = None
    daily_return: Optional[float] = None
    signal_date: Optional[datetime] = None
    calculated_at: Optional[datetime] = None

    # 新框架字段
    volume_signal: Optional[str] = None
    breakout: Optional[bool] = None
    reason: Optional[str] = None
    # 持仓信息
    cost: Optional[float] = None
    quantity: Optional[int] = None
    profit_loss: Optional[float] = None    # 盈亏金额
    profit_loss_pct: Optional[float] = None  # 盈亏比例%
    profit_rate: Optional[float] = None      # 持仓收益率（浮盈浮亏）
    # 新增决策变量
    ma20_below_days: Optional[int] = None    # 连续跌破MA20天数
    breakout_confirm: Optional[bool] = None   # 突破确认（次日验证）
    cooldown_days: Optional[int] = None       # 冷却期剩余天数
    template_name: Optional[str] = None       # 绑定的策略模板
    params: Optional[dict] = None           # 当前模板参数
    # 位置判断
    is_low_position: Optional[bool] = None    # 是否低位（从底部涨<8%）
    is_high_position: Optional[bool] = None   # 是否高位（连续涨≥3天）
    rise_from_low_pct: Optional[float] = None  # 从20日低点上涨百分比

    # 评分策略字段
    signal_score: Optional[float] = None
    buy_score: Optional[float] = None
    sell_score: Optional[float] = None
    risk_score: Optional[float] = None
    trend_score: Optional[float] = None
    volume_score: Optional[float] = None
    momentum_score: Optional[float] = None
    position_score: Optional[float] = None
    score_breakdown: Optional[dict] = None

    # 技术指标扩展
    trend_strength: Optional[float] = None
    trend_level: Optional[str] = None
    rsi: Optional[float] = None
    rsi_signal: Optional[str] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    dynamic_stop_price: Optional[float] = None
    dynamic_stop_loss_pct: Optional[float] = None
    stop_loss_triggered: Optional[bool] = None

    # 市场过滤与突破质量
    market_symbol: Optional[str] = None
    market_trend: Optional[str] = None
    market_filter: Optional[str] = None
    market_score: Optional[float] = None
    market_reason: Optional[str] = None
    market_rsi: Optional[float] = None
    market_trend_strength: Optional[float] = None
    breakout_strength: Optional[float] = None
    breakout_quality: Optional[str] = None

    # 仓位和 AI 兼容字段
    position_ratio: Optional[float] = None
    max_position_ratio: Optional[float] = None
    can_add_position: Optional[bool] = None
    ai_summary: Optional[str] = None
    ai_signal: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_risk_level: Optional[str] = None
    decision_factors: Optional[List[str]] = None
    technical_snapshot: Optional[dict] = None

    class Config:
        from_attributes = True
