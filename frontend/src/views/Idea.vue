<template>
  <div class="idea-container" @dblclick="hidden = !hidden">
    <div class="idea-meta" v-show="!hidden">
      <span><i class="icon-clock"></i> {{ lastRefresh }}</span>
      <span><i class="icon-refresh"></i> {{ countdown }}s</span>
      <span class="switch-btn" @click="goSimple" title="切换到极简模式">极简模式 ↗</span>
    </div>
    <pre id="content" v-show="!hidden">{{ text || '加载中...' }}</pre>
    <pre id="decoy" v-show="hidden">{{ fakeLog }}</pre>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const API = '/api'
const text = ref('')
const countdown = ref(30)
const lastRefresh = ref('—')
const hidden = ref(false)
const fakeLog = ref('')
let timer = null
let countdownTimer = null
let logTimer = null

function formatTime() {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resetCountdown() {
  countdown.value = 30
}

function goSimple() {
  window.location.href = '/?tab=simple'
}

const logTemplates = [
  '[INFO] 正在编译模块...',
  '[INFO] 依赖解析完成，耗时 1.2s',
  '[DEBUG] 加载配置: /etc/app/config.yaml',
  '[INFO] 数据库连接池初始化成功',
  '[WARN] 缓存命中率 67%，建议扩容',
  '[INFO] Worker #3 启动完成，PID: 18420',
  '[DEBUG] 收到心跳包，间隔 30s',
  '[INFO] 任务队列已满，暂缓调度',
  '[DEBUG] GC 回收完成，释放 128MB',
  '[INFO] 健康检查通过',
  '[DEBUG] 加载插件: auth-hmac v2.1',
  '[WARN] 磁盘使用率 78%，注意清理',
  '[INFO] 备份任务完成，耗时 45s',
  '[DEBUG] 解析命令行参数...',
  '[INFO] 服务监听端口 8080',
  '[DEBUG] 连接 Redis 集群...',
  '[INFO] 缓存预热完成',
  '[WARN] 请求超时 3 次，已重试',
  '[DEBUG] 写入日志到 /var/log/app.log',
  '[INFO] 热更新检测到新版本 v1.2.3',
]

let logLines = []

function addLogLine() {
  const now = new Date()
  const ts = now.toTimeString().slice(0, 8)
  const msg = logTemplates[Math.floor(Math.random() * logTemplates.length)]
  logLines.push(`${ts} ${msg}`)
  if (logLines.length > 12) logLines.shift()
  fakeLog.value = logLines.join('\n')
}

function startFakeLog() {
  logLines = []
  fakeLog.value = ''
  addLogLine()
  logTimer = setInterval(addLogLine, 2000 + Math.random() * 3000)
}

function stopFakeLog() {
  if (logTimer) { clearInterval(logTimer); logTimer = null }
}

async function fetchIndex() {
  try {
    const r = await fetch(`${API}/stocks/000001`)
    if (!r.ok) throw new Error(r.statusText)
    const data = await r.json()
    return {
      name: data.name || '上证指数',
      price: data.current_price,
      change: data.price_change_percent
    }
  } catch {
    try {
      const r = await fetch(`http://qt.gtimg.cn/q=sh000001`)
      if (!r.ok) throw new Error()
      const content = await r.text()
      const parts = content.split('~')
      if (parts.length > 4) {
        const price = parseFloat(parts[3])
        const yesterday = parseFloat(parts[4])
        const change = ((price - yesterday) / yesterday * 100).toFixed(2)
        return {
          name: '上证指数',
          price: price.toFixed(2),
          change: parseFloat(change)
        }
      }
    } catch {}
    return null
  }
}

async function load() {
  try {
    const [indexData, signalsRes] = await Promise.all([
      fetchIndex(),
      fetch(`${API}/stocks/signals`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json() })
    ])

    const signals = signalsRes
    const buys = signals.filter(s => s.buy_signal)

    const lines = []

    if (indexData) {
      const idxChange = indexData.change >= 0 ? `+${indexData.change.toFixed(2)}%` : `${indexData.change.toFixed(2)}%`
      lines.push(`${indexData.name} ${indexData.price} ${idxChange}`)
    }

    lines.push(`重点关注 (${buys.length})`)
    lines.push('─'.repeat(40))

    if (buys.length === 0) {
      lines.push('暂无买入信号')
    } else {
      buys.forEach(s => {
        const price = s.current_price != null ? s.current_price.toFixed(3) : '—'
        const change = s.daily_return != null
          ? (s.daily_return >= 0 ? `+${s.daily_return.toFixed(2)}%` : `${s.daily_return.toFixed(2)}%`)
          : '—'
        lines.push(`${s.name || s.symbol}（${s.symbol}）${price} ${change}`)
      })
    }

    text.value = lines.join('\n')
    const cachedTime = signals.length > 0 ? new Date(signals[0].calculated_at) : null
    lastRefresh.value = cachedTime ? cachedTime.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : formatTime()
    resetCountdown()
  } catch (e) {
    text.value = '加载失败: ' + e.message
  }
}

onMounted(() => {
  load()
  timer = setInterval(load, 30000)
  countdownTimer = setInterval(() => {
    if (countdown.value > 0) countdown.value--
  }, 1000)
  startFakeLog()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (countdownTimer) clearInterval(countdownTimer)
  stopFakeLog()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  background: #3C3F41;
  color: #d4d4d4;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.idea-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 16px;
  background: #3C3F41;
  min-height: 100vh;
}
.idea-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 0;
  font-size: 0.8rem;
  color: #666;
  border-bottom: 1px solid #333;
  padding: 10px 0;
}
.idea-meta span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.switch-btn {
  margin-left: auto;
  cursor: pointer;
  color: #9a9a9a;
  font-size: 0.8rem;
  text-decoration: none;
  transition: color 0.2s;
}
.switch-btn:hover {
  color: #d4d4d4;
}
.icon-clock::before {
  content: "⏱";
}
.icon-refresh::before {
  content: "🔄";
}
#content {
  font-family: "JetBrains Mono", "Fira Code", "Consolas", "Monaco", monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: #d4d4d4;
  background: transparent;
}
#decoy {
  font-family: "JetBrains Mono", "Fira Code", "Consolas", "Monaco", monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: #d4d4d4;
  background: transparent;
}
</style>