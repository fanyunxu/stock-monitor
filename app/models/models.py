from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    market = Column(String(20), default="CN")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    alert_rules = relationship("AlertRule", back_populates="stock", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="stock", cascade="all, delete-orphan")
    alert_logs = relationship("AlertLog", back_populates="stock", cascade="all, delete-orphan")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    # alert_type: 'rise'(趋势上涨) / 'fall'(趋势下跌) / 'above'(价格高于) / 'below'(价格低于)
    alert_type = Column(String(10), nullable=False)
    # 百分比阈值（趋势告警用）
    threshold_percent = Column(Numeric(5, 2), nullable=False)
    # 统计天数（趋势告警用）
    days = Column(Integer, nullable=False, default=1)
    # 绝对价格阈值（价格突破告警用），可为空
    target_price = Column(Numeric(15, 4), nullable=True)
    enabled = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=0)  # 0 = no cooldown
    # 续警机制：首次预警后，价格再波动超过此阈值则续警（默认1%）
    followup_threshold = Column(Numeric(5, 2), nullable=True)
    # 续警基准价：当天首次预警时的价格，用于计算续警
    followup_base_price = Column(Numeric(15, 4), nullable=True)
    # 续警基准价日期（避免跨日问题）
    followup_base_date = Column(String(20), nullable=True)
    # 上次检查时的价格（用于判断是否变化）
    last_checked_price = Column(Numeric(15, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", back_populates="alert_rules")
    alert_logs = relationship("AlertLog", back_populates="alert_rule", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    price = Column(Numeric(15, 4), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    stock = relationship("Stock", back_populates="price_history")


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    triggered_price = Column(Numeric(15, 4), nullable=False)
    # 快照触发时的规则参数（避免规则修改后历史被篡改）
    alert_type = Column(String(10), nullable=False)
    threshold_percent = Column(Numeric(5, 2), nullable=False)
    days = Column(Integer, nullable=False, default=1)
    target_price = Column(Numeric(15, 4), nullable=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged = Column(Boolean, default=False)
    # 是否为续警
    is_followup = Column(Boolean, default=False)

    stock = relationship("Stock", back_populates="alert_logs")
    alert_rule = relationship("AlertRule", back_populates="alert_logs")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EtfWatch(Base):
    """ETF 关注列表（盯盘的标的）"""
    __tablename__ = "etf_watch"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    market = Column(String(10), default="CN")
    enabled = Column(Boolean, default=True)
    initial_capital = Column(Numeric(10, 2), default=2000.0)
    cost = Column(Numeric(10, 3), nullable=True)      # 持仓成本价
    quantity = Column(Integer, nullable=True)           # 持仓股数
    last_stop_loss_date = Column(Date, nullable=True)   # 上次止损日期（用于冷却期）
    template_name = Column(String(20), default="CORE")  # 绑定的策略模板
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    signals = relationship("EtfSignal", back_populates="etf_watch", cascade="all, delete-orphan")


class EtfSignal(Base):
    """每日 ETF 交易信号计算结果"""
    __tablename__ = "etf_signals"

    id = Column(Integer, primary_key=True, index=True)
    etf_watch_id = Column(Integer, ForeignKey("etf_watch.id"), nullable=False)
    signal_date = Column(DateTime(timezone=True), nullable=False)
    # 趋势
    trend = Column(String(10), nullable=False)  # UP / DOWN
    # 回调位置
    pullback = Column(Boolean, default=False)
    # 情绪过滤
    sentiment = Column(String(20), nullable=False)  # NORMAL / OVERHEAT
    # 信号
    buy_signal = Column(Boolean, default=False)
    sell_signal = Column(Boolean, default=False)
    # 操作建议
    action = Column(String(50), nullable=True)
    # 成交量比率（当前量/5日均量）
    volume_ratio = Column(Numeric(6, 3), nullable=True)
    # 连续上涨天数
    consecutive_up_days = Column(Integer, default=0)
    # 累计涨幅（%）
    cumulative_return = Column(Numeric(8, 3), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    etf_watch = relationship("EtfWatch", back_populates="signals")
