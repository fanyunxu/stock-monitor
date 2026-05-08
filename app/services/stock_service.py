import yfinance as yf
import requests
import math
from datetime import datetime
from typing import Optional


class StockService:
    """Stock data service - supports CN (Tencent API), US/HK (Yahoo Finance)."""

    @staticmethod
    def get_stock_info(symbol: str, market: str = "US") -> dict:
        """Fetch stock info: name, price, change percent."""
        if market == "CN":
            return StockService._get_cn_stock_info(symbol)
        return StockService._get_yahoo_stock_info(symbol, market)

    @staticmethod
    def _get_cn_stock_info(symbol: str) -> dict:
        """Fetch CN (A-share) stock info via Tencent Finance API."""
        symbol = symbol.upper().strip()
        
        # Determine exchange prefix
        # 000-003, 300-302: Shenzhen main board / ChiNext
        # 15xxxx-16xxxx: Shenzhen ETF (funds)
        # 002: SME board
        # 001: Shanghai
        if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"  # Shenzhen ETF funds
        else:
            prefix = "sh"  # Shanghai
        
        full_code = f"{prefix}{symbol}"
        
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            url = f"http://qt.gtimg.cn/q={full_code}"
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            
            # Parse Tencent API response
            # Format: v_sz002548="51~金新农~002548~5.18~5.16~5.17~..."
            content = r.text
            if "~" not in content:
                raise ValueError(f"Invalid response for {symbol}")
            
            parts = content.split("~")
            name = parts[1]
            current_price = float(parts[3])
            yesterday_close = float(parts[4])
            
            price_change = current_price - yesterday_close
            price_change_percent = (price_change / yesterday_close * 100) if yesterday_close else 0.0
            
            return {
                "symbol": symbol,
                "name": name,
                "current_price": current_price,
                "previous_price": yesterday_close,
                "price_change": price_change,
                "price_change_percent": price_change_percent,
                "market": "CN",
                "timestamp": datetime.now()
            }
        except Exception as e:
            raise ValueError(f"Could not fetch CN stock info for {symbol}: {str(e)}")

    @staticmethod
    def _get_yahoo_stock_info(symbol: str, market: str = "US") -> dict:
        """Fetch US/HK stock info via Yahoo Finance."""
        full_symbol = StockService._format_symbol(symbol, market)
        
        try:
            ticker = yf.Ticker(full_symbol)
            info = ticker.info
            
            return {
                "symbol": symbol.upper(),
                "name": info.get("shortName") or info.get("longName") or symbol.upper(),
                "current_price": info.get("currentPrice") or info.get("previousClose"),
                "previous_price": info.get("previousClose"),
                "price_change": None,
                "price_change_percent": None,
                "market": market,
                "timestamp": datetime.now()
            }
        except Exception:
            # Fallback: try history
            try:
                ticker = yf.Ticker(full_symbol)
                hist = ticker.history(period="2d")
                if not hist.empty:
                    cp = float(hist["Close"].iloc[-1])
                    pp = float(hist["Close"].iloc[-2]) if len(hist) > 1 else cp
                    return {
                        "symbol": symbol.upper(),
                        "name": symbol.upper(),
                        "current_price": cp,
                        "previous_price": pp,
                        "price_change": None,
                        "price_change_percent": None,
                        "market": market,
                        "timestamp": datetime.now()
                    }
            except Exception:
                pass
            raise ValueError(f"Could not fetch stock info for {symbol}")

    @staticmethod
    def get_price_history(symbol: str, market: str = "US", days: int = 30) -> list:
        """Fetch price history. CN uses EastMoney, US/HK uses Yahoo."""
        if market == "CN":
            return StockService._get_cn_price_history(symbol, days)

        full_symbol = StockService._format_symbol(symbol, market)

        try:
            ticker = yf.Ticker(full_symbol)
            hist = ticker.history(period=f"{days}d")
            return [
                {"price": float(row["Close"]), "timestamp": row.name.to_pydatetime()}
                for _, row in hist.iterrows()
            ]
        except Exception as e:
            raise ValueError(f"Could not fetch price history for {symbol}: {str(e)}")

    @staticmethod
    def get_price_history_with_volume(symbol: str, market: str = "CN", days: int = 30) -> list:
        """
        Fetch price history with volume data.
        Returns list of: {price, volume, timestamp}
        """
        if market == "CN":
            return StockService._get_cn_price_history_with_volume(symbol, days)

        full_symbol = StockService._format_symbol(symbol, market)
        try:
            ticker = yf.Ticker(full_symbol)
            hist = ticker.history(period=f"{days}d")
            return [
                {
                    "price": float(row["Close"]),
                    "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                    "timestamp": row.name.to_pydatetime()
                }
                for _, row in hist.iterrows()
            ]
        except Exception as e:
            raise ValueError(f"Could not fetch price+volume history for {symbol}: {str(e)}")

    @staticmethod
    def _get_cn_price_history(symbol: str, days: int = 30) -> list:
        """Fetch CN stock daily kline via Sina Finance API (fallback to EastMoney)."""
        symbol = symbol.upper().strip()
        
        # Determine Sina prefix
        if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"
        else:
            prefix = "sh"

        # Try Sina first
        try:
            url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                "symbol": f"{prefix}{symbol}",
                "scale": 240,  # daily kline
                "ma": "no",
                "datalen": min(days, 60)
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            if isinstance(data, list) and len(data) > 0:
                result = []
                for item in data[-days:]:
                    result.append({
                        "price": float(item["close"]),
                        "timestamp": datetime.strptime(item["day"], "%Y-%m-%d")
                    })
                return result
        except Exception:
            pass

        # Fallback to EastMoney
        try:
            if prefix == "sz":
                secid_prefix = "0"
            else:
                secid_prefix = "1"
            
            url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                "secid": f"{secid_prefix}{symbol}",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": "101",
                "fqt": "1",
                "end": "20500101",
                "lmt": days
            }
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            klines = data.get("data", {}).get("klines", [])
            result = []
            for kline in klines:
                parts = kline.split(",")
                result.append({
                    "price": float(parts[2]),
                    "timestamp": datetime.strptime(parts[0], "%Y%m%d")
                })
            return result
        except Exception as e:
            raise ValueError(f"Could not fetch CN price history for {symbol}: {str(e)}")

    @staticmethod
    def _get_cn_price_history_with_volume(symbol: str, days: int = 30) -> list:
        """Fetch CN stock daily kline with volume via Sina (primary) or EastMoney (fallback)."""
        symbol = symbol.upper().strip()

        # Determine Sina prefix
        if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"
        else:
            prefix = "sh"

        # Try Sina first (supports ETFs well)
        try:
            url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                "symbol": f"{prefix}{symbol}",
                "scale": 240,
                "ma": "no",
                "datalen": min(days, 60)
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()

            if isinstance(data, list) and len(data) > 0:
                result = []
                for item in data[-days:]:
                    result.append({
                        "price": float(item["close"]),
                        "volume": float(item["volume"]),
                        "timestamp": datetime.strptime(item["day"], "%Y-%m-%d")
                    })
                if result:
                    return result
        except Exception:
            pass

        # Fallback to EastMoney
        if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            secid_prefix = "0"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
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
                "lmt": days
            }
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()

            klines = (data.get("data") or {}).get("klines") or []
            result = []
            for kline in klines:
                parts = kline.split(",")
                result.append({
                    "price": float(parts[2]),
                    "volume": float(parts[5]),
                    "timestamp": datetime.strptime(parts[0], "%Y%m%d")
                })
            return result[-days:]
        except Exception as e:
            raise ValueError(f"Could not fetch CN price+volume history for {symbol}: {str(e)}")

    @staticmethod
    def get_current_price(symbol: str, market: str = "US") -> float:
        """Quick price lookup."""
        return StockService.get_stock_info(symbol, market)["current_price"]

    @staticmethod
    def _format_symbol(symbol: str, market: str) -> str:
        """Format ticker symbol per market convention."""
        symbol = symbol.upper().strip()
        
        if market == "HK" and not symbol.endswith(".HK"):
            symbol = f"{symbol}.HK"
        # CN stocks handled in CN-specific methods
        
        return symbol

    @staticmethod
    def get_technical_indicators(symbol: str, market: str = "CN", days: int = 30) -> dict:
        """Calculate MA5, MA10, MA20, golden/death cross, position vs MA."""
        try:
            history = StockService.get_price_history(symbol, market, days)
        except Exception:
            return {}
        
        if len(history) < 5:
            return {}
        
        prices = [h["price"] for h in history]
        
        # Calculate MAs
        ma5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else None
        ma10 = sum(prices[-10:]) / 10 if len(prices) >= 10 else None
        ma20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else None
        
        # Current price
        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) >= 2 else current_price
        
        # MA position
        above_ma = {}
        if ma5 is not None:
            above_ma["ma5"] = current_price > ma5
        if ma10 is not None:
            above_ma["ma10"] = current_price > ma10
        if ma20 is not None:
            above_ma["ma20"] = current_price > ma20
        
        # Golden/Death cross (MA5 crosses MA10)
        golden_cross = False
        death_cross = False
        if len(prices) >= 11:
            prev_ma5 = sum(prices[-6:-1]) / 5
            prev_ma10 = sum(prices[-11:-1]) / 10
            cur_ma5 = sum(prices[-5:]) / 5
            cur_ma10 = sum(prices[-10:]) / 10
            golden_cross = (prev_ma5 <= prev_ma10) and (cur_ma5 > cur_ma10)
            death_cross = (prev_ma5 >= prev_ma10) and (cur_ma5 < cur_ma10)
        
        # Multi alignment (多头/空头)
        if ma5 is not None and ma10 is not None and ma20 is not None:
            if ma5 > ma10 > ma20:
                alignment = "多头"
            elif ma5 < ma10 < ma20:
                alignment = "空头"
            else:
                alignment = "混乱"
        else:
            alignment = "数据不足"
        
        return {
            "ma5": round(ma5, 3) if ma5 else None,
            "ma10": round(ma10, 3) if ma10 else None,
            "ma20": round(ma20, 3) if ma20 else None,
            "current_price": round(current_price, 3),
            "above_ma": above_ma,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "alignment": alignment,
            "trend": "偏强" if current_price > ma5 else "偏弱" if ma5 else "未知"
        }
