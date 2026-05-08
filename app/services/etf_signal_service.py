import requests
from datetime import date, timedelta
from app.services.stock_service import StockService


class EtfSignalService:
    """ETF 交易信号计算服务（v5 策略模板版）。

    支持 CORE / THEME 两种策略模板，参数完全可配置。
    """

    # ---------- 内置模板定义 ----------

    TEMPLATES = {
        "CORE": {
            "stop_loss": -0.05,
            "take_profit": 0.05,
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
            "take_profit": 0.04,
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

    # ---------- 内部工具方法 ----------

    @staticmethod
    def _get_prev_day_high_low(symbol: str) -> tuple:
        """获取前一日（倒数第二根K线）最高/最低价。"""
        symbol = symbol.upper().strip()

        if symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            secid_prefix = "0"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            secid_prefix = "0"
        else:
            secid_prefix = "1"

        try:
            url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                "secid": f"{secid_prefix}{symbol}",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": "101",
                "fqt": "1",
                "end": "20500101",
                "lmt": 3,
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            klines = (data.get("data") or {}).get("klines") or []
            if len(klines) < 2:
                return None, None
            prev_kline = klines[-2]
            parts = prev_kline.split(",")
            return float(parts[3]), float(parts[4])
        except Exception:
            return None, None

    @staticmethod
    def _count_ma20_below_days(closes: list, threshold_days: int = 2) -> int:
        """
        统计连续多少天收盘价低于MA20（从最近一根往前算）。
        """
        if len(closes) < 21:
            return 0
        ma20 = sum(closes[-20:]) / 20
        count = 0
        for i in range(len(closes) - 2, max(len(closes) - 2 - threshold_days, -1), -1):
            if closes[i] < ma20:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _is_breakout_confirmed(symbol: str, prev_high: float, confirm_days: int = 1) -> bool:
        """
        突破确认：前 confirm_days 天收盘价均 > 前高。
        """
        symbol = symbol.upper().strip()
        if prev_high is None or confirm_days < 1:
            return False

        if symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            secid_prefix = "0"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            secid_prefix = "0"
        else:
            secid_prefix = "1"

        try:
            url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                "secid": f"{secid_prefix}{symbol}",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": "101",
                "fqt": "1",
                "end": "20500101",
                "lmt": confirm_days + 1,
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            klines = (data.get("data") or {}).get("klines") or []
            if len(klines) < confirm_days + 1:
                return False
            # 从倒数第2根往前 confirm_days 根
            for i in range(1, confirm_days + 1):
                prev_close = float(klines[-i].split(",")[2])
                if prev_close <= prev_high:
                    return False
            return True
        except Exception:
            return False

    # ---------- 核心方法 ----------

    @staticmethod
    def calculate_etf_signals(symbol: str, market: str = "CN",
                               cost: float = None, quantity: int = None,
                               initial_capital: float = 2000.0,
                               last_stop_loss_date=None,
                               template_name: str = None) -> dict:
        """
        计算 ETF 交易信号（v5 策略模板版）。

        Args:
            symbol: ETF 代码
            market: 市场（默认 CN）
            cost: 持仓成本价（None 表示无持仓）
            quantity: 持仓股数
            initial_capital: 总资金
            last_stop_loss_date: date对象，上次止损日期
            template_name: 策略模板名（默认 CORE）
        """
        template_name = template_name or EtfSignalService.DEFAULT_TEMPLATE
        params = EtfSignalService.TEMPLATES.get(template_name, EtfSignalService.TEMPLATES["CORE"])

        stop_loss = params["stop_loss"]
        take_profit = params["take_profit"]
        buy_ratio = params["buy_ratio"]
        add_ratio = params["add_ratio"]
        volume_threshold = params["volume_threshold"]
        breakout_confirm_days = params["breakout_confirm_days"]
        max_position_ratio = params["max_position_ratio"]
        cooldown_days_cfg = params["cooldown_days"]
        add_profit_threshold = params["add_profit_threshold"]
        sell_partial_profit = params["sell_partial_profit"]

        try:
            raw = StockService.get_price_history_with_volume(symbol, market, days=35)
        except Exception as e:
            return {"error": f"获取行情数据失败: {e}"}

        if len(raw) < 25:
            return {"error": "数据不足（需要至少 25 个交易日）"}

        closes = [d["price"] for d in raw]
        volumes = [d["volume"] for d in raw]

        try:
            info = StockService.get_stock_info(symbol, market)
            current_price = info.get("current_price", closes[-1])
            change_pct = info.get("price_change_percent", 0.0)
        except Exception:
            current_price = closes[-1]
            change_pct = 0.0

        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20

        avg_volume_5 = sum(volumes[-5:]) / 5
        yesterday_volume = volumes[-1]
        volume_ratio = round(yesterday_volume / avg_volume_5, 3) if avg_volume_5 > 0 else 0.0

        yesterday_close = closes[-1]
        prev_close = closes[-2] if len(closes) >= 2 else yesterday_close

        consecutive_up_days = 0
        for i in range(len(closes) - 2, -1, -1):
            if closes[i] > closes[i + 1]:
                consecutive_up_days += 1
            else:
                break
        if current_price > yesterday_close:
            consecutive_up_days += 1

        ma20_below_days = EtfSignalService._count_ma20_below_days(closes, threshold_days=breakout_confirm_days + 1)

        prev_high, prev_low = EtfSignalService._get_prev_day_high_low(symbol)

        # ====== 五维判断 ======

        trend = "UP" if (ma5 > ma10 and ma10 > ma20 and current_price > ma20) else "DOWN"

        ma10_diff_pct = abs(current_price - ma10) / ma10 if ma10 > 0 else 1
        ma20_diff_pct = abs(current_price - ma20) / ma20 if ma20 > 0 else 1
        pullback = (ma10_diff_pct < 0.02 or ma20_diff_pct < 0.02) and (current_price >= ma20)

        sentiment = "OVERHEAT" if (change_pct > 3 or consecutive_up_days >= 3) else "NORMAL"

        is_up_yesterday = yesterday_close > prev_close
        if is_up_yesterday:
            volume_signal = "STRONG" if volume_ratio > 2 else ("WEAK" if volume_ratio < 1 else "NORMAL")
        else:
            volume_signal = "RISK" if volume_ratio > 2 else "NORMAL"

        breakout = prev_high is not None and current_price > prev_high
        breakout_confirm = breakout and EtfSignalService._is_breakout_confirmed(symbol, prev_high, breakout_confirm_days)

        # ====== 位置判断（低位/中继/高位）======
        low_20 = min(closes[-20:]) if len(closes) >= 20 else min(closes)
        rise_from_low_pct = (current_price - low_20) / low_20 * 100 if low_20 > 0 else 999
        # 低位：从底部上涨不超过 8%，视为低位启动
        is_low_position = rise_from_low_pct <= 8
        # 高位：连续上涨 ≥3 天 且 价格已在 MA20 之上
        is_high_position = consecutive_up_days >= 3 and current_price > ma20

        # ====== 冷却期 ======

        cooldown_remaining = 0
        if last_stop_loss_date:
            today = date.today()
            days_since_stop = (today - last_stop_loss_date).days
            cooldown_remaining = max(0, cooldown_days_cfg - days_since_stop)

        # ====== 持仓信息 ======

        has_position = (cost is not None and cost > 0 and quantity is not None and quantity > 0)
        profit_rate = None
        if has_position:
            profit_rate = (current_price - float(cost)) / float(cost)

        # ====== 交易决策（优先级） ======

        action = "HOLD"
        reason = "当前无明确信号"
        buy_signal = False
        sell_signal = False

        if not has_position:
            # --- 情况1：无持仓 ---
            if cooldown_remaining > 0:
                action = "HOLD"
                reason = f"冷却期：止损后{cooldown_remaining}天内禁止买入"
            elif trend == "UP" and pullback and sentiment == "NORMAL" and volume_signal != "WEAK":
                action = f"BUY_{int(buy_ratio * 100)}"
                reason = f"无持仓+趋势向上+回调充分+情绪正常+量比正常，试探买入{int(buy_ratio * 100)}%"
                buy_signal = True
            elif trend == "UP" and pullback and sentiment == "NORMAL" and volume_signal == "WEAK" and is_low_position:
                # 低位缩量上涨 → 试仓（从底部上涨<8%，缩量可能是主力控盘）
                action = f"BUY_{int(buy_ratio * 100)}"
                reason = f"低位缩量启动（从底部涨{rise_from_low_pct:.1f}%）+趋势向上，可试探买入{int(buy_ratio * 100)}%"
                buy_signal = True
            else:
                action = "HOLD"
                if trend == "DOWN":
                    reason = "无持仓但趋势向下，耐心等待"
                elif not pullback:
                    reason = "无持仓但价格未回调至MA10/MA20附近，不宜追入"
                elif sentiment == "OVERHEAT":
                    reason = "无持仓但涨幅过热，谨慎买入"
                elif volume_signal == "WEAK" and is_high_position:
                    reason = "高位缩量上涨，不追，等回调或放量确认"
                elif volume_signal == "WEAK":
                    reason = "缩量整理中，等放量确认"
                else:
                    reason = "无持仓，当前无买入信号"

        else:
            # --- 情况2：已有持仓 ---
            # ① 止损（最高优先级）
            stop_loss_triggered = (
                (profit_rate is not None and profit_rate <= stop_loss and current_price < ma20)
                or (ma20_below_days >= breakout_confirm_days)
            )
            if stop_loss_triggered:
                action = "SELL_ALL"
                reason = f"止损：亏损{profit_rate*100:.1f}%+跌破MA20连续{ma20_below_days}天"
                sell_signal = True

            # ② 冷却期
            elif cooldown_remaining > 0:
                action = "HOLD"
                reason = f"冷却期：止损后{cooldown_remaining}天内禁止买入"

            # ③ 放量下跌（风险）
            elif change_pct < 0 and volume_ratio > 2:
                action = "SELL_PARTIAL"
                reason = "放量下跌：下跌且量比>2，主力可能出货，减持"
                sell_signal = True

            # ④ 小亏持有
            elif profit_rate < 0 and trend == "UP":
                action = "HOLD"
                reason = f"小亏{profit_rate*100:.1f}%但趋势向上，持有观望"

            # ⑤ 回本阶段
            elif profit_rate is not None and 0 <= profit_rate < add_profit_threshold:
                action = "HOLD"
                reason = f"回本阶段(盈利{profit_rate*100:.1f}%)，暂不止盈"

            # ⑥ 加仓
            elif (profit_rate is not None and profit_rate >= add_profit_threshold
                  and breakout_confirm and volume_ratio > volume_threshold):
                action = f"ADD_{int(add_ratio * 100)}"
                reason = f"盈利{profit_rate*100:.1f}%+突破确认+放量，可加仓{int(add_ratio * 100)}%"
                buy_signal = True

            # ⑦ 止盈
            elif profit_rate is not None and profit_rate >= sell_partial_profit:
                action = "SELL_PARTIAL"
                reason = f"盈利{profit_rate*100:.1f}%，触发止盈，减持"
                sell_signal = True

            else:
                action = "HOLD"
                reason = f"持仓中，盈亏{(profit_rate*100 if profit_rate else 0):.1f}%，无操作信号"

        return {
            "trend": trend,
            "pullback": pullback,
            "sentiment": sentiment,
            "volume_signal": volume_signal,
            "breakout": breakout,
            "breakout_confirm": breakout_confirm,
            "is_low_position": is_low_position,
            "is_high_position": is_high_position,
            "rise_from_low_pct": round(rise_from_low_pct, 2) if rise_from_low_pct else None,
            "action": action,
            "reason": reason,
            "buy_signal": buy_signal,
            "sell_signal": sell_signal,
            "volume_ratio": volume_ratio,
            "consecutive_up_days": consecutive_up_days,
            "ma20_below_days": ma20_below_days,
            "cooldown_days": cooldown_remaining,
            "ma5": round(ma5, 3),
            "ma10": round(ma10, 3),
            "ma20": round(ma20, 3),
            "current_price": round(current_price, 3),
            "change_pct": round(change_pct, 2),
            "prev_high": round(prev_high, 3) if prev_high else None,
            "prev_low": round(prev_low, 3) if prev_low else None,
            "position_size": quantity,
            "avg_cost": round(float(cost), 3) if cost else None,
            "profit_rate": round(profit_rate, 4) if profit_rate is not None else None,
            "template_name": template_name,
            "params": params,
        }

    @staticmethod
    def get_templates() -> dict:
        """返回所有内置模板（不含敏感逻辑，仅参数）。"""
        return {name: params for name, params in EtfSignalService.TEMPLATES.items()}

    @staticmethod
    def validate_params(params: dict) -> tuple:
        """校验参数合法性，返回 (is_valid, error_message)。"""
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
