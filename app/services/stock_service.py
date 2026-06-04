import yfinance as yf
import requests
import math
import subprocess
import json
import random
from datetime import datetime, timedelta
from typing import Optional


class StockService:
    """Stock data service - supports CN (Tencent/Sina/EastMoney rotation), US/HK (Yahoo Finance)."""

    @staticmethod
    def get_stock_info(symbol: str, market: str = "US") -> dict:
        """Fetch stock info: name, price, change percent."""
        if market == "CN":
            return StockService._get_cn_stock_info(symbol)
        return StockService._get_yahoo_stock_info(symbol, market)

    @staticmethod
    def _get_cn_stock_info(symbol: str) -> dict:
        """Fetch CN (A-share) stock info, rotating between Tencent/Sina/EastMoney to spread load."""
        symbol = symbol.upper().strip()

        if symbol == "000300":
            prefix = "sh"
            secid_prefix = "1"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
            secid_prefix = "0"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"
            secid_prefix = "0"
        else:
            prefix = "sh"
            secid_prefix = "1"

        # Rotate between 3 free sources to avoid rate limiting at 1s refresh
        sources = [
            lambda: StockService._cn_quote_tencent(prefix, symbol),
            lambda: StockService._cn_quote_sina(prefix, symbol),
            lambda: StockService._cn_quote_eastmoney(secid_prefix, symbol),
        ]
        random.shuffle(sources)

        for fn in sources:
            try:
                result = fn()
                if result.get("current_price") and result["current_price"] > 0:
                    return result
            except Exception:
                continue

        raise ValueError(f"Could not fetch CN stock info for {symbol}: all sources failed")

    @staticmethod
    def _cn_quote_tencent(prefix: str, symbol: str) -> dict:
        """Real-time CN stock quote from Tencent Finance."""
        full_code = f"{prefix}{symbol}"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-H", "User-Agent: Mozilla/5.0",
             f"http://qt.gtimg.cn/q={full_code}"],
            capture_output=True, timeout=10
        )
        content = result.stdout.decode("gbk", errors="replace")
        if "~" not in content:
            raise ValueError(f"Invalid Tencent response for {symbol}")

        parts = content.split("~")
        name = parts[1]
        current_price = float(parts[3])
        yesterday_close = float(parts[4])
        if current_price <= 0:
            raise ValueError(f"Tencent returned zero/negative price for {symbol}")

        return {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "previous_price": yesterday_close,
            "price_change": current_price - yesterday_close,
            "price_change_percent": (current_price - yesterday_close) / yesterday_close * 100 if yesterday_close else 0.0,
            "market": "CN",
            "timestamp": datetime.now()
        }

    @staticmethod
    def _cn_quote_sina(prefix: str, symbol: str) -> dict:
        """Real-time CN stock quote from Sina Finance."""
        full_code = f"{prefix}{symbol}"
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-H", "User-Agent: Mozilla/5.0",
             "-H", "Referer: https://finance.sina.com.cn",
             f"http://hq.sinajs.cn/list={full_code}"],
            capture_output=True, timeout=10
        )
        content = result.stdout.decode("gbk", errors="replace")
        # Format: var hq_str_sh600036="name,open,prev_close,price,high,low,...";
        if '="' not in content or content.strip().endswith('=""'):
            raise ValueError(f"Invalid Sina response for {symbol}")

        data = content.split('="')[1].rstrip('";\n')
        fields = data.split(",")
        if len(fields) < 4:
            raise ValueError(f"Short Sina response for {symbol}")

        name = fields[0]
        current_price = float(fields[3])
        yesterday_close = float(fields[2])
        if current_price <= 0:
            raise ValueError(f"Sina returned zero/negative price for {symbol}")

        return {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "previous_price": yesterday_close,
            "price_change": current_price - yesterday_close,
            "price_change_percent": (current_price - yesterday_close) / yesterday_close * 100 if yesterday_close else 0.0,
            "market": "CN",
            "timestamp": datetime.now()
        }

    @staticmethod
    def _cn_quote_eastmoney(secid_prefix: str, symbol: str) -> dict:
        """Real-time CN stock quote from EastMoney API."""
        url = (
            f"http://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid_prefix}.{symbol}"
            f"&fields=f43,f57,f58,f170"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-H", "User-Agent: Mozilla/5.0",
             url],
            capture_output=True, timeout=10
        )
        data = json.loads(result.stdout)
        d = data.get("data") or {}
        if d is None or d.get("f43") is None:
            raise ValueError(f"Invalid EastMoney response for {symbol}")

        # f43 is price * 1000 (e.g. 1968 → 1.968)
        current_price = d["f43"] / 1000
        if current_price <= 0:
            raise ValueError(f"EastMoney returned zero/negative price for {symbol}")
        # f170 is change percent * 100 (e.g. -150 → -1.50%)
        change_pct = (d.get("f170") or 0) / 100
        yesterday_close = current_price / (1 + change_pct / 100) if change_pct != -100 else None

        return {
            "symbol": symbol,
            "name": d.get("f58") or d.get("f57", symbol),
            "current_price": current_price,
            "previous_price": yesterday_close,
            "price_change": current_price - yesterday_close if yesterday_close else None,
            "price_change_percent": change_pct if yesterday_close else 0.0,
            "market": "CN",
            "timestamp": datetime.now()
        }

    @staticmethod
    def _get_cn_secid_prefix(symbol: str) -> str:
        """Determine EastMoney secid prefix (0=Shenzhen, 1=Shanghai) for a CN symbol."""
        if symbol == "000300":
            return "1"
        if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            return "0"
        if symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            return "0"
        return "1"

    @staticmethod
    def _cn_quote_tencent_orderbook(prefix: str, symbol: str) -> dict:
        """5-level order book from Tencent API (fallback for when EastMoney Level-2 unavailable)."""
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-H", "User-Agent: Mozilla/5.0",
             f"http://qt.gtimg.cn/q={prefix}{symbol}"],
            capture_output=True, timeout=10
        )
        content = result.stdout.decode("gbk", errors="replace")
        if "~" not in content:
            raise ValueError(f"Invalid Tencent orderbook response for {symbol}")
        parts = content.split("~")
        if len(parts) < 30:
            raise ValueError(f"Short Tencent orderbook response for {symbol}")

        # Field positions (0-indexed): [9-18] = 买一到买五, [19-28] = 卖一到卖五
        # Pattern: 9=买一价, 10=买一量, 11=买二价, 12=买二量, ...
        bids = []
        bid_total = 0
        for i in range(5):
            try:
                p = float(parts[9 + i * 2])
                v = int(parts[10 + i * 2])
                bids.append({"price": round(p, 4), "volume": v})
                bid_total += v
            except (ValueError, IndexError):
                bids.append({"price": None, "volume": 0})

        asks = []
        ask_total = 0
        for i in range(5):
            try:
                p = float(parts[19 + i * 2])
                v = int(parts[20 + i * 2])
                asks.append({"price": round(p, 4), "volume": v})
                ask_total += v
            except (ValueError, IndexError):
                asks.append({"price": None, "volume": 0})

        total = bid_total + ask_total
        return {
            "asks": asks,
            "bids": bids,
            "ask_total": ask_total,
            "bid_total": bid_total,
            "committee_ratio": round((bid_total - ask_total) / total * 100, 2) if total > 0 else 0.0,
            "committee_diff": bid_total - ask_total,
        }

    @staticmethod
    def _cn_quote_eastmoney_orderbook(secid_prefix: str, symbol: str) -> dict:
        """10-level order book (Level-2) from EastMoney. Fields f11-f50 are used for the book."""
        # Note: f43/f47/f48 in this range are NOT current_price/volume/amount
        # (those are accessed via the snapshot fields, requested separately).
        # Here f43 = 买三价, f47 = 买七价, f48 = 买八价, f50 = 买十量.
        fields = ",".join([f"f{n}" for n in range(11, 51)])
        url = (
            f"http://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid_prefix}.{symbol}&fields={fields}"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "5",
             "-H", "User-Agent: Mozilla/5.0",
             url],
            capture_output=True, timeout=10
        )
        data = json.loads(result.stdout)
        d = data.get("data") or {}
        if not d:
            raise ValueError(f"Empty EastMoney orderbook data for {symbol}")

        # 卖盘: f11-f20 价, f21-f30 量
        asks = []
        ask_total = 0
        for i in range(10):
            price = d.get(f"f{11 + i}")
            volume = d.get(f"f{21 + i}")
            if price is not None and price > 0:
                p = price / 1000  # 价格也是 * 1000
                v = int(volume or 0)
                asks.append({"price": round(p, 4), "volume": v})
                ask_total += v
            else:
                asks.append({"price": None, "volume": 0})

        # 买盘: f31-f40 价, f41-f50 量
        bids = []
        bid_total = 0
        for i in range(10):
            price = d.get(f"f{31 + i}")
            volume = d.get(f"f{41 + i}")
            if price is not None and price > 0:
                p = price / 1000
                v = int(volume or 0)
                bids.append({"price": round(p, 4), "volume": v})
                bid_total += v
            else:
                bids.append({"price": None, "volume": 0})

        total = bid_total + ask_total
        return {
            "asks": asks,
            "bids": bids,
            "ask_total": ask_total,
            "bid_total": bid_total,
            "committee_ratio": round((bid_total - ask_total) / total * 100, 2) if total > 0 else 0.0,
            "committee_diff": bid_total - ask_total,
        }

    @staticmethod
    def _cn_quote_eastmoney_indicators(secid_prefix: str, symbol: str) -> dict:
        """Snapshot indicators: current price, volume, amount, turnover, volume ratio, etc."""
        fields = "f43,f60,f47,f48,f168,f10,f49,f161,f170,f57,f58"
        url = (
            f"http://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid_prefix}.{symbol}&fields={fields}"
        )
        result = subprocess.run(
            ["curl", "-s", "--max-time", "3",
             "-H", "User-Agent: Mozilla/5.0",
             url],
            capture_output=True, timeout=5
        )
        data = json.loads(result.stdout)
        d = data.get("data") or {}
        if not d or d.get("f43") is None:
            raise ValueError(f"Empty EastMoney indicator data for {symbol}")

        current_price = d["f43"] / 1000
        change_pct = (d.get("f170") or 0) / 100
        prev_close = (d.get("f60") or 0) / 1000 if d.get("f60") else None
        return {
            "name": d.get("f58") or d.get("f57") or symbol,
            "current_price": round(current_price, 4),
            "prev_close": round(prev_close, 4) if prev_close else None,
            "price_change_percent": round(change_pct, 2),
            "volume": int(d.get("f47") or 0),  # 手
            "amount": d.get("f48") or 0,  # 元
            "turnover_rate": round((d.get("f168") or 0) / 100, 2),  # 已经是 * 100
            "volume_ratio": round((d.get("f10") or 0) / 100, 2),
            "inner_volume": int(d.get("f49") or 0),  # 内盘
            "outer_volume": int(d.get("f161") or 0),  # 外盘
        }

    @staticmethod
    def get_order_book(symbol: str, market: str = "CN") -> dict:
        """Fetch 10-level order book (Level-2) and real-time indicators.

        Returns a dict combining EastMoney Level-2 order book + snapshot indicators.
        Falls back to Tencent 5-level if EastMoney Level-2 unavailable.
        """
        ts = datetime.now().isoformat()
        if market != "CN":
            return StockService._get_order_book_yahoo(symbol, market, ts)

        symbol = symbol.upper().strip()
        secid_prefix = StockService._get_cn_secid_prefix(symbol)

        # 1) Try EastMoney for snapshot indicators
        indicators = None
        for _ in range(2):
            try:
                indicators = StockService._cn_quote_eastmoney_indicators(secid_prefix, symbol)
                break
            except Exception:
                continue

        # 2) Try EastMoney for 10-level order book
        book_source = "eastmoney_level2"
        book = None
        for _ in range(2):
            try:
                book = StockService._cn_quote_eastmoney_orderbook(secid_prefix, symbol)
                break
            except Exception:
                continue

        # 3) Fallback to Tencent 5-level if EastMoney book failed
        if book is None:
            if symbol == "000300":
                prefix = "sh"
            elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
                prefix = "sz"
            elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
                prefix = "sz"
            else:
                prefix = "sh"
            try:
                book = StockService._cn_quote_tencent_orderbook(prefix, symbol)
                book_source = "tencent_5level"
            except Exception:
                book = {
                    "asks": [{"price": None, "volume": 0}] * 10,
                    "bids": [{"price": None, "volume": 0}] * 10,
                    "ask_total": 0, "bid_total": 0,
                    "committee_ratio": 0.0, "committee_diff": 0,
                }
                book_source = "empty"

        # 4) Pad to 10 levels if source was 5-level
        if book_source == "tencent_5level":
            book["asks"] = list(book["asks"]) + [{"price": None, "volume": 0}] * 5
            book["bids"] = list(book["bids"]) + [{"price": None, "volume": 0}] * 5

        # 5) Combine with indicators
        result = {
            "symbol": symbol,
            "market": "CN",
            "source": book_source,
            "asks": book["asks"],
            "bids": book["bids"],
            "ask_total": book["ask_total"],
            "bid_total": book["bid_total"],
            "committee_ratio": book["committee_ratio"],
            "committee_diff": book["committee_diff"],
            "timestamp": ts,
        }
        if indicators:
            result.update({
                "name": indicators["name"],
                "current_price": indicators["current_price"],
                "prev_close": indicators["prev_close"],
                "price_change_percent": indicators["price_change_percent"],
                "volume": indicators["volume"],
                "amount": indicators["amount"],
                "turnover_rate": indicators["turnover_rate"],
                "volume_ratio": indicators["volume_ratio"],
                "inner_volume": indicators["inner_volume"],
                "outer_volume": indicators["outer_volume"],
            })
        else:
            result.update({
                "name": symbol,
                "current_price": None,
                "prev_close": None,
                "price_change_percent": None,
                "volume": 0,
                "amount": 0.0,
                "turnover_rate": None,
                "volume_ratio": None,
                "inner_volume": 0,
                "outer_volume": 0,
            })
        return result

    @staticmethod
    def _get_order_book_yahoo(symbol: str, market: str, ts: str) -> dict:
        """Order book fallback for non-CN markets (limited data)."""
        empty_book = {
            "asks": [{"price": None, "volume": 0}] * 10,
            "bids": [{"price": None, "volume": 0}] * 10,
            "ask_total": 0, "bid_total": 0,
            "committee_ratio": 0.0, "committee_diff": 0,
        }
        try:
            info = StockService.get_stock_info(symbol, market)
        except Exception:
            info = {}
        return {
            "symbol": symbol,
            "market": market,
            "source": "yahoo_basic",
            **empty_book,
            "name": info.get("name") or symbol,
            "current_price": info.get("current_price"),
            "prev_close": info.get("previous_price"),
            "price_change_percent": info.get("price_change_percent"),
            "volume": 0, "amount": 0.0,
            "turnover_rate": None, "volume_ratio": None,
            "inner_volume": 0, "outer_volume": 0,
            "timestamp": ts,
        }

    @staticmethod
    def get_realtime_extended(symbol: str, market: str = "CN") -> dict:
        """Lightweight real-time indicator fetch for 1s frontend refresh.

        Returns current_price, volume, amount, turnover, etc. but NOT the 10-level book
        (call get_order_book() when book is needed). Faster than get_order_book().
        """
        ts = datetime.now().isoformat()
        if market != "CN":
            try:
                info = StockService.get_stock_info(symbol, market)
                return {
                    "symbol": symbol,
                    "market": market,
                    "name": info.get("name") or symbol,
                    "current_price": info.get("current_price"),
                    "price_change_percent": info.get("price_change_percent"),
                    "prev_close": info.get("previous_price"),
                    "volume": None, "amount": None,
                    "turnover_rate": None, "volume_ratio": None,
                    "inner_volume": None, "outer_volume": None,
                    "timestamp": ts,
                }
            except Exception:
                return {"symbol": symbol, "market": market, "error": "fetch failed"}

        symbol = symbol.upper().strip()
        secid_prefix = StockService._get_cn_secid_prefix(symbol)
        try:
            indicators = StockService._cn_quote_eastmoney_indicators(secid_prefix, symbol)
            return {"symbol": symbol, "market": "CN", **indicators, "timestamp": ts}
        except Exception:
            return {"symbol": symbol, "market": "CN", "error": "fetch failed", "timestamp": ts}

    @staticmethod
    def _get_yahoo_stock_info(symbol: str, market: str = "US") -> dict:
        """Fetch US/HK/KR stock info via Yahoo Finance."""
        full_symbol = StockService._format_symbol(symbol, market)

        try:
            ticker = yf.Ticker(full_symbol)
            info = ticker.info

            # For indices (^XXXXX), info.currentPrice is often None; use history instead
            cp = info.get("currentPrice")
            pp = info.get("previousClose")
            if cp is None:
                hist = ticker.history(period="2d")
                if not hist.empty:
                    cp = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        pp = float(hist["Close"].iloc[-2])
                    elif pp is None:
                        pp = cp
                else:
                    cp = pp if pp is not None else info.get("navPrice")

            if cp is not None and cp <= 0:
                cp = None
            price_change = None
            price_change_pct = None
            if cp is not None and pp is not None and pp != 0:
                price_change = cp - pp
                price_change_pct = price_change / pp * 100

            return {
                "symbol": symbol.upper(),
                "name": info.get("shortName") or info.get("longName") or symbol.upper(),
                "current_price": cp,
                "previous_price": pp,
                "price_change": price_change,
                "price_change_percent": price_change_pct,
                "market": market,
                "timestamp": datetime.now()
            }
        except Exception as e:
            raise ValueError(f"Could not fetch stock info for {symbol}: {str(e)}")

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
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
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
        if symbol == "000300":
            prefix = "sh"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"
        else:
            prefix = "sh"

        # Try Sina first via curl (with retry on empty/blocked response)
        for attempt in range(3):
            try:
                sina_url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{symbol}&scale=240&ma=no&datalen={min(days, 60)}"
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "10",
                     "-H", "User-Agent: Mozilla/5.0",
                     sina_url],
                    capture_output=True, text=True, timeout=15
                )
                if result.stdout and result.stdout.strip().startswith("["):
                    import json
                    data = json.loads(result.stdout)
                    if isinstance(data, list) and len(data) > 0:
                        res = []
                        for item in data[-days:]:
                            res.append({
                                "price": float(item["close"]),
                                "timestamp": datetime.strptime(item["day"], "%Y-%m-%d")
                            })
                        return res
            except Exception:
                pass

        # Fallback to EastMoney via curl
        try:
            if prefix == "sz":
                secid_prefix = "0"
            else:
                secid_prefix = "1"
            
            em_url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params_str = (
                f"secid={secid_prefix}.{symbol}"
                "&fields1=f1,f2,f3,f4,f5,f6"
                "&fields2=f51,f52,f53,f54,f55,f56"
                "&klt=101&fqt=1&end=20500101&lmt=" + str(days)
            )
            result = subprocess.run(
                ["curl", "-s", "--max-time", "15",
                 "-H", "User-Agent: Mozilla/5.0",
                 "-H", "Connection: close",
                 f"{em_url}?{params_str}"],
                capture_output=True, text=True, timeout=20
            )
            if result.stdout and "klines" in result.stdout:
                import json
                data = json.loads(result.stdout)
                klines = (data.get("data") or {}).get("klines") or []
                res = []
                for kline in klines:
                    parts = kline.split(",")
                    res.append({
                        "price": float(parts[2]),
                        "timestamp": datetime.strptime(parts[0], "%Y-%m-%d")
                    })
                return res
        except Exception:
            pass

        # Last resort: Yahoo Finance (works for most CN stocks/ETFs)
        try:
            # Determine Yahoo suffix: .SS for Shanghai, .SZ for Shenzhen
            if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
                yf_suffix = f"{symbol}.SZ"
            elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
                yf_suffix = f"{symbol}.SZ"
            else:
                yf_suffix = f"{symbol}.SS"
            
            ticker = yf.Ticker(yf_suffix)
            # Get enough days plus buffer for timezone offset
            hist = ticker.history(start=(datetime.now() - timedelta(days=days+5)).strftime("%Y-%m-%d"), 
                                  end=datetime.now().strftime("%Y-%m-%d"))
            if not hist.empty:
                result = []
                for dt, row in hist.iterrows():
                    close = float(row["Close"])
                    # Skip rows with NaN/Inf values
                    if math.isnan(close) or math.isinf(close):
                        continue
                    result.append({
                        "price": close,
                        "timestamp": dt.replace(tzinfo=None) if dt.tzinfo else dt
                    })
                if result:
                    return result[-days:]
        except Exception:
            pass

        raise ValueError(f"Could not fetch CN price history for {symbol}: all sources failed")

    @staticmethod
    def _get_cn_price_history_with_volume(symbol: str, days: int = 30) -> list:
        """Fetch CN stock daily kline with volume via Sina (primary) or EastMoney (fallback)."""
        symbol = symbol.upper().strip()

        # Determine Sina prefix
        if symbol == "000300":
            prefix = "sh"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            prefix = "sz"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            prefix = "sz"
        else:
            prefix = "sh"

        # Try Sina first via curl (with retry)
        for attempt in range(3):
            try:
                sina_url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{symbol}&scale=240&ma=no&datalen={min(days, 60)}"
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "10",
                     "-H", "User-Agent: Mozilla/5.0",
                     sina_url],
                    capture_output=True, text=True, timeout=15
                )
                if result.stdout and result.stdout.strip().startswith("["):
                    import json
                    data = json.loads(result.stdout)
                    if isinstance(data, list) and len(data) > 0:
                        res = []
                        for item in data[-days:]:
                            close = float(item["close"])
                            res.append({
                                "price": close,
                                "open": float(item.get("open", close)),
                                "high": float(item.get("high", close)),
                                "low": float(item.get("low", close)),
                                "close": close,
                                "volume": float(item["volume"]),
                                "timestamp": datetime.strptime(item["day"], "%Y-%m-%d")
                            })
                        if res:
                            return res
            except Exception:
                pass

        # Fallback to EastMoney via curl (with retry)
        if symbol == "000300":
            secid_prefix = "1"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            secid_prefix = "0"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            secid_prefix = "0"
        else:
            secid_prefix = "1"

        for attempt in range(3):
            try:
                em_url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
                params_str = (
                    f"secid={secid_prefix}.{symbol}"
                    "&fields1=f1,f2,f3,f4,f5,f6"
                    "&fields2=f51,f52,f53,f54,f55,f56"
                    "&klt=101&fqt=1&end=20500101&lmt=" + str(days)
                )
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "15",
                     "-H", "User-Agent: Mozilla/5.0",
                     "-H", "Connection: close",
                     f"{em_url}?{params_str}"],
                    capture_output=True, text=True, timeout=20
                )
                if result.stdout and "klines" in result.stdout:
                    import json
                    data = json.loads(result.stdout)
                    klines = (data.get("data") or {}).get("klines") or []
                    res = []
                    for kline in klines:
                        parts = kline.split(",")
                        close = float(parts[2])
                        res.append({
                            "price": close,
                            "open": float(parts[1]),
                            "high": float(parts[3]),
                            "low": float(parts[4]),
                            "close": close,
                            "volume": float(parts[5]),
                            "timestamp": datetime.strptime(parts[0], "%Y-%m-%d")
                        })
                    return res[-days:]
            except Exception:
                pass
        # Last resort: use _get_cn_price_history and fill volume with 0
        try:
            simple_hist = StockService._get_cn_price_history(symbol, days)
            if simple_hist:
                return [{"price": r["price"], "open": r["price"],
                         "high": r["price"], "low": r["price"],
                         "close": r["price"], "volume": 0.0,
                         "timestamp": r["timestamp"]} for r in simple_hist]
        except Exception:
            pass
        raise ValueError(f"Could not fetch CN price+volume history for {symbol}: all sources failed")

    @staticmethod
    def get_current_price(symbol: str, market: str = "US") -> float:
        """Quick price lookup."""
        return StockService.get_stock_info(symbol, market)["current_price"]

    @staticmethod
    def get_intraday_klines(symbol: str, market: str = "CN", klt: int = 1, limit: int = 240, beg: str = None) -> list:
        """Fetch intraday minute-level kline data from EastMoney.

        Args:
            symbol: stock/ETF symbol
            market: market code (CN only for now)
            klt: kline type — 1=1min, 5=5min
            limit: max bars to return
            beg: optional start date in YYYYMMDD format for historical data

        Returns:
            list of {open, high, low, close, volume, timestamp}
        """
        if market != "CN":
            return StockService._get_intraday_klines_yahoo(symbol, market, klt, limit, beg)

        symbol = symbol.upper().strip()
        if symbol == "000300":
            secid_prefix = "1"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
            secid_prefix = "0"
        elif symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
            secid_prefix = "0"
        else:
            secid_prefix = "1"

        if beg:
            end_date = beg
            date_params = f"&beg={beg}&end={end_date}"
            lmt = max(limit, 60)
        else:
            end_date = "20500101"
            date_params = ""
            lmt = max(limit, 60)
        em_url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params_str = (
            f"secid={secid_prefix}.{symbol}"
            "&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56"
            f"&klt={klt}&fqt=1&end={end_date}&lmt={lmt}"
            f"{date_params}"
        )

        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["curl", "-s", "--max-time", "15",
                     "-H", "User-Agent: Mozilla/5.0",
                     "-H", "Connection: close",
                     f"{em_url}?{params_str}"],
                    capture_output=True, text=True, timeout=20
                )
                if result.stdout and "klines" in result.stdout:
                    import json
                    data = json.loads(result.stdout)
                    klines = (data.get("data") or {}).get("klines") or []
                    if not klines:
                        continue
                    res = []
                    for kline in klines:
                        parts = kline.split(",")
                        ts_str = parts[0]
                        # Minute data: "2026-05-24 09:31"; daily data: "2026-05-24"
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d")
                        close = float(parts[2])
                        res.append({
                            "open": float(parts[1]),
                            "high": float(parts[3]),
                            "low": float(parts[4]),
                            "close": close,
                            "volume": float(parts[5]),
                            "timestamp": ts,
                        })
                    return res[-limit:]
            except Exception:
                pass

        # Fallback: try Yahoo Finance for historical CN data
        if beg:
            return StockService._get_intraday_klines_yahoo(symbol, "CN", klt, limit, beg)

        return []

    @staticmethod
    def _get_intraday_klines_yahoo(symbol: str, market: str, klt: int, limit: int, beg: str = None) -> list:
        """Fallback: fetch intraday data from Yahoo Finance.

        Args:
            beg: optional target date in YYYYMMDD format for historical data
        """
        full_symbol = StockService._format_symbol(symbol, market)
        # For CN stocks, Yahoo needs .SS (Shanghai) or .SZ (Shenzhen) suffix
        if market == "CN":
            s = symbol.upper().strip()
            if s.startswith(("000", "001", "002", "003", "300", "301", "302")):
                full_symbol = f"{s}.SZ"
            elif s.startswith(("159", "150", "161", "162", "163", "164", "165")):
                full_symbol = f"{s}.SZ"
            else:
                full_symbol = f"{s}.SS"
        interval_map = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "60m"}
        interval = interval_map.get(klt, "5m")
        try:
            ticker = yf.Ticker(full_symbol)

            if beg:
                # Historical: use start/end to get a specific date's data
                target_date = datetime.strptime(beg, "%Y%m%d")
                end_dt = target_date + timedelta(days=1)
                hist = ticker.history(start=target_date, end=end_dt, interval=interval)
                filter_date = target_date.date()
            else:
                hist = ticker.history(period="5d", interval=interval)
                filter_date = datetime.now().date()

            if hist.empty:
                return []
            bars = []
            for ts, row in hist.iterrows():
                close = float(row["Close"])
                if math.isnan(close) or math.isinf(close):
                    continue
                bars.append({
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": close,
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                    "timestamp": ts.to_pydatetime().replace(tzinfo=None) if ts.tzinfo else ts.to_pydatetime(),
                })
            # Filter to target date
            bars = [b for b in bars if b["timestamp"].date() == filter_date]
            return bars[-limit:]
        except Exception:
            return []

    @staticmethod
    def _format_symbol(symbol: str, market: str) -> str:
        """Format ticker symbol per market convention."""
        symbol = symbol.upper().strip()

        if market == "HK" and not symbol.endswith(".HK"):
            symbol = f"{symbol}.HK"
        # Korea KOSPI index needs ^ prefix on Yahoo Finance
        elif market == "KS" and not symbol.startswith("^"):
            symbol = f"^{symbol}"
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
