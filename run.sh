#!/bin/bash
set -e

cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1"; }

# Check if venv exists
if [ ! -d "venv" ]; then
    error "venv not found, run: virtualenv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Stop existing uvicorn process
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    warn "Stopping existing uvicorn..."
    pkill -f "uvicorn app.main:app"
    sleep 1
fi

# Build frontend
log "Building frontend..."
cd frontend
npm install --silent 2>/dev/null || npm install
npm run build
cd ..

# Copy bootstrap files to static (after build, since emptyOutDir may clear them)
log "Copying bootstrap files..."
cp frontend/node_modules/bootstrap/dist/css/bootstrap.min.css static/ 2>/dev/null || true
cp frontend/node_modules/bootstrap/dist/js/bootstrap.bundle.min.js static/ 2>/dev/null || true
cp frontend/node_modules/bootstrap-icons/font/bootstrap-icons.css static/ 2>/dev/null || true

# Create font symlinks
log "Setting up font symlinks..."
mkdir -p static/fonts
ln -sf ../frontend/node_modules/bootstrap-icons/font/bootstrap-icons.woff2 static/fonts/ 2>/dev/null || true
ln -sf ../frontend/node_modules/bootstrap-icons/font/bootstrap-icons.woff static/fonts/ 2>/dev/null || true

# Start uvicorn
log "Starting uvicorn..."
source venv/bin/activate
export DATABASE_HOST=$(grep -A1 "^database:" config.yaml | grep "host:" | awk -F'"' '{print $2}')
export DATABASE_PORT=$(grep -A1 "^database:" config.yaml | grep "port:" | awk '{print $2}')
export DATABASE_NAME=$(grep -A1 "^database:" config.yaml | grep "name:" | awk -F'"' '{print $2}')
export DATABASE_USER=$(grep -A1 "^database:" config.yaml | grep "user:" | awk -F'"' '{print $2}')
export DATABASE_PASSWORD=$(grep -A1 "^database:" config.yaml | grep "password:" | awk -F'"' '{print $2}')

nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
echo $! > logs/app.pid

sleep 2
if ps -p $(cat logs/app.pid) > /dev/null 2>&1; then
    log "Server started successfully (PID: $(cat logs/app.pid))"
    log "Access: http://localhost:8000"
else
    error "Server failed to start, check logs/app.log"
    exit 1
fi
