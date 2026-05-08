from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models import get_db
from app.models.models import AlertRule, Stock, AlertLog
from app.schemas.schemas import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse,
    AlertLogResponse, MessageResponse
)
from app.services.alert_service import AlertService
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

VALID_ALERT_TYPES = {"rise", "fall", "above", "below"}


@router.get("", response_model=List[AlertRuleResponse])
def list_alert_rules(db: Session = Depends(get_db)):
    rules = db.query(AlertRule).order_by(AlertRule.created_at.desc()).all()
    result = []
    for rule in rules:
        stock = db.query(Stock).filter(Stock.id == rule.stock_id).first()
        result.append(AlertRuleResponse(
            id=rule.id,
            stock_id=rule.stock_id,
            alert_type=rule.alert_type,
            threshold_percent=float(rule.threshold_percent),
            days=rule.days,
            target_price=float(rule.target_price) if rule.target_price else None,
            enabled=rule.enabled,
            created_at=rule.created_at,
            stock_symbol=stock.symbol if stock else None,
            stock_name=stock.name if stock else None,
            followup_threshold=float(rule.followup_threshold) if rule.followup_threshold else None,
        ))
    return result


@router.post("", response_model=AlertRuleResponse)
def create_alert_rule(rule_data: AlertRuleCreate, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == rule_data.stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    if rule_data.alert_type not in VALID_ALERT_TYPES:
        raise HTTPException(status_code=400, detail=f"alert_type must be one of: {', '.join(VALID_ALERT_TYPES)}")

    if rule_data.alert_type in ("rise", "fall"):
        if rule_data.threshold_percent <= 0:
            raise HTTPException(status_code=400, detail="threshold_percent must be positive for trend alerts")
        if rule_data.days < 1:
            raise HTTPException(status_code=400, detail="days must be at least 1")
        if rule_data.target_price is not None:
            raise HTTPException(status_code=400, detail="target_price is only for price-break alerts")
    elif rule_data.alert_type in ("above", "below"):
        if rule_data.target_price is None:
            raise HTTPException(status_code=400, detail="target_price is required for price-break alerts")
        if rule_data.threshold_percent != 0:
            raise HTTPException(status_code=400, detail="threshold_percent should be 0 for price-break alerts")

    rule = AlertRule(
        stock_id=rule_data.stock_id,
        alert_type=rule_data.alert_type,
        threshold_percent=rule_data.threshold_percent,
        days=rule_data.days,
        target_price=rule_data.target_price,
        enabled=rule_data.enabled,
        followup_threshold=rule_data.followup_threshold,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return AlertRuleResponse(
        id=rule.id,
        stock_id=rule.stock_id,
        alert_type=rule.alert_type,
        threshold_percent=float(rule.threshold_percent),
        days=rule.days,
        target_price=float(rule.target_price) if rule.target_price else None,
        enabled=rule.enabled,
        created_at=rule.created_at,
        stock_symbol=stock.symbol,
        stock_name=stock.name,
        followup_threshold=float(rule.followup_threshold) if rule.followup_threshold else None,
    )


@router.put("/{rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(rule_id: int, rule_data: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    if rule_data.alert_type is not None:
        if rule_data.alert_type not in VALID_ALERT_TYPES:
            raise HTTPException(status_code=400, detail=f"alert_type must be one of: {', '.join(VALID_ALERT_TYPES)}")
        rule.alert_type = rule_data.alert_type

    if rule_data.threshold_percent is not None:
        rule.threshold_percent = rule_data.threshold_percent

    if rule_data.days is not None:
        rule.days = rule_data.days

    if rule_data.target_price is not None:
        rule.target_price = rule_data.target_price

    if rule_data.enabled is not None:
        rule.enabled = rule_data.enabled

    if rule_data.followup_threshold is not None:
        rule.followup_threshold = rule_data.followup_threshold

    db.commit()
    db.refresh(rule)

    stock = db.query(Stock).filter(Stock.id == rule.stock_id).first()
    return AlertRuleResponse(
        id=rule.id,
        stock_id=rule.stock_id,
        alert_type=rule.alert_type,
        threshold_percent=float(rule.threshold_percent),
        days=rule.days,
        target_price=float(rule.target_price) if rule.target_price else None,
        enabled=rule.enabled,
        created_at=rule.created_at,
        stock_symbol=stock.symbol if stock else None,
        stock_name=stock.name if stock else None,
        followup_threshold=float(rule.followup_threshold) if rule.followup_threshold else None,
    )


@router.delete("/{rule_id}", response_model=MessageResponse)
def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()
    return MessageResponse(message="Alert rule deleted successfully")


@router.delete("/logs/clear_all", response_model=MessageResponse)
def clear_all_alert_logs(db: Session = Depends(get_db)):
    """Delete all alert log records."""
    deleted = db.query(AlertLog).delete()
    db.commit()
    return MessageResponse(message=f"已清空 {deleted} 条告警记录")


@router.post("/{rule_id}/toggle", response_model=AlertRuleResponse)
def toggle_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    rule.enabled = not rule.enabled
    db.commit()
    db.refresh(rule)
    stock = db.query(Stock).filter(Stock.id == rule.stock_id).first()
    return AlertRuleResponse(
        id=rule.id,
        stock_id=rule.stock_id,
        alert_type=rule.alert_type,
        threshold_percent=float(rule.threshold_percent),
        days=rule.days,
        target_price=float(rule.target_price) if rule.target_price else None,
        enabled=rule.enabled,
        created_at=rule.created_at,
        stock_symbol=stock.symbol if stock else None,
        stock_name=stock.name if stock else None,
        followup_threshold=float(rule.followup_threshold) if rule.followup_threshold else None,
    )


@router.get("/logs", response_model=List[AlertLogResponse])
def list_alert_logs(db: Session = Depends(get_db)):
    logs = db.query(AlertLog).order_by(AlertLog.triggered_at.desc()).limit(100).all()
    result = []
    for log in logs:
        stock = db.query(Stock).filter(Stock.id == log.stock_id).first()
        # Get stock name from stock service if not in DB
        stock_name = None
        if stock:
            stock_name = stock.name
            if not stock_name:
                try:
                    info = StockService.get_stock_info(stock.symbol, stock.market)
                    stock_name = info.get("name") or stock.symbol
                except Exception:
                    stock_name = stock.symbol
        result.append(AlertLogResponse(
            id=log.id,
            stock_id=log.stock_id,
            alert_rule_id=log.alert_rule_id,
            triggered_price=float(log.triggered_price),
            triggered_at=log.triggered_at,
            acknowledged=log.acknowledged,
            stock_symbol=stock.symbol if stock else None,
            stock_name=stock_name,
            market=stock.market if stock else None,
            alert_type=log.alert_type,
            threshold_percent=float(log.threshold_percent) if log.threshold_percent else None,
            days=log.days,
            target_price=float(log.target_price) if log.target_price else None,
            is_followup=log.is_followup,
        ))
    return result


@router.post("/logs/{log_id}/acknowledge", response_model=AlertLogResponse)
def acknowledge_alert(log_id: int, db: Session = Depends(get_db)):
    log = db.query(AlertLog).filter(AlertLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Alert log not found")
    log.acknowledged = True
    db.commit()
    db.refresh(log)
    stock = db.query(Stock).filter(Stock.id == log.stock_id).first()
    return AlertLogResponse(
        id=log.id,
        stock_id=log.stock_id,
        alert_rule_id=log.alert_rule_id,
        triggered_price=float(log.triggered_price),
        triggered_at=log.triggered_at,
        acknowledged=log.acknowledged,
        stock_symbol=stock.symbol if stock else None,
        stock_name=stock.name if stock else None,
        market=stock.market if stock else None,
        alert_type=log.alert_type,
        threshold_percent=float(log.threshold_percent) if log.threshold_percent else None,
        days=log.days,
        target_price=float(log.target_price) if log.target_price else None,
        is_followup=log.is_followup,
    )


@router.post("/check-alerts")
def check_alerts(db: Session = Depends(get_db)):
    """Trigger alert checking (for scheduler/cron)."""
    triggered = AlertService.check_alerts(db)
    return {
        "message": f"Checked alerts. {len(triggered)} triggered.",
        "triggered_count": len(triggered)
    }
