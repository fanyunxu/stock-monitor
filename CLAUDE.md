# Stock Monitor (盯盘助手)

A web-based stock monitoring and ETF signal management system.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL
- **Frontend**: Vue 3 + Bootstrap 5 + Vite
- **Data**: yfinance, EastMoney API, Tencent Finance API

## Quick Start

```bash
# Create venv and install dependencies
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && npm run build && cd ..

# Create font symlinks
ln -sf frontend/node_modules/bootstrap-icons/font/bootstrap-icons.woff2 static/fonts/
ln -sf frontend/node_modules/bootstrap-icons/font/bootstrap-icons.woff static/fonts/

# Run (set database env vars as needed)
DATABASE_HOST=192.168.0.12 DATABASE_PORT=35432 DATABASE_NAME=stock_monitor \
DATABASE_USER=postgres DATABASE_PASSWORD=xxx \
uvicorn app.main:app --host 0.0.0.0 --port 8000
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
