# 盯盘助手 (Stock Monitor)

A web-based ETF & stock signal monitoring dashboard for Chinese A-share markets.

**版本**: 后端 v2.2 | 前端 v1.9

---

## 功能特性

- **ETF/股票信号监控** — 支持 A股 ETF 和个股，趋势、买入/卖出信号自动计算
- **持仓管理** — 录入成本价和股数，实时显示盈亏
- **多信号筛选** — 按买入/卖出/观望/持有状态筛选
- **服务器监控** — CPU、内存、磁盘健康状态
- **自动刷新** — 每 30 秒自动刷新信号

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10 + FastAPI |
| 前端 | Vue 3 + Vite + Bootstrap 5 |
| 数据库 | PostgreSQL |
| 数据源 | AKShare（A 股）|

---

## 项目结构

```
stock-monitor/
├── app/
│   ├── api/
│   │   ├── etf.py          # ETF/股票持仓 & 信号（路由: /api/stocks）
│   │   ├── alerts.py       # 告警规则（已废弃，前端未使用）
│   │   └── system.py       # 系统信息、健康检查
│   ├── models/             # SQLAlchemy 模型
│   ├── schemas/            # Pydantic 请求/响应模型
│   ├── services/
│   │   ├── etf_signal_service.py  # ETF 信号计算
│   │   ├── stock_service.py       # 行情获取（AKShare）
│   │   └── notification_service.py # 微信/IYUU 推送
│   └── main.py             # FastAPI 入口
├── frontend/
│   └── src/
│       ├── App.vue              # 根组件（Tab 导航）
│       ├── views/
│       │   ├── Alerts.vue      # 信号页面（主页面）
│       │   ├── EtfSignals.vue   # ETF 信号详情（备用）
│       │   ├── Server.vue       # 服务器监控
│       │   ├── Logs.vue         # 运行日志
│       │   ├── Dashboard.vue    # 控制台
│       │   └── Idea.vue         # 极简模式
│       └── components/
│           └── EtfSignalRow.vue  # 信号行组件
├── static/                 # 前端构建产物（后端直接 serve）
├── config.yaml             # 应用配置
├── requirements.txt        # Python 依赖
├── run.sh                  # 一键启动脚本
└── migrate_add_instrument_type.py  # 数据库迁移
```

---

## 快速启动

### 1. 确认环境

- Python 3.10+
- Node.js 18+
- PostgreSQL（数据库 `stock_monitor` 已存在）

### 2. 启动后端

```bash
cd stock-monitor

# 安装依赖
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启动服务（会自动构建前端）
bash run.sh
```

或者手动启动：

```bash
source venv/bin/activate
export DATABASE_HOST=192.168.0.12
export DATABASE_PORT=35432
export DATABASE_NAME=stock_monitor
export DATABASE_USER=postgres
export DATABASE_PASSWORD=2342ccbd

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 **http://localhost:8000**

### 3. 前端开发

```bash
cd frontend
npm install
npm run dev      # 开发模式（端口 5173）
npm run build     # 构建产物输出到 ../static/
```

---

## 配置文件（config.yaml）

```yaml
database:
  host: "192.168.0.12"
  port: 35432
  name: "stock_monitor"
  user: "postgres"
  password: "2342ccbd"

app:
  host: "0.0.0.0"
  port: 8000
  debug: false

stock:
  default_market: "CN"

alert:
  check_interval: 0  # 告警检查间隔（分钟），0=禁用
  iyuu_token: "YOUR_IYUU_TOKEN"
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_HOST` | 数据库地址 | 192.168.0.12 |
| `DATABASE_PORT` | 数据库端口 | 35432 |
| `DATABASE_NAME` | 数据库名 | stock_monitor |
| `DATABASE_USER` | 用户名 | postgres |
| `DATABASE_PASSWORD` | 密码 | 2342ccbd |

---

## API 接口

> **说明**：项目已移除旧股票列表功能，所有标的（ETF 和个股）统一通过 `/api/stocks` 接口管理。

### 持仓管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks/watch` | 获取所有关注标的 |
| POST | `/api/stocks/watch` | 添加标的到关注列表 |
| PATCH | `/api/stocks/watch/{symbol}` | 更新标的持仓成本/数量 |
| DELETE | `/api/stocks/watch/{symbol}` | 从关注列表移除 |

**添加/更新持仓示例：**
```bash
# 添加
curl -X POST http://localhost:8000/api/stocks/watch \
  -H "Content-Type: application/json" \
  -d '{"symbol": "515700", "market": "CN", "instrument_type": "ETF"}'

# 更新持仓
curl -X PATCH http://localhost:8000/api/stocks/watch/515700 \
  -H "Content-Type: application/json" \
  -d '{"symbol": "515700", "cost": 2.872, "quantity": 300}'
```

### 信号查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks/signals` | 获取所有标的最新信号（含盈亏） |
| GET | `/api/stocks/signals/{symbol}` | 获取单个标的信号 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/version` | 版本信息 |
| GET | `/api/server` | 服务器监控数据 |
| GET | `/api/logs` | 运行日志 |
| GET | `/health` | 健康检查 |

完整 API 文档访问 **http://localhost:8000/docs**

---

## 标的代码格式

| 市场 | 示例 | 格式说明 |
|------|------|----------|
| A 股 ETF | 512480 | 510xxx（沪）/ 159xxx（深） |
| A 股个股 | 600000 / 000001 | 600xxx（沪）/ 000xxx（深） |
| 创业板 ETF | 159915 | 159xxx 为深交所 ETF |

`instrument_type` 字段：`ETF` 或 `STOCK`

---

## 页面说明

访问 http://localhost:8000 后：

- **📊 信号**（默认）— 所有 ETF/股票信号，支持筛选和搜索
- **📈 信号详情** — 完整信号指标（备用）
- **🖥️ 服务器监控** — 系统资源状态
- **📝 运行日志** — 应用日志
- **⚡ 极简模式** — 纯文字版，适合快速浏览
