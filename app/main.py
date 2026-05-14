from fastapi import FastAPI, HTTPException, Body, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import threading
import time
import os
import yaml
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from app.models import Base, engine, SessionLocal, get_db
from app.models.models import AlertRule, Stock, AppSetting
from app.api import alerts, system, etf
from app.services.alert_service import AlertService

# Create database tables
Base.metadata.create_all(bind=engine)

def load_config():
    # Look for config.yaml in the project root (parent of app directory)
    import os
    app_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(app_dir)
    path = os.path.join(root_dir, "config.yaml")
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}

# Global alert checker state
_alert_check_interval = 1  # minutes
_alert_check_running = True
_alert_checker_thread = None

# Log file path
_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "alert_check.log")


def _ensure_log_dir():
    """Create log directory if it doesn't exist."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
    except Exception:
        pass


def _write_check_log(stock_count: int, triggered_count: int, status: str):
    """Write a check log entry and keep only the last 100 lines."""
    try:
        _ensure_log_dir()
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | 检查了 {stock_count} 只股票 | 触发 {triggered_count} 条告警 | {status}\n"

        # Append new line
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        # Prune: keep only last 100 lines
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > 100:
            with open(_LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-100:])
    except Exception as e:
        print(f"[AlertLog] failed to write log: {e}")

def _run_alert_checker_loop(interval_minutes):
    """Background thread that periodically checks alerts."""
    while _alert_check_running:
        try:
            db = SessionLocal()
            try:
                logs = AlertService.check_alerts(db)
                # Count enabled rules with valid stocks (stocks actually checked)
                checked_count = db.query(AlertRule).filter(
                    AlertRule.enabled == True,
                    AlertRule.stock_id != None
                ).join(Stock, AlertRule.stock_id == Stock.id).count()
                _write_check_log(
                    stock_count=checked_count,
                    triggered_count=len(logs),
                    status="OK"
                )
            except Exception as e:
                _write_check_log(0, 0, f"ERROR: {e}")
                raise
            finally:
                db.close()
        except Exception as e:
            print(f"[AlertChecker] error: {e}")
        # Sleep in small increments for fast shutdown
        for _ in range(interval_minutes * 60):
            if not _alert_check_running:
                break
            time.sleep(1)

def _start_alert_checker(interval_minutes):
    global _alert_checker_thread, _alert_check_running
    if interval_minutes <= 0:
        return
    _alert_check_running = True
    _alert_checker_thread = threading.Thread(
        target=_run_alert_checker_loop,
        args=(interval_minutes,),
        daemon=True
    )
    _alert_checker_thread.start()

def _stop_alert_checker():
    global _alert_check_running
    _alert_check_running = False

# Module-level shared state for interval (used by API)
alert_check_interval_state = [1]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load interval from config
    cfg = load_config()
    interval = cfg.get("alert", {}).get("check_interval", 1)
    alert_check_interval_state[0] = interval
    if interval > 0:
        _start_alert_checker(interval)
    yield
    # Shutdown: stop the checker
    _stop_alert_checker()

app = FastAPI(
    title="Stock Monitor (盯盘助手)",
    description="A web-based stock monitoring dashboard",
    version="2.1",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

from app.api import ai

# Include routers
app.include_router(etf.router)
app.include_router(ai.router)


@app.get("/", include_in_schema=False)
def root(request: Request):
    from fastapi.responses import RedirectResponse
    tab = request.query_params.get("tab")
    if tab:
        return RedirectResponse(url=f"/static/index.html?tab={tab}")
    return RedirectResponse(url="/static/index.html")

@app.get("/s")
def simple_shortcut():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/?tab=simple")

@app.get("/idea")
def idea_mode():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/idea.html")

@app.get("/i")
def idea_shortcut():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/idea.html")

@app.get("/p")
def positions_mode():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/positions.html")


@app.get("/api/market/index")
def get_market_index():
    """Get 上证指数 real-time data."""
    import requests
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("http://qt.gtimg.cn/q=sh000001", headers=headers, timeout=10)
        parts = r.text.split("~")
        current_price = float(parts[3])
        yesterday_close = float(parts[4])
        price_change = current_price - yesterday_close
        price_change_percent = (price_change / yesterday_close * 100) if yesterday_close else 0.0
        return {
            "name": parts[1] or "上证指数",
            "current_price": current_price,
            "price_change": price_change,
            "price_change_percent": price_change_percent,
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": app.version}


@app.get("/api/version")
def get_version():
    """Return app version."""
    return {
        "backend_version": app.version,
    }


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db)):
    """Get app settings."""
    interval = alert_check_interval_state[0]
    # Get notification_enabled from DB (default True)
    notify_setting = db.query(AppSetting).filter(AppSetting.key == "notification_enabled").first()
    notification_enabled = True if (notify_setting is None or notify_setting.value != "false") else False
    return {
        "alert_check_interval": interval,
        "notification_enabled": notification_enabled
    }


@app.put("/api/settings")
def update_settings(body: dict = Body(...), db: Session = Depends(get_db)):
    """Update settings: alert_check_interval and/or notification_enabled."""
    interval = body.get("interval")
    notification_enabled = body.get("notification_enabled")

    if interval is not None:
        if interval < 0 or interval > 60:
            raise HTTPException(status_code=400, detail="interval must be 0-60")
        alert_check_interval_state[0] = interval
        _stop_alert_checker()
        if interval > 0:
            _start_alert_checker(interval)

    if notification_enabled is not None:
        setting = db.query(AppSetting).filter(AppSetting.key == "notification_enabled").first()
        if setting is None:
            setting = AppSetting(key="notification_enabled", value="true" if notification_enabled else "false")
            db.add(setting)
        else:
            setting.value = "true" if notification_enabled else "false"
        db.commit()

    return {
        "alert_check_interval": alert_check_interval_state[0],
        "notification_enabled": notification_enabled
    }


@app.get("/api/logs")
def get_check_logs():
    """Return alert check log entries (last 100 lines)."""
    log_path = os.path.join(os.path.dirname(__file__), "logs", "alert_check.log")
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            result.append({
                "timestamp": parts[0].strip(),
                "stock_count": parts[1].strip(),
                "triggered": parts[2].strip(),
                "status": parts[3].strip()
            })
    return result
