"""
AI Analysis Service — MiniMax LLM integration for stock analysis.

Features:
- OpenAI-compatible API client for MiniMax
- Prompt builder with technical + news + concept data
- Multi-source news scrapers (EastMoney, Sina Finance, CnInfo)
- Concept/sector hot topic detection
- 30-minute result cache
"""

import json
import time
import threading
import os
import re
import yaml
import requests
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI


# =============================================================================
# Config Loader  (priority: env var > DB > config.yaml > defaults)
# =============================================================================

def clear_ai_cache():
    """Clear analysis cache and reset AI client to pick up new API key."""
    with _cache_lock:
        _analysis_cache.clear()
    AiAnalysisService._client = None


def _load_ai_config() -> dict:
    """Load AI config. Priority: env var > DB > config.yaml > defaults."""

    # Base defaults
    cfg = {"enabled": True, "api_key": "", "base_url": "https://api.minimax.chat/v1",
           "model": "minimax-text-01", "cache_ttl": 1800, "provider": "minimax"}

    # Layer 1: config.yaml
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        if os.path.exists(config_path):
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            ai_cfg = data.get("ai", {})
            cfg.update(ai_cfg)
    except Exception:
        pass

    # Layer 2: Database AppSetting (highest priority after env vars)
    try:
        from app.models import SessionLocal
        from app.models.models import AppSetting
        db = SessionLocal()
        try:
            for field, key in [("api_key", "ai_api_key"), ("model", "ai_model"),
                               ("base_url", "ai_base_url"), ("enabled", "ai_enabled")]:
                row = db.query(AppSetting).filter(AppSetting.key == key).first()
                if row and row.value:
                    if field == "enabled":
                        cfg[field] = row.value.lower() in ("true", "1", "yes")
                    else:
                        cfg[field] = row.value
        finally:
            db.close()
    except Exception:
        pass

    # Layer 3: Environment variables (absolute highest priority)
    if os.environ.get("AI_API_KEY"):
        cfg["api_key"] = os.environ["AI_API_KEY"]
    if os.environ.get("AI_BASE_URL"):
        cfg["base_url"] = os.environ["AI_BASE_URL"]
    if os.environ.get("AI_MODEL"):
        cfg["model"] = os.environ["AI_MODEL"]

    return cfg


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class NewsItem:
    title: str
    summary: str = ""
    date: str = ""
    source: str = ""


@dataclass
class ConceptTag:
    name: str
    change_pct: float = 0.0
    is_hot: bool = False


@dataclass
class AiAnalysisResult:
    symbol: str
    analysis: str
    news_items: List[NewsItem] = field(default_factory=list)
    concept_tags: List[ConceptTag] = field(default_factory=list)
    generated_at: str = ""
    cached: bool = False
    error: Optional[str] = None


# =============================================================================
# Cache
# =============================================================================

_analysis_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()


def _get_cached(symbol: str, ttl: int = 1800) -> Optional[AiAnalysisResult]:
    with _cache_lock:
        if symbol in _analysis_cache:
            result, ts = _analysis_cache[symbol]
            if time.time() - ts < ttl:
                result.cached = True
                return result
            del _analysis_cache[symbol]
    return None


def _set_cache(symbol: str, result: AiAnalysisResult):
    with _cache_lock:
        _analysis_cache[symbol] = (result, time.time())


# =============================================================================
# EastMoney Data Scrapers
# =============================================================================

def _determine_market_prefix(symbol: str) -> str:
    """Determine EastMoney secid prefix: 0= Shenzhen, 1= Shanghai."""
    if symbol == "000300":
        return "1"
    if symbol.startswith(("000", "001", "002", "003", "300", "301", "302")):
        return "0"
    if symbol.startswith(("159", "150", "161", "162", "163", "164", "165")):
        return "0"
    return "1"


