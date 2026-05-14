from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.models import get_db
from app.models.models import AppSetting
from app.services.ai_service import AiAnalysisService, clear_ai_cache

router = APIRouter(prefix="/api/ai", tags=["ai"])


# =============================================================================
# Schemas
# =============================================================================

class AiAnalysisResponse(BaseModel):
    symbol: str
    analysis: str
    news_titles: list = []
    concept_tags: list = []
    hot_concepts: list = []
    generated_at: str
    cached: bool
    error: Optional[str] = None


class AiSettingsResponse(BaseModel):
    api_key: str          # masked: only shows last 4 chars if set
    model: str
    base_url: str
    enabled: bool
    configured: bool      # whether a valid key exists


class AiSettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    enabled: Optional[bool] = None


SETTING_KEYS = {
    "api_key": "ai_api_key",
    "model": "ai_model",
    "base_url": "ai_base_url",
    "enabled": "ai_enabled",
}
DEFAULTS = {
    "api_key": "",
    "model": "minimax-text-01",
    "base_url": "https://api.minimax.chat/v1",
    "enabled": "true",
}


def _read_settings(db: Session) -> dict:
    """Read all AI settings from DB, falling back to defaults."""
    result = {}
    for field, key in SETTING_KEYS.items():
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        result[field] = row.value if row else DEFAULTS[field]
    return result


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "(未配置)"
    return "*" * (len(key) - 4) + key[-4:]


# =============================================================================
# Analysis Endpoints
# =============================================================================

@router.get("/analyze/{symbol}", response_model=AiAnalysisResponse)
def analyze_stock(
    symbol: str,
    name: str = "",
    market: str = "CN",
    instrument_type: str = "ETF",
    force: bool = False,
):
    """Run AI analysis for a stock using MiniMax LLM."""
    result = AiAnalysisService.analyze(
        symbol=symbol.upper(),
        name=name,
        market=market,
        instrument_type=instrument_type,
        signal_data=None,
        force=force,
    )
    if not result.analysis and result.error:
        raise HTTPException(status_code=503, detail=result.error)
    return AiAnalysisResponse(
        symbol=result.symbol,
        analysis=result.analysis,
        news_titles=[n.title for n in result.news_items],
        concept_tags=[{"name": c.name, "change_pct": c.change_pct, "is_hot": c.is_hot}
                       for c in result.concept_tags if c.change_pct != 0.0 or c.name],
        hot_concepts=[{"name": c.name, "change_pct": c.change_pct}
                       for c in result.concept_tags if c.is_hot],
        generated_at=result.generated_at,
        cached=result.cached,
        error=result.error,
    )


@router.post("/analyze/{symbol}")
def analyze_stock_with_data(
    symbol: str,
    body: dict = {},
    name: str = "",
    market: str = "CN",
    instrument_type: str = "ETF",
    force: bool = False,
):
    """POST variant: accepts signal data in request body for richer analysis."""
    signal_data = body.get("signal_data", {})
    result = AiAnalysisService.analyze(
        symbol=symbol.upper(),
        name=name or body.get("name", ""),
        market=market,
        instrument_type=instrument_type or body.get("instrument_type", "ETF"),
        signal_data=signal_data,
        force=force,
    )
    if not result.analysis and result.error:
        raise HTTPException(status_code=503, detail=result.error)
    return {
        "symbol": result.symbol,
        "analysis": result.analysis,
        "news_titles": [n.title for n in result.news_items],
        "concept_tags": [{"name": c.name, "change_pct": c.change_pct, "is_hot": c.is_hot}
                          for c in result.concept_tags],
        "generated_at": result.generated_at,
        "cached": result.cached,
        "error": result.error,
    }


# =============================================================================
# Settings Endpoints
# =============================================================================

@router.get("/settings", response_model=AiSettingsResponse)
def get_ai_settings(db: Session = Depends(get_db)):
    """Get current AI configuration. API key is masked."""
    settings = _read_settings(db)
    return AiSettingsResponse(
        api_key=_mask_key(settings["api_key"]),
        model=settings["model"],
        base_url=settings["base_url"],
        enabled=settings["enabled"].lower() in ("true", "1", "yes"),
        configured=bool(settings["api_key"] and len(settings["api_key"]) >= 8),
    )


@router.put("/settings", response_model=AiSettingsResponse)
def update_ai_settings(data: AiSettingsUpdate, db: Session = Depends(get_db)):
    """Update AI configuration. Only provided fields are changed."""
    update_map = {}
    if data.api_key is not None:
        update_map["api_key"] = data.api_key
    if data.model is not None:
        update_map["model"] = data.model
    if data.base_url is not None:
        update_map["base_url"] = data.base_url
    if data.enabled is not None:
        update_map["enabled"] = "true" if data.enabled else "false"

    if not update_map:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_map.items():
        key = SETTING_KEYS[field]
        row = db.query(AppSetting).filter(AppSetting.key == key).first()
        if row is None:
            row = AppSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value

    db.commit()

    # Clear AI cache so new settings take effect immediately
    clear_ai_cache()

    settings = _read_settings(db)
    return AiSettingsResponse(
        api_key=_mask_key(settings["api_key"]),
        model=settings["model"],
        base_url=settings["base_url"],
        enabled=settings["enabled"].lower() in ("true", "1", "yes"),
        configured=bool(settings["api_key"] and len(settings["api_key"]) >= 8),
    )
