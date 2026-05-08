# 盯盘助手 (Stock Monitor)

A web-based stock & ETF monitoring dashboard for Chinese A-share and US/HK markets.

**版本**: 后端 v2.1 | 前端 v1.8

## 功能特性

- **股票关注列表** — 支持 A股、美股、港股，实时价格 + 日涨跌
- **价格告警** — 按连续涨跌天数触发，支持微信/IYUU 推送
- **ETF 信号监控** — 28 只 ETF 持仓追踪，趋势/买入/卖出信号自动计算
- **服务器监控** — CPU、内存、磁盘健康状态
- **告警历史** — 触发记录查看与确认

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 + FastAPI |
| 前端 | Vue 3 + Vite + Bootstrap 5 |
| 数据库 | PostgreSQL |
| 数据源 | yfinance（美股）、AKShare（A 股）|

## 项目结构

```
stock-monitor/
├── app/
│   ├── api/           # API 路由
│   │   ├── alerts.py      # 告警规则 CRUD
│   │   ├── etf.py         # ETF 持仓 & 信号
│   │   ├── stocks.py      # 股票关注列表
│   │   └── system.py      # 系统信息、健康检查
│   ├── models/         # SQLAlchemy 模型
│   ├── schemas/        # Pydantic 请求/响应模型
│   ├── services/       # 业务逻辑
│   │   ├── alert_service.py      # 告警检测
│   │   ├── etf_signal_service.py # ETF 信号计算
│   │   ├── stock_service.py      # 行情获取
│   │   └── notification_service.py # 微信/IYUU 推送
│   └── main.py         # FastAPI 入口
├── frontend/
│   └── src/
│       ├── App.vue         # 根组件（Tab 导航）
│       ├── views/          # 页面视图
│       │   ├── Dashboard.vue    # 首页（股票卡片 + ETF 信号表）
│       │   ├── Alerts.vue       # 告警规则
│       │   ├── EtfSignals.vue   # ETF 信号详情
│       │   ├── History.vue      # 告警历史
│       │   ├── Server.vue       # 服务器监控
│       │   └── Logs.vue         # 运行日志
│       └── components/     # 可复用组件
│           ├── StockCard.vue       # 个股卡片
│           ├── AlertRuleItem.vue   # 告警规则项
│           ├── AlertHistoryItem.vue # 告警历史项
│           ├── ServerInfo.vue      # 服务器信息卡片
│           └── EtfSignalRow.vue    # ETF 信号行
├── static/              # 生产构建产物（后端直接 serve）
├── config.yaml          # 应用配置
├── requirements.txt     # Python 依赖
├── Dockerfile
└── docker-compose.yml
```

## 快速启动

### 1. 配置数据库

确保 PostgreSQL 可用，数据库 `stock_monitor` 已创建。

### 2. 启动后端

```bash
cd stock-monitor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量（或修改 config.yaml）
export DATABASE_HOST=192.168.0.12
export DATABASE_PORT=35432
export DATABASE_NAME=stock_monitor
export DATABASE_USER=postgres
export DATABASE_PASSWORD=2342ccbd

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 前端开发（如需修改 UI）

```bash
cd frontend
npm install
npm run dev      # 开发模式（端口 5173）
npm run build   # 构建产物输出到 ../static/
```

### 4. Docker 部署

```bash
docker-compose up -d
```

访问 **http://localhost:8000**（默认打开 ETF 信号页面）

## 配置文件（config.yaml）

```yaml
database:
  host: "192.168.0.12"
  port: 35432
  name: "stock_monitor"
  user: "postgres"
  password: "2342ccbd"

alert:
  check_interval: 1  # 分钟，0=禁用
  iyuu_token: "YOUR_IYUU_TOKEN"  # IYUU 通知令牌
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_HOST` | 数据库地址 | 192.168.0.12 |
| `DATABASE_PORT` | 数据库端口 | 35432 |
| `DATABASE_NAME` | 数据库名 | stock_monitor |
| `DATABASE_USER` | 用户名 | postgres |
| `DATABASE_PASSWORD` | 密码 | 2342ccbd |

## API 接口

### 股票
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks` | 关注列表（含实时价格） |
| POST | `/api/stocks` | 添加股票 |
| DELETE | `/api/stocks/{symbol}` | 移除股票 |

### 告警规则
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 所有规则 |
| POST | `/api/alerts` | 创建规则 |
| PUT | `/api/alerts/{id}` | 更新规则 |
| DELETE | `/api/alerts/{id}` | 删除规则 |
| POST | `/api/alerts/{id}/toggle` | 启用/禁用 |

### ETF
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/etf/watch` | ETF 持仓列表 |
| POST | `/api/etf/watch` | 添加 ETF |
| PATCH | `/api/etf/watch/{symbol}` | 更新持仓成本/数量 |
| DELETE | `/api/etf/watch/{symbol}` | 删除 ETF |
| GET | `/api/etf/signals` | ETF 信号列表（首页展示） |
| POST | `/api/etf/signals/refresh-all` | 刷新所有信号 |

### 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/version` | 版本信息 |
| GET | `/api/server` | 服务器监控数据 |
| GET | `/health` | 健康检查 |

完整文档访问 **http://localhost:8000/docs**

## 股票代码格式

| 市场 | 示例 | 格式 |
|------|------|------|
| A 股 | 上证 600000 | 600000.SS |
| A 股 | 深证 000001 | 000001.SZ |
| 港股 | 腾讯 00700 | 00700.HK |
| 美股 | 苹果 AAPL | AAPL |

## 页面说明

访问 http://localhost:8000 后，默认进入 **ETF 信号** 页面，左侧导航栏可切换：

- 📊 **控制台** — 股票卡片 + ETF 信号表
- 🔔 **告警规则** — 管理价格告警
- 📈 **ETF 信号** — ETF 完整信号详情
- 📋 **告警历史** — 触发记录
- 🖥️ **服务器监控** — 系统资源
- 📝 **运行日志** — 应用日志
