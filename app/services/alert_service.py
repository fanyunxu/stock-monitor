from sqlalchemy.orm import Session
import os
from app.models.models import AlertRule, Stock, PriceHistory, AlertLog, AppSetting
from app.services.stock_service import StockService
from app.services.notification_service import NotificationService
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta


class AlertService:
    # 续警默认阈值：1%
    DEFAULT_FOLLOWUP_THRESHOLD = 1.0

    # A股/港股交易时间（北京时间）
    CN_MARKET_OPEN_HOUR = 9
    CN_MARKET_OPEN_MIN = 30
    CN_MARKET_CLOSE_HOUR = 15
    CN_MARKET_CLOSE_MIN = 0
    # 午间休市
    CN_LUNCH_START_HOUR = 11
    CN_LUNCH_START_MIN = 30
    CN_LUNCH_END_HOUR = 13
    CN_LUNCH_END_MIN = 0

    @staticmethod
    def is_market_open(market: str = "CN") -> bool:
        """判断指定市场当前是否在交易时间内。"""
        now = datetime.now()
        weekday = now.weekday()
        # 周六、周日休市
        if weekday >= 5:
            return False

        if market == "CN":
            # 上午：9:30 - 11:30
            morning_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            morning_end = now.replace(hour=11, minute=30, second=0, microsecond=0)
            # 下午：13:00 - 15:00
            afternoon_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
            afternoon_end = now.replace(hour=15, minute=0, second=0, microsecond=0)

            if morning_start <= now < morning_end:
                return True
            if afternoon_start <= now < afternoon_end:
                return True
            return False

        elif market == "HK":
            # 港股：9:30 - 12:00, 13:00 - 16:00
            morning_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            morning_end = now.replace(hour=12, minute=0, second=0, microsecond=0)
            afternoon_start = now.replace(hour=13, minute=0, second=0, microsecond=0)
            afternoon_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
            if morning_start <= now < morning_end:
                return True
            if afternoon_start <= now < afternoon_end:
                return True
            return False

        elif market == "US":
            # 美股：21:30 - 04:00（北京时间，次日）
            # 简化判断
            hour = now.hour
            if 21 <= hour or hour < 4:
                return True
            return False

        # 未知市场默认开盘
        return True

    @staticmethod
    def check_alerts(db: Session) -> List[AlertLog]:
        """Check all enabled alert rules and trigger if conditions are met."""
        triggered_logs = []
        enabled_rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()

        for rule in enabled_rules:
            try:
                stock = db.query(Stock).filter(Stock.id == rule.stock_id).first()
                if not stock:
                    continue

                # ==========================================
                # 0. 检查是否在交易时间内
                # ==========================================
                if not AlertService.is_market_open(stock.market):
                    continue

                today_str = datetime.now().strftime("%Y-%m-%d")

                # 获取当前价格（用于续警判断）
                newest_price = None
                history = None

                if rule.alert_type in ("rise", "fall"):
                    if rule.days < 1:
                        continue
                    history = StockService.get_price_history(
                        stock.symbol, stock.market, days=rule.days + 1
                    )
                    if len(history) < 2:
                        continue
                    oldest_price = history[0]["price"]
                    newest_price = history[-1]["price"]
                elif rule.alert_type in ("above", "below"):
                    if not rule.target_price:
                        continue
                    info = StockService.get_stock_info(stock.symbol, stock.market)
                    newest_price = info.get("current_price")

                if newest_price is None:
                    continue

                # ==========================================
                # 0.5 价格无变化，跳过（和上次检查的价格相同则跳过）
                # ==========================================
                if (rule.last_checked_price is not None
                        and newest_price == float(rule.last_checked_price)):
                    # 更新检查时间但不触发
                    rule.last_checked_price = newest_price
                    db.commit()
                    continue

                # 更新最后检查价格
                rule.last_checked_price = newest_price

                # ==========================================
                # 1. 处理续警机制（新一天自动重置基准价）
                # ==========================================
                followup_threshold = float(rule.followup_threshold or AlertService.DEFAULT_FOLLOWUP_THRESHOLD)

                # 新一天：重置续警基准价
                if rule.followup_base_date != today_str:
                    rule.followup_base_price = None
                    rule.followup_base_date = today_str

                # ==========================================
                # 2. 检查主预警（趋势/突破）
                # ==========================================
                should_trigger, main_alert_type = AlertService._check_main_alert(
                    db, rule, stock, newest_price, history
                )

                # 主预警触发
                if should_trigger and newest_price is not None:
                    log = AlertLog(
                        stock_id=stock.id,
                        alert_rule_id=rule.id,
                        triggered_price=newest_price,
                        alert_type=rule.alert_type,
                        threshold_percent=rule.threshold_percent,
                        days=rule.days,
                        target_price=rule.target_price,
                        triggered_at=datetime.now(),
                        acknowledged=False,
                        is_followup=False
                    )
                    db.add(log)
                    triggered_logs.append(log)

                    # 设置续警基准价为本次触发价格
                    rule.followup_base_price = newest_price
                    rule.followup_base_date = today_str

                    if rule.alert_type in ("rise", "fall") and history:
                        for h in history:
                            price_record = PriceHistory(
                                stock_id=stock.id,
                                price=h["price"],
                                timestamp=h["timestamp"]
                            )
                            db.add(price_record)

                    # 主预警触发后，跳过续警判断（本次价格已用于主预警）
                    newest_price = None

                # ==========================================
                # 3. 检查续警
                # ==========================================
                if (newest_price is not None
                        and rule.followup_base_price is not None
                        and rule.followup_base_date == today_str):
                    followup_logs = AlertService._check_followup_alert(
                        db, rule, stock, newest_price, followup_threshold
                    )
                    triggered_logs.extend(followup_logs)

            except Exception as e:
                print(f"Error checking alert {rule.id}: {str(e)}")
                continue

        if triggered_logs:
            db.commit()
            notify_setting = db.query(AppSetting).filter(
                AppSetting.key == "notification_enabled"
            ).first()
            if notify_setting is None or notify_setting.value != "false":
                AlertService._send_notification(db, triggered_logs)

        return triggered_logs

    @staticmethod
    def _check_main_alert(db: Session, rule: AlertRule, stock: Stock, newest_price: float,
                           history: List[Dict]) -> Tuple[bool, str]:
        """检查主预警条件，返回 (should_trigger, alert_type)。"""
        should_trigger = False
        alert_type = rule.alert_type

        if rule.alert_type in ("rise", "fall") and history:
            oldest_price = history[0]["price"]
            pct = ((newest_price - oldest_price) / oldest_price) * 100
            if rule.alert_type == "rise" and pct >= float(rule.threshold_percent):
                should_trigger = True
            elif rule.alert_type == "fall" and pct <= -float(rule.threshold_percent):
                should_trigger = True

        elif rule.alert_type in ("above", "below"):
            if newest_price is None:
                return False, alert_type
            if rule.alert_type == "above" and float(newest_price) >= float(rule.target_price):
                should_trigger = True
            elif rule.alert_type == "below" and float(newest_price) <= float(rule.target_price):
                should_trigger = True

        # Cooldown 检查
        if should_trigger and rule.cooldown_minutes and rule.cooldown_minutes > 0:
            recent_log = db.query(AlertLog).filter(
                AlertLog.alert_rule_id == rule.id,
                AlertLog.triggered_at >= datetime.now() - timedelta(minutes=rule.cooldown_minutes)
            ).first()
            if recent_log:
                should_trigger = False

        return should_trigger, alert_type

    @staticmethod
    def _check_followup_alert(db: Session, rule: AlertRule, stock: Stock,
                                newest_price: float, followup_threshold: float) -> List[AlertLog]:
        """检查续警条件。续警从基准价波动 followup_threshold% 即触发。"""
        triggered_logs = []

        base = float(rule.followup_base_price)
        pct_change = abs(newest_price - base) / base * 100

        if pct_change < followup_threshold:
            return triggered_logs

        # 检查 cooldown（续警单独 cooldown，默认 60 分钟）
        cooldown = rule.cooldown_minutes if rule.cooldown_minutes and rule.cooldown_minutes > 0 else 60
        recent = db.query(AlertLog).filter(
            AlertLog.alert_rule_id == rule.id,
            AlertLog.is_followup == True,
            AlertLog.triggered_at >= datetime.now() - timedelta(minutes=cooldown)
        ).first()
        if recent:
            return triggered_logs

        # 检查是否跟上次触发价格相同（避免重复）
        last_log = db.query(AlertLog).filter(
            AlertLog.alert_rule_id == rule.id
        ).order_by(AlertLog.triggered_at.desc()).first()
        if last_log and abs(float(last_log.triggered_price) - newest_price) / newest_price < 0.001:
            return triggered_logs

        # 触发续警
        log = AlertLog(
            stock_id=stock.id,
            alert_rule_id=rule.id,
            triggered_price=newest_price,
            alert_type=rule.alert_type,
            threshold_percent=rule.threshold_percent,
            days=rule.days,
            target_price=rule.target_price,
            triggered_at=datetime.now(),
            acknowledged=False,
            is_followup=True
        )
        db.add(log)
        triggered_logs.append(log)

        # 更新续警基准价
        rule.followup_base_price = newest_price

        return triggered_logs

    @staticmethod
    def _send_notification(db: Session, triggered_logs: List[AlertLog]):
        """Send IYUU notification for triggered alerts."""
        import yaml

        iyuu_token = os.environ.get("IYUU_TOKEN")
        if not iyuu_token:
            try:
                config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
                if os.path.exists(config_path):
                    with open(config_path) as f:
                        cfg = yaml.safe_load(f) or {}
                    iyuu_token = cfg.get("alert", {}).get("iyuu_token")
            except Exception:
                pass

        if not iyuu_token:
            print("[AlertService] No IYUU token configured, skipping notification")
            return

        currency_symbols = {"CN": "¥", "HK": "HK$", "US": "$"}
        alert_type_labels = {
            "rise": "📈 趋势上涨", "fall": "📉 趋势下跌",
            "above": "📈 价格突破上限", "below": "📉 价格突破下限"
        }

        alerts_data = []
        for log in triggered_logs:
            stock = db.query(Stock).filter(Stock.id == log.stock_id).first()
            rule = db.query(AlertRule).filter(AlertRule.id == log.alert_rule_id).first()
            if not stock or not rule:
                continue

            pct = 0.0
            try:
                info = StockService.get_stock_info(stock.symbol, stock.market)
                pct = info.get("price_change_percent", 0)
            except Exception:
                pass

            followup_tag = " [续警]" if log.is_followup else ""
            base_label = alert_type_labels.get(rule.alert_type, rule.alert_type)

            alerts_data.append({
                "symbol": stock.symbol,
                "name": stock.name or "",
                "market": stock.market,
                "alert_type": rule.alert_type,
                "alert_label": base_label + followup_tag,
                "triggered_price": float(log.triggered_price),
                "price_change_percent": pct,
                "threshold_percent": float(rule.threshold_percent),
                "target_price": float(rule.target_price) if rule.target_price else None,
                "days": rule.days,
                "is_followup": log.is_followup,
            })

        if alerts_data:
            NotificationService.send_alert_notification(alerts_data, config={"iyuu_token": iyuu_token})
