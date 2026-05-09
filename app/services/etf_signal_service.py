from datetime import date
import time
from app.services.stock_service import StockService


class EtfSignalService:
    """ETF 交易信号计算服务（评分策略版）。"""

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
    def _clamp(value: float, low: float = 0, high: float = 100) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _ma(values: list, period: int, end_index: int = None) -> float:
        if end_index is None:
            end_index = len(values)
        start = end_index - period
        if start < 0 or end_index > len(values):
            return None
        window = values[start:end_index]
        return sum(window) / period if len(window) == period else None

    @staticmethod
    def _count_consecutive_up_days(closes: list, current_price: float) -> int:
        if len(closes) < 2:
            return 0
        series = closes[:]
        if current_price is not None and current_price != closes[-1]:
            series.append(current_price)
        count = 0
        for i in range(len(series) - 1, 0, -1):
            if series[i] > series[i - 1]:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _count_ma_below_days(closes: list, period: int = 20, max_days: int = 3) -> int:
        count = 0
        for end_index in range(len(closes), period - 1, -1):
            ma = EtfSignalService._ma(closes, period, end_index)
            if ma is None or closes[end_index - 1] >= ma:
                break
            count += 1
            if count >= max_days:
                break
        return count

    @staticmethod
    def _calculate_rsi(closes: list, period: int = 14) -> float:
        if len(closes) <= period:
            return None
        gains = []
        losses = []
        for i in range(len(closes) - period, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calculate_atr(klines: list, period: int = 14) -> float:
        if len(klines) <= period:
            return None
        true_ranges = []
        for i in range(len(klines) - period, len(klines)):
            high = klines[i].get("high", klines[i].get("price"))
            low = klines[i].get("low", klines[i].get("price"))
            prev_close = klines[i - 1].get("close", klines[i - 1].get("price"))
            if high is None or low is None or prev_close is None:
                continue
            true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        return sum(true_ranges) / len(true_ranges) if true_ranges else None

    @staticmethod
    def _trend_strength(closes: list, current_price: float, ma5: float, ma10: float, ma20: float) -> tuple:
        score = 50.0
        if ma5 and ma10 and ma20:
            if ma5 > ma10 > ma20:
                score += 22
            elif ma5 < ma10 < ma20:
                score -= 22
            else:
                score += 4 if ma5 > ma20 else -4

            if current_price > ma5 > ma10:
                score += 12
            elif current_price < ma5 < ma10:
                score -= 12

            ma5_prev = EtfSignalService._ma(closes, 5, len(closes) - 1)
            ma20_prev = EtfSignalService._ma(closes, 20, len(closes) - 1)
            if ma5_prev and ma20_prev:
                if ma5 > ma5_prev and ma20 >= ma20_prev:
                    score += 10
                elif ma5 < ma5_prev and ma20 <= ma20_prev:
                    score -= 10

            distance = (current_price - ma20) / ma20 if ma20 else 0
            score += EtfSignalService._clamp(distance * 400, -18, 18)

        if len(closes) >= 6 and closes[-6] > 0:
            five_day_return = (current_price - closes[-6]) / closes[-6]
            score += EtfSignalService._clamp(five_day_return * 220, -14, 14)

        score = round(EtfSignalService._clamp(score), 1)
        if score >= 75:
            level = "STRONG_UP"
        elif score >= 58:
            level = "UP"
        elif score >= 43:
            level = "NEUTRAL"
        elif score >= 28:
            level = "DOWN"
        else:
            level = "STRONG_DOWN"
        return score, level

    @staticmethod
    def _rsi_signal(rsi: float) -> str:
        if rsi is None:
            return "UNKNOWN"
        if rsi < 35:
            return "OVERSOLD"
        if rsi > 70:
            return "OVERBOUGHT"
        return "NEUTRAL"

    @staticmethod
    def _market_filter() -> dict:
        now = time.time()
        cached = EtfSignalService._market_cache
        if cached["data"] is not None and now - cached["timestamp"] < EtfSignalService._MARKET_CACHE_TTL:
            return cached["data"]

        try:
            raw = StockService.get_price_history_with_volume(EtfSignalService.MARKET_SYMBOL, "CN", days=35)
            closes = [d["price"] for d in raw]
            if len(closes) < 25:
                raise ValueError("沪深300数据不足")
            ma5 = EtfSignalService._ma(closes, 5)
            ma20 = EtfSignalService._ma(closes, 20)
            current_price = closes[-1]
            rsi = EtfSignalService._calculate_rsi(closes)
            strength, level = EtfSignalService._trend_strength(closes, current_price, ma5, EtfSignalService._ma(closes, 10), ma20)

            score = strength
            if rsi is not None and rsi > 78:
                score -= 8
            elif rsi is not None and rsi < 25:
                score -= 5
            score = round(EtfSignalService._clamp(score), 1)

            if current_price < ma20 and strength < 42:
                market_filter = "BLOCK"
                reason = "沪深300低于MA20且趋势偏弱"
            elif current_price < ma20 or strength < 50:
                market_filter = "CAUTION"
                reason = "沪深300趋势一般，降低买入权重"
            else:
                market_filter = "PASS"
                reason = "沪深300趋势过滤通过"

            data = {
                "market_symbol": EtfSignalService.MARKET_SYMBOL,
                "market_trend": "UP" if strength >= 55 else "DOWN" if strength < 45 else "NEUTRAL",
                "market_filter": market_filter,
                "market_score": score,
                "market_reason": reason,
                "market_rsi": round(rsi, 2) if rsi is not None else None,
                "market_trend_strength": strength,
                "market_trend_level": level,
            }
        except Exception as e:
            data = {
                "market_symbol": EtfSignalService.MARKET_SYMBOL,
                "market_trend": "NEUTRAL",
                "market_filter": "CAUTION",
                "market_score": 50,
                "market_reason": f"沪深300过滤数据不可用: {e}",
                "market_rsi": None,
                "market_trend_strength": 50,
                "market_trend_level": "NEUTRAL",
            }

        EtfSignalService._market_cache = {"data": data, "timestamp": now}
        return data

    @staticmethod
    def _breakout_metrics(klines: list, current_price: float, confirm_days: int, volume_ratio: float, volume_threshold: float) -> dict:
        if len(klines) < confirm_days + 3:
            return {
                "prev_high": None,
                "prev_low": None,
                "breakout": False,
                "breakout_strength": 0.0,
                "breakout_confirm": False,
                "breakout_quality": "NONE",
            }
        prev = klines[-2]
        prev_high = prev.get("high", prev.get("price"))
        prev_low = prev.get("low", prev.get("price"))
        breakout = prev_high is not None and current_price > prev_high
        breakout_strength = ((current_price - prev_high) / prev_high * 100) if breakout and prev_high else 0.0

        confirmed = True
        for offset in range(2, confirm_days + 2):
            current_bar = klines[-offset]
            prior_bar = klines[-offset - 1]
            close = current_bar.get("close", current_bar.get("price"))
            prior_high = prior_bar.get("high", prior_bar.get("price"))
            if close is None or prior_high is None or close <= prior_high:
                confirmed = False
                break

        if breakout and confirmed and volume_ratio >= volume_threshold:
            quality = "VOLUME_CONFIRMED"
        elif breakout and confirmed:
            quality = "CONFIRMED"
        elif breakout:
            quality = "WEAK"
        else:
            quality = "NONE"

        return {
            "prev_high": prev_high,
            "prev_low": prev_low,
            "breakout": breakout,
            "breakout_strength": round(breakout_strength, 2),
            "breakout_confirm": breakout and confirmed,
            "breakout_quality": quality,
        }

    @staticmethod
    def calculate_etf_signals(symbol: str, market: str = "CN",
                              cost: float = None, quantity: int = None,
                              initial_capital: float = 2000.0,
                              last_stop_loss_date=None,
                              template_name: str = None) -> dict:
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

        closes = [d.get("close", d["price"]) for d in raw]
        volumes = [d.get("volume", 0) for d in raw]

        try:
            info = StockService.get_stock_info(symbol, market)
            current_price = info.get("current_price", closes[-1]) or closes[-1]
            change_pct = info.get("price_change_percent")
            if change_pct is None and closes[-1]:
                change_pct = (current_price - closes[-1]) / closes[-1] * 100
        except Exception:
            current_price = closes[-1]
            change_pct = 0.0

        ma5 = EtfSignalService._ma(closes, 5)
        ma10 = EtfSignalService._ma(closes, 10)
        ma20 = EtfSignalService._ma(closes, 20)
        rsi = EtfSignalService._calculate_rsi(closes)
        rsi_signal = EtfSignalService._rsi_signal(rsi)
        atr = EtfSignalService._calculate_atr(raw)
        atr_pct = (atr / current_price * 100) if atr and current_price else None
        trend_strength, trend_level = EtfSignalService._trend_strength(closes, current_price, ma5, ma10, ma20)

        closed_volume_window = volumes[-6:-1] if len(volumes) >= 6 else volumes[-5:]
        avg_volume_5 = sum(closed_volume_window) / len(closed_volume_window) if closed_volume_window else 0
        reference_volume = volumes[-1]
        volume_ratio = round(reference_volume / avg_volume_5, 3) if avg_volume_5 > 0 else 0.0

        prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
        yesterday_close = closes[-1]
        consecutive_up_days = EtfSignalService._count_consecutive_up_days(closes, current_price)
        ma20_below_days = EtfSignalService._count_ma_below_days(closes, 20, breakout_confirm_days + 1)

        trend = "UP" if trend_strength >= 55 else "DOWN"
        ma10_diff_pct = abs(current_price - ma10) / ma10 if ma10 else 1
        ma20_diff_pct = abs(current_price - ma20) / ma20 if ma20 else 1
        pullback = (ma10_diff_pct < 0.02 or ma20_diff_pct < 0.025) and current_price >= ma20
        sentiment = "OVERHEAT" if ((rsi is not None and rsi > 70) or change_pct > 3 or consecutive_up_days >= 4) else "NORMAL"

        is_up_day = current_price > prev_close if current_price != yesterday_close else yesterday_close > prev_close
        if is_up_day:
            volume_signal = "STRONG" if volume_ratio > 2 else "WEAK" if volume_ratio < 0.8 else "NORMAL"
        else:
            volume_signal = "RISK" if volume_ratio > 2 else "NORMAL"

        breakout_data = EtfSignalService._breakout_metrics(raw, current_price, breakout_confirm_days, volume_ratio, volume_threshold)
        market_data = EtfSignalService._market_filter()

        low_20 = min(closes[-20:])
        rise_from_low_pct = (current_price - low_20) / low_20 * 100 if low_20 > 0 else 999
        is_low_position = rise_from_low_pct <= 8
        is_high_position = consecutive_up_days >= 3 and current_price > ma20

        cooldown_remaining = 0
        if last_stop_loss_date:
            days_since_stop = (date.today() - last_stop_loss_date).days
            cooldown_remaining = max(0, cooldown_days_cfg - days_since_stop)

        has_position = cost is not None and cost > 0 and quantity is not None and quantity > 0
        profit_rate = (current_price - float(cost)) / float(cost) if has_position else None
        position_value = current_price * quantity if has_position else 0
        position_ratio = position_value / initial_capital if initial_capital and initial_capital > 0 else 0
        can_add_position = position_ratio < max_position_ratio

        fixed_stop_price = float(cost) * (1 + stop_loss) if has_position else None
        recent_high = max(d.get("high", d.get("price")) for d in raw[-20:])
        atr_stop_price = recent_high - 2 * atr if has_position and atr else None
        dynamic_stop_price = max(fixed_stop_price, atr_stop_price) if fixed_stop_price and atr_stop_price else fixed_stop_price
        dynamic_stop_loss_pct = ((dynamic_stop_price - float(cost)) / float(cost) * 100) if has_position and dynamic_stop_price else None
        stop_loss_triggered = bool(has_position and dynamic_stop_price and current_price <= dynamic_stop_price and (trend_strength < 45 or market_data["market_filter"] != "PASS"))

        trend_score = trend_strength
        volume_score = 50
        if volume_signal == "STRONG":
            volume_score = 78
        elif volume_signal == "WEAK":
            volume_score = 38
        elif volume_signal == "RISK":
            volume_score = 25
        momentum_score = 50
        if rsi is not None:
            if rsi < 35:
                momentum_score += 18
            elif rsi <= 65:
                momentum_score += 8
            elif rsi > 80:
                momentum_score -= 22
            elif rsi > 70:
                momentum_score -= 14
        if breakout_data["breakout_quality"] == "VOLUME_CONFIRMED":
            momentum_score += 18
        elif breakout_data["breakout_quality"] == "CONFIRMED":
            momentum_score += 12
        elif breakout_data["breakout_quality"] == "WEAK":
            momentum_score += 5
        if pullback:
            momentum_score += 8
        momentum_score = round(EtfSignalService._clamp(momentum_score), 1)

        position_score = 50
        if is_low_position:
            position_score += 16
        if is_high_position:
            position_score -= 16
        if not can_add_position:
            position_score -= 20
        position_score = round(EtfSignalService._clamp(position_score), 1)

        market_score = market_data["market_score"]
        risk_score = 20
        if sentiment == "OVERHEAT":
            risk_score += 18
        if volume_signal == "RISK":
            risk_score += 24
        if ma20_below_days >= breakout_confirm_days + 1:
            risk_score += 18
        if rsi is not None and rsi > 80:
            risk_score += 18
        if market_data["market_filter"] == "BLOCK":
            risk_score += 18
        elif market_data["market_filter"] == "CAUTION":
            risk_score += 8
        if stop_loss_triggered:
            risk_score += 35
        if profit_rate is not None and profit_rate >= take_profit:
            risk_score += 16
        risk_score = round(EtfSignalService._clamp(risk_score), 1)

        buy_score = (
            trend_score * 0.34 + volume_score * 0.16 + momentum_score * 0.22 +
            position_score * 0.14 + market_score * 0.14
        )
        if cooldown_remaining > 0:
            buy_score -= 30
        if sentiment == "OVERHEAT":
            buy_score -= 15
        if market_data["market_filter"] == "BLOCK":
            buy_score -= 35
        elif market_data["market_filter"] == "CAUTION":
            buy_score -= 10
        if not can_add_position:
            buy_score -= 20
        buy_score = round(EtfSignalService._clamp(buy_score), 1)

        sell_score = risk_score
        if has_position and profit_rate is not None:
            if profit_rate <= stop_loss:
                sell_score += 25
            if profit_rate >= sell_partial_profit:
                sell_score += 15
            if profit_rate >= take_profit:
                sell_score += 20
            if trend_strength < 35:
                sell_score += 15
        sell_score = round(EtfSignalService._clamp(sell_score), 1)
        signal_score = round(EtfSignalService._clamp(buy_score - risk_score * 0.25 + 15), 1)

        decision_factors = []
        if trend_strength >= 65:
            decision_factors.append(f"趋势强度较高({trend_strength})")
        elif trend_strength < 45:
            decision_factors.append(f"趋势偏弱({trend_strength})")
        if pullback:
            decision_factors.append("价格接近MA10/MA20回踩区")
        else:
            decision_factors.append("价格未到理想回踩区，追入性价比一般")
        if breakout_data["breakout_quality"] != "NONE":
            decision_factors.append(f"突破质量{breakout_data['breakout_quality']}，突破幅度{breakout_data['breakout_strength']:.2f}%")
        else:
            decision_factors.append("尚未形成有效突破")
        if rsi is not None:
            decision_factors.append(f"RSI {rsi:.1f}({rsi_signal})")
        if volume_signal == "STRONG":
            decision_factors.append(f"放量上涨，量比{volume_ratio:.2f}")
        elif volume_signal == "WEAK":
            decision_factors.append(f"缩量上涨，量比{volume_ratio:.2f}")
        elif volume_signal == "RISK":
            decision_factors.append(f"放量下跌风险，量比{volume_ratio:.2f}")
        else:
            decision_factors.append(f"量能正常，量比{volume_ratio:.2f}")
        if atr_pct is not None:
            decision_factors.append(f"ATR波动率{atr_pct:.1f}%")
        if ma20_below_days:
            decision_factors.append(f"连续{ma20_below_days}天收盘低于各自MA20")
        if profit_rate is not None:
            decision_factors.append(f"当前持仓收益{profit_rate * 100:.1f}%")
        decision_factors.append(market_data["market_reason"])
        if stop_loss_triggered:
            decision_factors.append("触发ATR/固定止损风控")
        if not can_add_position:
            decision_factors.append("仓位已接近上限")

        action = "HOLD"
        buy_signal = False
        sell_signal = False
        ai_signal = "HOLD"

        if not has_position:
            if cooldown_remaining > 0:
                reason = f"冷却期剩余{cooldown_remaining}天，暂停买入"
            elif buy_score >= 70 and market_data["market_filter"] != "BLOCK":
                adjusted_buy_ratio = buy_ratio * (0.7 if market_data["market_filter"] == "CAUTION" else 1)
                action = f"BUY_{int(adjusted_buy_ratio * 100)}"
                reason = f"买入评分{buy_score}，趋势/动量/市场过滤满足试仓条件"
                buy_signal = True
                ai_signal = "BUY"
            else:
                reason = f"买入评分{buy_score}未达阈值或市场过滤偏谨慎，继续观察"
        else:
            if stop_loss_triggered or (profit_rate is not None and profit_rate <= stop_loss and current_price < ma20):
                action = "SELL_ALL"
                reason = f"卖出评分{sell_score}，触发动态止损或固定止损"
                sell_signal = True
                ai_signal = "SELL"
            elif sell_score >= 78 and profit_rate is not None and profit_rate < 0:
                action = "SELL_ALL"
                reason = f"卖出评分{sell_score}，亏损叠加趋势/市场风险"
                sell_signal = True
                ai_signal = "SELL"
            elif sell_score >= 75:
                action = "SELL_PARTIAL"
                reason = f"卖出评分{sell_score}，风险升高或达到止盈区，建议减仓"
                sell_signal = True
                ai_signal = "REDUCE"
            elif buy_score >= 75 and profit_rate is not None and profit_rate >= add_profit_threshold and can_add_position and market_data["market_filter"] != "BLOCK":
                adjusted_add_ratio = add_ratio * (0.7 if market_data["market_filter"] == "CAUTION" else 1)
                action = f"ADD_{int(adjusted_add_ratio * 100)}"
                reason = f"买入评分{buy_score}，盈利{profit_rate * 100:.1f}%且未超过仓位上限，可加仓"
                buy_signal = True
                ai_signal = "ADD"
            else:
                reason = f"持仓中，买入评分{buy_score}/卖出评分{sell_score}，暂不操作"

        ai_confidence = round(max(buy_score, sell_score, 100 - risk_score) / 100, 2)
        if risk_score >= 70:
            ai_risk_level = "HIGH"
        elif risk_score >= 45:
            ai_risk_level = "MEDIUM"
        else:
            ai_risk_level = "LOW"
        ai_summary = f"{symbol.upper()} {ai_signal}：评分{signal_score}，风险{ai_risk_level}，{reason}"

        score_breakdown = {
            "trend_score": trend_score,
            "volume_score": volume_score,
            "momentum_score": momentum_score,
            "position_score": position_score,
            "market_score": market_score,
            "risk_score": risk_score,
        }
        technical_snapshot = {
            "ma5": round(ma5, 3) if ma5 else None,
            "ma10": round(ma10, 3) if ma10 else None,
            "ma20": round(ma20, 3) if ma20 else None,
            "rsi": round(rsi, 2) if rsi is not None else None,
            "atr": round(atr, 4) if atr else None,
            "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
            "volume_ratio": volume_ratio,
            "trend_strength": trend_strength,
            "breakout_quality": breakout_data["breakout_quality"],
            "market_filter": market_data["market_filter"],
        }

        return {
            "trend": trend,
            "trend_strength": trend_strength,
            "trend_level": trend_level,
            "pullback": pullback,
            "sentiment": sentiment,
            "volume_signal": volume_signal,
            "breakout": breakout_data["breakout"],
            "breakout_confirm": breakout_data["breakout_confirm"],
            "breakout_strength": breakout_data["breakout_strength"],
            "breakout_quality": breakout_data["breakout_quality"],
            "is_low_position": is_low_position,
            "is_high_position": is_high_position,
            "rise_from_low_pct": round(rise_from_low_pct, 2),
            "action": action,
            "reason": reason,
            "buy_signal": buy_signal,
            "sell_signal": sell_signal,
            "volume_ratio": volume_ratio,
            "consecutive_up_days": consecutive_up_days,
            "ma20_below_days": ma20_below_days,
            "cooldown_days": cooldown_remaining,
            "ma5": round(ma5, 3) if ma5 else None,
            "ma10": round(ma10, 3) if ma10 else None,
            "ma20": round(ma20, 3) if ma20 else None,
            "current_price": round(current_price, 3),
            "change_pct": round(change_pct or 0, 2),
            "prev_high": round(breakout_data["prev_high"], 3) if breakout_data["prev_high"] else None,
            "prev_low": round(breakout_data["prev_low"], 3) if breakout_data["prev_low"] else None,
            "position_size": quantity,
            "avg_cost": round(float(cost), 3) if cost else None,
            "profit_rate": round(profit_rate, 4) if profit_rate is not None else None,
            "position_ratio": round(position_ratio, 4),
            "max_position_ratio": max_position_ratio,
            "can_add_position": can_add_position,
            "rsi": round(rsi, 2) if rsi is not None else None,
            "rsi_signal": rsi_signal,
            "atr": round(atr, 4) if atr else None,
            "atr_pct": round(atr_pct, 2) if atr_pct is not None else None,
            "dynamic_stop_price": round(dynamic_stop_price, 3) if dynamic_stop_price else None,
            "dynamic_stop_loss_pct": round(dynamic_stop_loss_pct, 2) if dynamic_stop_loss_pct is not None else None,
            "stop_loss_triggered": stop_loss_triggered,
            "signal_score": signal_score,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "risk_score": risk_score,
            "trend_score": trend_score,
            "volume_score": volume_score,
            "momentum_score": momentum_score,
            "position_score": position_score,
            "market_symbol": market_data["market_symbol"],
            "market_trend": market_data["market_trend"],
            "market_filter": market_data["market_filter"],
            "market_score": market_data["market_score"],
            "market_reason": market_data["market_reason"],
            "market_rsi": market_data["market_rsi"],
            "market_trend_strength": market_data["market_trend_strength"],
            "ai_summary": ai_summary,
            "ai_signal": ai_signal,
            "ai_confidence": ai_confidence,
            "ai_risk_level": ai_risk_level,
            "decision_factors": decision_factors,
            "score_breakdown": score_breakdown,
            "technical_snapshot": technical_snapshot,
            "template_name": template_name,
            "params": params,
        }

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
