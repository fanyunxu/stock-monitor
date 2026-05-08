import requests
import os
from typing import List, Dict, Any
from datetime import datetime


class NotificationService:
    """Send alert notifications via configured webhook (e.g. QQ, Telegram, etc.)."""

    @staticmethod
    def send_alert_notification(alerts: List[Dict[str, Any]], config: dict = None) -> bool:
        """Send alert notifications via IYUU webhook."""
        iyuu_token = (config or {}).get("iyuu_token") or os.environ.get("IYUU_TOKEN")
        if not iyuu_token:
            print("[Notification] No IYUU token configured, skipping notification")
            return False

        currency_symbols = {"CN": "¥", "HK": "HK$", "US": "$"}

        all_messages = []
        for alert in alerts:
            symbol = alert.get("symbol", "Unknown")
            name = alert.get("name", "")
            alert_type = alert.get("alert_type", "rise")
            pct = alert.get("price_change_percent", 0)
            price = alert.get("triggered_price", 0)
            threshold = alert.get("threshold_percent", 0)
            days = alert.get("days", 1)
            market = alert.get("market", "CN")
            currency = currency_symbols.get(market, "¥")

            if alert_type == "above":
                direction = "📈 价格突破上限"
                msg = (
                    f"🔔 盯盘告警\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"股票：{symbol} {'(' + name + ')' if name else ''}\n"
                    f"类型：{direction}\n"
                    f"当前价：{currency}{price:.2f}\n"
                    f"目标价格：{currency}{threshold:.2f}\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            elif alert_type == "below":
                direction = "📉 价格突破下限"
                msg = (
                    f"🔔 盯盘告警\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"股票：{symbol} {'(' + name + ')' if name else ''}\n"
                    f"类型：{direction}\n"
                    f"当前价：{currency}{price:.2f}\n"
                    f"目标价格：{currency}{threshold:.2f}\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            elif alert_type == "rise":
                direction = "📈 价格上涨"
                msg = (
                    f"🔔 盯盘告警\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"股票：{symbol} {'(' + name + ')' if name else ''}\n"
                    f"类型：{direction}\n"
                    f"当前价：{currency}{price:.2f}\n"
                    f"变动：{pct:+.2f}%（阈值：{threshold}%，统计{days}天）\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                direction = "📉 价格下跌"
                msg = (
                    f"🔔 盯盘告警\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"股票：{symbol} {'(' + name + ')' if name else ''}\n"
                    f"类型：{direction}\n"
                    f"当前价：{currency}{price:.2f}\n"
                    f"变动：{pct:+.2f}%（阈值：{threshold}%，统计{days}天）\n"
                    f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            all_messages.append(msg)

        # 合并多条消息
        full_message = "\n\n".join(all_messages)

        try:
            resp = requests.post(
                "http://api.iyuu.cn/index.php?s=App.Site.WebHook",
                data={"token": iyuu_token, "msg": full_message},
                timeout=10
            )
            result = resp.json()
            if result.get("ret") == 200:
                print(f"[Notification] ✅ Sent {len(alerts)} alert(s) via IYUU")
                return True
            else:
                print(f"[Notification] ⚠️ IYUU returned {result.get('ret')}: {result.get('msg', '')}")
                return False
        except Exception as e:
            print(f"[Notification] ❌ Failed to send IYUU notification: {e}")
            return False
