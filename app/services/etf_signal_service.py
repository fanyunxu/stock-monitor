class EtfSignalService:
    """ETF 交易信号计算服务 — delegates to SignalEngine (multi-factor engine)."""

    TEMPLATES = {
        "CORE": {
            "stop_loss": -0.05,
            "take_profit": 0.08,
            "buy_ratio": 0.3,
            "add_ratio": 0.4,
            "volume_threshold": 1.5,
            "breakout_confirm_days": 1,
            "max_position_ratio": 0.8,
            "cooldown_days": 2,
            "add_profit_threshold": 0.02,
            "sell_partial_profit": 0.05,
        },
        "THEME": {
            "stop_loss": -0.06,
            "take_profit": 0.07,
            "buy_ratio": 0.2,
            "add_ratio": 0.2,
            "volume_threshold": 2.0,
            "breakout_confirm_days": 2,
            "max_position_ratio": 0.6,
            "cooldown_days": 2,
            "add_profit_threshold": 0.03,
            "sell_partial_profit": 0.04,
        },
    }

    DEFAULT_TEMPLATE = "CORE"
    MARKET_SYMBOL = "000300"
    _market_cache = {"data": None, "timestamp": 0}
    _MARKET_CACHE_TTL = 60

    @staticmethod
    def calculate_etf_signals(symbol: str, market: str = "CN",
                              cost: float = None, quantity: int = None,
                              initial_capital: float = 2000.0,
                              last_stop_loss_date=None,
                              template_name: str = None,
                              instrument_type: str = "ETF") -> dict:
        """Delegate to SignalEngine for professional multi-factor signal calculation."""
        from app.services.signal_engine import SignalEngine
        return SignalEngine.calculate(
            symbol=symbol, market=market,
            cost=cost, quantity=quantity,
            initial_capital=initial_capital,
            last_stop_loss_date=last_stop_loss_date,
            template_name=template_name,
            instrument_type=instrument_type,
        )

    @staticmethod
    def get_templates() -> dict:
        return {name: params for name, params in EtfSignalService.TEMPLATES.items()}

    @staticmethod
    def validate_params(params: dict) -> tuple:
        constraints = {
            "stop_loss": (-0.1, -0.01),
            "take_profit": (0.02, 0.15),
            "buy_ratio": (0.1, 0.5),
            "add_ratio": (0.1, 0.5),
            "volume_threshold": (1.0, 3.0),
            "breakout_confirm_days": (1, 3),
            "cooldown_days": (1, 5),
            "add_profit_threshold": (0.01, 0.1),
            "sell_partial_profit": (0.02, 0.15),
        }
        for key, (lo, hi) in constraints.items():
            if key in params:
                v = params[key]
                if not isinstance(v, (int, float)):
                    return False, f"{key} 须为数字"
                if v < lo or v > hi:
                    return False, f"{key} 须在 {lo}~{hi} 范围"
        return True, ""

    @staticmethod
    def get_template_names() -> list:
        return list(EtfSignalService.TEMPLATES.keys())