def _fetch_news(symbol: str) -> List[NewsItem]:
    """Fetch recent news for a stock from EastMoney."""
    prefix = _determine_market_prefix(symbol)
    try:
        url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {
            "stock_list": f"{prefix}{symbol}",
            "page_size": 8,
            "page_index": 1,
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://guba.eastmoney.com/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        items = []
        announcements = data.get("data", {}).get("list", [])
        for ann in announcements[:5]:
            items.append(NewsItem(
                title=ann.get("title", ""),
                summary=ann.get("summary", "")[:200] if ann.get("summary") else "",
                date=ann.get("notice_date", "")[:10],
                source="东方财富公告"
            ))
        return items
    except Exception:
        return []


def _fetch_stock_news_fallback(symbol: str, name: str = "") -> List[NewsItem]:
    """Fallback: try EastMoney stock news search."""
    prefix = _determine_market_prefix(symbol)
    try:
        # Try EastMoney stock news API
        url = f"https://search-api-web.eastmoney.com/search/jsonp"
        params = {
            "cb": "jQuery",
            "param": json.dumps({
                "uid": "",
                "keyword": symbol,
                "type": ["8196"],
                "client": "web",
                "source": "web_search",
                "pageIndex": 1,
                "pageSize": 5
            }),
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://so.eastmoney.com/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        # Parse JSONP
        text = r.text
        if text.startswith("jQuery("):
            text = text[7:-1]
        data = json.loads(text)
        items = []
        news_list = data.get("Data", [])
        for n in news_list[:5]:
            items.append(NewsItem(
                title=n.get("Title", ""),
                summary=n.get("Content", "")[:200] if n.get("Content") else "",
                date=n.get("Date", "")[:10],
                source="东方财富新闻"
            ))
        return items
    except Exception:
        return []


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text)


def _fetch_sina_news(keyword: str) -> List[NewsItem]:
    """Fetch stock-related news from Sina Finance."""
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get"
        params = {
            "pageid": "153",
            "lid": "2509",
            "k": keyword,
            "num": 6,
            "page": 1,
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        items = []
        for n in (data.get("result", {}).get("data", []) or [])[:6]:
            ctime = n.get("ctime", "")
            date_str = datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d") if ctime else ""
            items.append(NewsItem(
                title=_strip_html(n.get("title", "")),
                summary=n.get("intro", "")[:200],
                date=date_str,
                source="新浪财经",
            ))
        return items
    except Exception:
        return []


def _fetch_cninfo_news(keyword: str) -> List[NewsItem]:
    """Fetch corporate disclosures from CnInfo (巨潮资讯)."""
    try:
        url = "http://www.cninfo.com.cn/new/fulltextSearch/full"
        params = {
            "searchkey": keyword,
            "sdate": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "edate": datetime.now().strftime("%Y-%m-%d"),
            "isfulltext": "false",
            "sortName": "pubdate",
            "sortType": "desc",
            "pageNum": 1,
            "pageSize": 5,
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "http://www.cninfo.com.cn/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        items = []
        for n in (data.get("announcements", []) or [])[:5]:
            ts = n.get("announcementTime", 0)
            date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else ""
            type_name = n.get("announcementTypeName") or ""
            items.append(NewsItem(
                title=_strip_html(n.get("announcementTitle", "")),
                summary=f"{n.get('secName', '')} {type_name}".strip(),
                date=date_str,
                source="巨潮资讯",
            ))
        return items
    except Exception:
        return []


def _deduplicate_news(news_list: List[NewsItem], threshold: float = 0.65) -> List[NewsItem]:
    """Remove duplicate news items by title similarity. Keeps the first occurrence."""
    seen = []
    for item in news_list:
        is_dup = False
        for s in seen:
            if SequenceMatcher(None, item.title, s.title).ratio() > threshold:
                is_dup = True
                break
        if not is_dup:
            seen.append(item)
    return seen


def _fetch_all_news(symbol: str, name: str = "") -> List[NewsItem]:
    """Fetch news from multiple sources in parallel and merge."""
    keyword = name or symbol
    all_news = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_fetch_news, symbol): "东方财富公告",
            executor.submit(_fetch_stock_news_fallback, symbol, name): "东方财富新闻",
            executor.submit(_fetch_sina_news, keyword): "新浪财经",
            executor.submit(_fetch_cninfo_news, keyword): "巨潮资讯",
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    all_news.extend(result)
            except Exception:
                pass

    # Deduplicate, sort by date descending (empty dates last)
    all_news = _deduplicate_news(all_news)
    all_news.sort(key=lambda x: (x.date if x.date else ""), reverse=True)

    # Ensure source diversity: max 4 per source, then take top 10
    balanced = []
    source_counts: Dict[str, int] = {}
    for item in all_news:
        cnt = source_counts.get(item.source, 0)
        if cnt < 4:
            balanced.append(item)
            source_counts[item.source] = cnt + 1
        if len(balanced) >= 10:
            break
    return balanced


def _fetch_concepts(symbol: str) -> List[ConceptTag]:
    """Fetch concept/sector tags for a stock."""
    prefix = _determine_market_prefix(symbol)
    try:
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax"
        params = {"code": f"{'SZ' if prefix == '0' else 'SH'}{symbol}"}
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        concepts = []
        for item in data[:8] if isinstance(data, list) else []:
            name = item.get("BOARD_NAME", item.get("name", ""))
            if name:
                concepts.append(ConceptTag(name=name, change_pct=0.0))
        return concepts
    except Exception:
        return []


def _fetch_hot_concepts() -> List[ConceptTag]:
    """Fetch currently hot concept boards from EastMoney."""
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "10", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:3",  # concept boards
            "fields": "f2,f3,f4,f12,f14",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        concepts = []
        for item in data.get("data", {}).get("diff", [])[:8]:
            change = item.get("f3", 0)
            concepts.append(ConceptTag(
                name=item.get("f14", ""),
                change_pct=change if change else 0.0,
                is_hot=abs(change) > 2.0,
            ))
        return concepts
    except Exception:
        return []


# =============================================================================
# Prompt Builder
# =============================================================================

SYSTEM_PROMPT = """你是一位专业的A股投资分析师，拥有20年经验。基于提供的技术指标数据、新闻资讯和板块热点，给出客观、全面、有洞察力的分析。

分析要求：
1. **综合研判**：一句话总结当前标的状态和操作建议
2. **技术面分析**：解读趋势、均线、MACD、RSI、布林带等指标的含义和信号
3. **消息面分析**：解读相关新闻对标的的影响。如有多个来源同时报道同一事件，说明信息可信度更高，应重点关注；不同来源的观点分歧也需指出
4. **板块热点**：分析所属概念板块的当前热度和机会
5. **风险提示**：列出主要风险点（技术面+消息面）
6. **操作建议**：基于综合判断给出具体的操作方向和仓位建议

注意：
- 使用简体中文
- 控制总字数在500字以内
- 观点要明确，不要模棱两可
- 风险提示必须具体，不能泛泛而谈
- 如果是ETF，说明其跟踪的指数方向和行业分布"""


def build_prompt(
    symbol: str,
    name: str,
    instrument_type: str,
    signal_data: dict,
    news: List[NewsItem],
    concepts: List[ConceptTag],
    hot_concepts: List[ConceptTag],
) -> str:
    """Build the user prompt for AI analysis."""
    parts = []

    # Basic info
    price = signal_data.get("current_price", "N/A")
    change = signal_data.get("change_pct", 0)
    parts.append(f"## 标的信息")
    parts.append(f"- 代码: {symbol} 名称: {name or symbol} 类型: {instrument_type}")
    parts.append(f"- 当前价格: {price} 涨跌幅: {change:+.2f}%")
    parts.append("")

    # Technical indicators
    parts.append("## 技术面数据")
    trend = signal_data.get("trend", "N/A")
    trend_level = signal_data.get("trend_level", "N/A")
    trend_strength = signal_data.get("trend_strength", 50)
    parts.append(f"- 趋势: {trend} ({trend_level}) 强度: {trend_strength:.0f}/100")
    ma5 = signal_data.get("ma5")
    ma10 = signal_data.get("ma10")
    ma20 = signal_data.get("ma20")
    if ma5 and ma10 and ma20:
        parts.append(f"- 均线: MA5={ma5:.3f} MA10={ma10:.3f} MA20={ma20:.3f}")

    rsi = signal_data.get("rsi")
    if rsi is not None:
        rsi_label = "超买" if rsi > 70 else ("超卖" if rsi < 35 else "正常")
        parts.append(f"- RSI(14): {rsi:.1f} ({rsi_label})")

    macd_hist = signal_data.get("macd_histogram")
    if macd_hist is not None:
        macd_dir = "多头" if macd_hist > 0 else "空头"
        parts.append(f"- MACD: {macd_dir} (柱={macd_hist:.4f})")

    bb_pos = signal_data.get("bollinger_position")
    bb_upper = signal_data.get("bollinger_upper")
    bb_lower = signal_data.get("bollinger_lower")
    if bb_pos is not None:
        if bb_pos > 1.0:
            bb_label = "突破上轨(超强)"
        elif bb_pos > 0.8:
            bb_label = "上轨区域(偏高)"
        elif bb_pos < 0.0:
            bb_label = "跌破下轨(超弱)"
        elif bb_pos < 0.2:
            bb_label = "下轨区域(偏低)"
        else:
            bb_label = "轨道内运行"
        parts.append(f"- 布林带: {bb_label} (位置={bb_pos:.1%}, 带宽={signal_data.get('bollinger_bandwidth', 0):.1%})")

    atr_pct = signal_data.get("atr_pct")
    if atr_pct is not None:
        vol_label = "高波动" if atr_pct > 3 else ("极高波动" if atr_pct > 5 else "正常")
        parts.append(f"- ATR波动率: {atr_pct:.1f}% ({vol_label})")

    vol_ratio = signal_data.get("volume_ratio")
    if vol_ratio is not None:
        parts.append(f"- 量比: {vol_ratio:.2f}")

    weekly = signal_data.get("weekly_trend", "NEUTRAL")
    parts.append(f"- 周线趋势: {weekly}")
    parts.append("")

    # Signal engine
    parts.append("## 信号引擎判断")
    parts.append(f"- 综合信号: {signal_data.get('action', 'N/A')}")
    parts.append(f"- 信号质量: {signal_data.get('signal_quality', 'N/A')}")
    parts.append(f"- 风险等级: {signal_data.get('ai_risk_level', 'N/A')}")
    reason = signal_data.get("reason", "")
    if reason:
        parts.append(f"- 理由: {reason}")
    parts.append("")

    # News (multi-source)
    parts.append("## 相关新闻资讯（多源）")
    if news:
        # Show source summary
        source_counts = Counter(n.source for n in news)
        source_summary = " | ".join(f"{src}: {cnt}条" for src, cnt in source_counts.items())
        parts.append(f"- 来源分布: {source_summary}")
        parts.append("")
        for i, n in enumerate(news, 1):
            parts.append(f"{i}. [{n.date}] [{n.source}] {n.title}")
            if n.summary:
                parts.append(f"   摘要: {n.summary[:150]}")
    else:
        parts.append("（暂无最近新闻数据）")
    parts.append("")

    # Concepts
    parts.append("## 板块概念")
    if concepts:
        concept_names = ", ".join(c.name for c in concepts[:6])
        parts.append(f"- 所属概念: {concept_names}")
    if hot_concepts:
        hot_list = [f"{c.name}({c.change_pct:+.1f}%)" for c in hot_concepts[:5] if c.is_hot]
        if hot_list:
            parts.append(f"- 当前热点板块: {', '.join(hot_list)}")
        else:
            all_hot = [f"{c.name}({c.change_pct:+.1f}%)" for c in hot_concepts[:5]]
            parts.append(f"- 板块涨跌: {', '.join(all_hot)}")
    if not concepts and not hot_concepts:
        parts.append("（暂无板块数据）")
    parts.append("")

    # Market context
    market_filter = signal_data.get("market_filter", "CAUTION")
    market_score = signal_data.get("market_score", 50)
    parts.append(f"## 大盘环境")
    parts.append(f"- 沪深300过滤: {market_filter} (评分={market_score:.0f})")
    parts.append(f"- 市场趋势: {signal_data.get('market_trend', 'NEUTRAL')}")
    parts.append("")

    # Position info
    profit_rate = signal_data.get("profit_rate")
    if profit_rate is not None:
        parts.append(f"## 持仓情况")
        parts.append(f"- 浮动盈亏: {profit_rate*100:+.1f}%")
        parts.append(f"- 止损价: {signal_data.get('dynamic_stop_price', 'N/A')}")
        stop_trig = signal_data.get("stop_loss_triggered", False)
        if stop_trig:
            parts.append("- ⚠️ 止损已触发！")

    prompt = "\n".join(parts)

    # Final instruction
    prompt += "\n\n请给出分析（包含：综合研判、技术面分析、消息面分析、板块热点、风险提示、操作建议）"

    return prompt


# =============================================================================
# MiniMax OpenAI-Compatible Client
# =============================================================================

class MiniMaxClient:
    """OpenAI-compatible client for MiniMax API."""

    def __init__(self, config: dict = None):
        self.config = config or _load_ai_config()
        self.enabled = self.config.get("enabled", False)
        self.client = None
        if self.enabled and self.config.get("api_key"):
            self.client = OpenAI(
                api_key=self.config["api_key"],
                base_url=self.config.get("base_url", "https://api.minimax.chat/v1"),
            )

    def chat(self, system_prompt: str, user_prompt: str, model: str = None) -> Optional[str]:
        """Send a chat completion request and return the response text."""
        if not self.client:
            return None
        model = model or self.config.get("model", "minimax-text-01")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
                extra_body={"reply_constraints": {"sender_type": "BOT", "sender_name": "分析师"}},
            )
            return response.choices[0].message.content
        except Exception as e:
            # Retry without extra_body (some OpenAI-compatible endpoints reject it)
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1500,
                )
                return response.choices[0].message.content
            except Exception as e2:
                raise RuntimeError(f"MiniMax API call failed: {e2}")


