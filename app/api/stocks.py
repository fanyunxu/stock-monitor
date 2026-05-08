from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.models import get_db
from app.models.models import Stock, PriceHistory
from app.schemas.schemas import (
    StockCreate, StockResponse, StockWithPrice,
    StockPriceResponse, PriceHistoryResponse, MessageResponse
)
from app.services.stock_service import StockService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=List[StockWithPrice])
def list_stocks(db: Session = Depends(get_db)):
    """List all stocks with current price from Tencent/Yahoo API."""
    stocks = db.query(Stock).order_by(Stock.created_at.desc()).all()
    result = []
    
    for stock in stocks:
        stock_data = StockWithPrice(
            id=stock.id,
            symbol=stock.symbol,
            name=stock.name,
            market=stock.market,
            created_at=stock.created_at
        )
        
        try:
            info = StockService.get_stock_info(stock.symbol, stock.market)
            stock_data.name = info.get("name") or stock.name
            stock_data.current_price = info["current_price"]
            stock_data.price_change = info.get("price_change")
            if info.get("previous_price") and info["current_price"]:
                stock_data.price_change_percent = (
                    (info["current_price"] - info["previous_price"])
                    / info["previous_price"] * 100
                )
        except Exception:
            stock_data.current_price = None
        
        result.append(stock_data)
    
    return result


@router.get("/text", response_class=PlainTextResponse)
def list_stocks_text(db: Session = Depends(get_db)):
    """List all stocks with technical indicators in plain text format."""
    stocks = db.query(Stock).order_by(Stock.created_at.desc()).all()
    lines = []
    
    for stock in stocks:
        try:
            info = StockService.get_stock_info(stock.symbol, stock.market)
            name = info.get("name") or stock.name
            price = info.get("current_price")
            price_change = info.get("price_change")
            
            if price is not None:
                price_str = f"{price:.3f}"
            else:
                price_str = "N/A"
            
            # Get technical indicators
            try:
                ti = StockService.get_technical_indicators(stock.symbol, stock.market)
            except Exception:
                ti = {}
            
            if price_change is not None and price_change != 0:
                pct = info.get("price_change_percent", 0)
                if price_change > 0:
                    arrow = "▲"
                    change_str = f"+{price_change:.3f} (+{pct:.2f}%)"
                else:
                    arrow = "▼"
                    change_str = f"{price_change:.3f} ({pct:.2f}%)"
            else:
                arrow = "―"
                change_str = "0.000 (0.00%)"
            
            # Build tech indicator string
            if ti.get("ma5"):
                trend = ti.get("trend", "")
                align = ti.get("alignment", "")
                gc = "✚" if ti.get("golden_cross") else ""
                dc = "✖" if ti.get("death_cross") else ""
                ma_str = f" MA5={ti['ma5']} MA10={ti['ma10']} MA20={ti['ma20']} {trend} {align}{gc}{dc}"
            else:
                ma_str = ""
            
            line = f"{name}（{stock.symbol}）：{price_str} {arrow} {change_str}{ma_str}"
            lines.append(line.strip())
        except Exception as e:
            lines.append(f"{stock.name}（{stock.symbol}）：N/A")
    
    return "\n".join(lines)


@router.get("/indicators")
def get_indicators(symbol: str, market: str = "CN", db: Session = Depends(get_db)):
    """Get technical indicators for a specific stock."""
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    try:
        ti = StockService.get_technical_indicators(symbol, market)
        if not ti:
            raise HTTPException(status_code=500, detail="Could not calculate indicators")
        return ti
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=StockResponse)
def add_stock(stock_data: StockCreate, db: Session = Depends(get_db)):
    """Add a stock - fetches name/price from Tencent/Yahoo on creation."""
    existing = db.query(Stock).filter(
        Stock.symbol == stock_data.symbol.upper()
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Stock already in watchlist")
    
    name = stock_data.name
    try:
        info = StockService.get_stock_info(
            stock_data.symbol,
            stock_data.market or "US"
        )
        name = info.get("name") or name
    except Exception:
        pass
    
    stock = Stock(
        symbol=stock_data.symbol.upper(),
        name=name,
        market=stock_data.market or "US"
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    
    return stock


@router.delete("/{symbol}", response_model=MessageResponse)
def remove_stock(symbol: str, db: Session = Depends(get_db)):
    """Remove a stock from watchlist."""
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    db.delete(stock)
    db.commit()
    
    return MessageResponse(message=f"Stock {symbol} removed successfully")


@router.get("/{symbol}/price", response_model=StockPriceResponse)
def get_stock_price(symbol: str, market: str = "US", db: Session = Depends(get_db)):
    """Get current price for a specific stock."""
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    try:
        info = StockService.get_stock_info(symbol, market)
        pct = None
        if info.get("current_price") and info.get("previous_price"):
            pct = (info["current_price"] - info["previous_price"])                   / info["previous_price"] * 100
        
        return StockPriceResponse(
            symbol=stock.symbol,
            name=info.get("name") or stock.name or stock.symbol,
            current_price=info["current_price"],
            previous_price=info.get("previous_price"),
            price_change=info.get("price_change"),
            price_change_percent=pct,
            market=stock.market,
            timestamp=info["timestamp"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/history", response_model=List[PriceHistoryResponse])
def get_price_history(symbol: str, days: int = 30, db: Session = Depends(get_db)):
    """Get price history, stored in DB if available."""
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    cutoff = datetime.now() - timedelta(days=days)
    stored = db.query(PriceHistory).filter(
        PriceHistory.stock_id == stock.id,
        PriceHistory.timestamp >= cutoff
    ).order_by(PriceHistory.timestamp.desc()).all()
    
    if stored:
        return [
            PriceHistoryResponse(
                id=h.id, stock_id=h.stock_id,
                price=float(h.price), timestamp=h.timestamp
            )
            for h in stored
        ]
    
    try:
        history = StockService.get_price_history(symbol, stock.market, days)
        for h in history:
            rec = PriceHistory(
                stock_id=stock.id,
                price=h["price"],
                timestamp=h["timestamp"]
            )
            db.add(rec)
        db.commit()
        
        return [
            PriceHistoryResponse(
                id=i, stock_id=stock.id,
                price=h["price"], timestamp=h["timestamp"]
            )
            for i, h in enumerate(history)
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
