# Stock Monitor (盯盘助手) - Specification

## 1. Project Overview

- **Project Name**: 盯盘助手 (Stock Monitor)
- **Type**: Web-based stock monitoring dashboard
- **Core Functionality**: A web application that allows users to manage a stock watchlist, set price alerts based on rise/fall percentage thresholds, and view stock prices with historical trends.
- **Target Users**: Individual investors who want to monitor stock prices and receive alerts on significant price movements.

## 2. Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: Simple HTML/CSS/JS with Bootstrap 5 for styling
- **Database**: PostgreSQL at 192.168.0.12:5432
  - Database name: stock_monitor
  - User: xlx
  - Password: xlx123456
- **Stock Data**: yfinance library for fetching stock prices
- **Docker**: Dockerfile and docker-compose.yml for containerized deployment

## 3. Database Schema

### Table: stocks
| Column    | Type         | Description                    |
|-----------|--------------|--------------------------------|
| id        | SERIAL PRIMARY KEY | Unique identifier         |
| symbol    | VARCHAR(20) UNIQUE NOT NULL | Stock ticker symbol |
| name      | VARCHAR(100) | Company name                   |
| market    | VARCHAR(20)  | Market (US, HK, CN, etc.)      |
| created_at | TIMESTAMP   | Record creation time           |

### Table: alert_rules
| Column          | Type         | Description                           |
|-----------------|--------------|---------------------------------------|
| id              | SERIAL PRIMARY KEY | Unique identifier                |
| stock_id        | INTEGER REFERENCES stocks(id) | Associated stock    |
| alert_type      | VARCHAR(10)  | 'rise' or 'fall'                      |
| threshold_percent | DECIMAL(5,2) | Percentage threshold (e.g., 5.00)    |
| days            | INTEGER      | Number of days to calculate change    |
| enabled         | BOOLEAN      | Whether alert is active               |
| created_at      | TIMESTAMP    | Record creation time                  |

### Table: price_history
| Column    | Type         | Description                    |
|-----------|--------------|--------------------------------|
| id        | SERIAL PRIMARY KEY | Unique identifier         |
| stock_id  | INTEGER REFERENCES stocks(id) | Associated stock    |
| price     | DECIMAL(15,4) | Stock price                   |
| timestamp | TIMESTAMP    | Price timestamp                |

### Table: alert_logs
| Column           | Type         | Description                    |
|------------------|--------------|--------------------------------|
| id               | SERIAL PRIMARY KEY | Unique identifier         |
| stock_id         | INTEGER REFERENCES stocks(id) | Associated stock    |
| alert_rule_id    | INTEGER REFERENCES alert_rules(id) | Associated rule |
| triggered_price  | DECIMAL(15,4) | Price when alert triggered    |
| triggered_at     | TIMESTAMP    | When alert was triggered       |
| acknowledged     | BOOLEAN      | Whether user acknowledged alert|

### Table: etf_watch
| Column           | Type         | Description                    |
|------------------|--------------|--------------------------------|
| id               | SERIAL PRIMARY KEY | Unique identifier         |
| symbol           | VARCHAR(20) UNIQUE NOT NULL | ETF ticker symbol   |
| name             | VARCHAR(100) | ETF name                       |
| market           | VARCHAR(10)  | Market (default CN)            |
| enabled          | BOOLEAN      | Whether ETF is active          |
| initial_capital  | DECIMAL(10,2)| Initial capital (default 2000)|
| created_at       | TIMESTAMP    | Record creation time           |

### Table: etf_signals
| Column              | Type         | Description                    |
|---------------------|--------------|--------------------------------|
| id                  | SERIAL PRIMARY KEY | Unique identifier         |
| etf_watch_id        | INTEGER REFERENCES etf_watch(id) | Associated ETF |
| signal_date         | TIMESTAMP    | Date of signal calculation     |
| trend               | VARCHAR(10)  | 'UP' or 'DOWN'                 |
| pullback            | BOOLEAN      | Whether price is at pullback   |
| sentiment           | VARCHAR(20)  | 'NORMAL' or 'OVERHEAT'         |
| buy_signal          | BOOLEAN      | Buy signal triggered           |
| sell_signal         | BOOLEAN      | Sell signal triggered           |
| action              | VARCHAR(50)  | Action suggestion              |
| volume_ratio        | DECIMAL(6,3) | Volume ratio vs 5-day avg      |
| consecutive_up_days | INTEGER      | Days of consecutive rise       |
| cumulative_return   | DECIMAL(8,3) | Cumulative return (%)          |
| created_at          | TIMESTAMP    | Record creation time           |

