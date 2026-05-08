#!/bin/bash
cd "$(dirname "$0")"

echo "=== 恢复字体文件 ==="
git checkout -- static/fonts/

echo "=== 重建字体软链接 ==="
ln -sf bootstrap-icons/bootstrap-icons.woff2 static/fonts/bootstrap-icons.woff2
ln -sf bootstrap-icons/bootstrap-icons.woff static/fonts/bootstrap-icons.woff

echo "=== 构建前端 ==="
cd frontend && npm run build

echo "=== 完成 ==="
echo "重启服务: kill \$(pgrep -f 'uvicorn app.main') && cd .. && DATABASE_HOST=192.168.0.12 DATABASE_PORT=35432 DATABASE_NAME=stock_monitor DATABASE_USER=postgres DATABASE_PASSWORD=2342ccbd nohup venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &"
