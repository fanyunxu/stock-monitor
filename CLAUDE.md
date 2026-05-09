# Stock Monitor (盯盘助手)

A web-based stock monitoring and ETF signal management system.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Vue 3 + Bootstrap 5 + Vite
- **Data**: yfinance, EastMoney API, Tencent Finance API

## Quick Start

```bash
# 一键启动/重启（推荐）
./run.sh

# Access: http://localhost:8000
# Idea mode: http://localhost:8000/idea
```

## Project Structure

```
app/
  api/          # FastAPI routes (stocks, alerts, etf, system)
  models/       # SQLAlchemy models
  schemas/      # Pydantic schemas
  services/     # Business logic (stock_service, etf_signal_service, alert_service)
frontend/
  src/
    views/      # Vue pages (EtfSignals, Simple, Dashboard, Alerts, etc.)
    components/ # Vue components
config.yaml     # App configuration (database, alert settings)
```

## Key Features

- **ETF Signals**: Real-time calculation with MA5/MA10/MA20, volume analysis, trend detection
- **Stock Alerts**: Configurable rise/fall alerts with cooldown and follow-up notifications
- **Simple Mode**: Minimal dark-mode view for `/s` shortcut

## API Endpoints

- `GET /api/etf/signals` - ETF signals (20s cache)
- `GET /api/etf/watch` - Watch list
- `GET /api/stocks/{symbol}` - Stock info
- `PUT /api/settings` - Update alert interval

## Config

`config.yaml` is read from the project root (not from `app/`).