## 4. API Endpoints

### Stocks
- `GET /api/stocks` - List all stocks in watchlist
- `POST /api/stocks` - Add a stock to watchlist
- `DELETE /api/stocks/{symbol}` - Remove a stock from watchlist
- `GET /api/stocks/{symbol}/price` - Get current price for a stock
- `GET /api/stocks/{symbol}/history` - Get price history

### Alert Rules
- `GET /api/alerts` - List all alert rules
- `POST /api/alerts` - Create a new alert rule
- `PUT /api/alerts/{id}` - Update an alert rule
- `DELETE /api/alerts/{id}` - Delete an alert rule
- `POST /api/alerts/{id}/toggle` - Enable/disable an alert rule

### Alert Logs
- `GET /api/alerts/logs` - List alert history
- `POST /api/alerts/logs/{id}/acknowledge` - Acknowledge an alert

### ETF Signals
- `GET /api/etf/watch` - List all watched ETFs
- `POST /api/etf/watch` - Add an ETF to watchlist
- `DELETE /api/etf/watch/{symbol}` - Remove an ETF from watchlist
- `GET /api/etf/signals` - Get signals for all watched ETFs
- `GET /api/etf/signals/{symbol}` - Get latest signal for one ETF (realtime calc)
- `POST /api/etf/signals/refresh-all` - Recalculate and save signals for all ETFs

### Monitoring
- `POST /api/check-alerts` - Trigger alert checking (called by scheduler)

## 5. Features

### Stock Management
- Add stocks by symbol (e.g., AAPL, GOOGL, 00700.HK for HK stocks)
- Auto-fetch stock name when adding
- Remove stocks from watchlist
- View current price and daily change

### Price Alerts
- Set alerts for continuous price rise over N days
- Set alerts for continuous price fall over N days
- Configure threshold percentage (e.g., 5% rise in 3 days)
- Enable/disable alerts without deleting
- Alert triggers are logged and displayed in history

### Dashboard
- Overview of all watched stocks with current prices
- Visual indicators for price changes (green/red)
- Quick access to add/remove stocks
- Alert status summary

### Alert Configuration
- Create alert rules with:
  - Stock selection
  - Alert type (rise/fall)
  - Threshold percentage
  - Days period
- Edit existing alert rules
- Toggle alerts on/off

### Alert History
- List of all triggered alerts
- Timestamp and triggered price
- Acknowledge functionality

## 6. Frontend Pages

### Dashboard (index.html)
- Stock watchlist with current prices
- Price change indicators (color-coded)
- Quick action buttons (remove, view details)
- Alert summary widget

### Add Stock Modal
- Symbol input field
- Market selector
- Add button

### Alert Configuration Page (alerts.html)
- List of alert rules with edit/delete
- Form to create/edit alert rules
- Toggle switches for enable/disable

### Alert History Page (history.html)
- Table of triggered alerts
- Acknowledge button for each
- Filter by stock

## 7. Docker Configuration

### Dockerfile
- Python 3.11-slim base image
- Install PostgreSQL client
- Copy requirements.txt and install dependencies
- Copy application code
- Expose port 8000
- Run with uvicorn

### docker-compose.yml
- Service: app (FastAPI backend)
- Service: db (PostgreSQL - external, not containerized)
- Environment variables for database connection
- Volume for persistent data (optional)
- Port mapping: 8000:8000

## 8. Configuration

All configuration via environment variables or config.yaml:
- Database connection settings
- Server host/port
- Log level

## 9. Acceptance Criteria

1. User can add a stock by symbol and see it in the watchlist
2. User can remove a stock from the watchlist
3. User can create alert rules for rise/fall with threshold and days
4. User can enable/disable alert rules
5. Alert logs are created when conditions are met
6. User can view price history for any stock
7. Dashboard displays all stocks with current prices
8. Docker deployment works with docker-compose up
9. Application connects to PostgreSQL database successfully
10. Price data is fetched using yfinance