# =============================================================================
# Main Analysis Service
# =============================================================================

class AiAnalysisService:
    """Main service for AI-powered stock analysis."""

    _client: Optional[MiniMaxClient] = None

    @classmethod
    def get_client(cls) -> MiniMaxClient:
        if cls._client is None:
            cls._client = MiniMaxClient()
        return cls._client

    @classmethod
    def analyze(
        cls,
        symbol: str,
        name: str = "",
        market: str = "CN",
        instrument_type: str = "ETF",
        signal_data: dict = None,
        force: bool = False,
    ) -> AiAnalysisResult:
        """Run AI analysis for a stock. Cached for 30 minutes unless force=True."""
        config = _load_ai_config()
        ttl = config.get("cache_ttl", 1800)
        cache_key = f"{symbol}:{market}"

        # Check cache
        if not force:
            cached = _get_cached(cache_key, ttl)
            if cached:
                return cached

        # Fetch enrichment data (multi-source news in parallel)
        signal_data = signal_data or {}
        news = _fetch_all_news(symbol, name)
        concepts = _fetch_concepts(symbol)
        hot_concepts = _fetch_hot_concepts()

        # Build prompt
        user_prompt = build_prompt(
            symbol=symbol, name=name, instrument_type=instrument_type,
            signal_data=signal_data, news=news, concepts=concepts, hot_concepts=hot_concepts,
        )

        # Call MiniMax
        analysis = None
        error = None
        if config.get("enabled") and config.get("api_key"):
            try:
                client = cls.get_client()
                analysis = client.chat(SYSTEM_PROMPT, user_prompt)
            except Exception as e:
                error = str(e)
        else:
            error = "AI analysis disabled: configure ai.api_key in config.yaml"

        result = AiAnalysisResult(
            symbol=symbol,
            analysis=analysis or "",
            news_items=news,
            concept_tags=concepts + hot_concepts,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            cached=False,
            error=error,
        )

        # Cache successful results
        if analysis and not error:
            _set_cache(cache_key, result)

        return result
