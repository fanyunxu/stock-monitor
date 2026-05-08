<template>
  <div>
    <!-- 恢复菜单按钮 -->
    <div class="simple-hint" @click="navState.visible = !navState.visible">
      <i :class="navState.visible ? 'bi bi-chevron-double-up' : 'bi bi-list'"></i>
    </div>

    <!-- 全屏极简内容 -->
    <div class="simple-container">
      <div class="simple-meta">
        <span class="simple-meta-item">
          <i class="bi bi-clock"></i> {{ lastRefresh }}
        </span>
        <span class="simple-meta-item">
          <i class="bi bi-arrow-repeat"></i> {{ countdown }}s
        </span>
      </div>
      <pre id="content">{{ text || '加载中...' }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, inject, onMounted, onUnmounted } from 'vue'

const API = '/api'
const text = ref('')
const countdown = ref(30)
const lastRefresh = ref('—')
let timer = null
let countdownTimer = null

const navState = inject('navState')

function formatTime() {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resetCountdown() {
  countdown.value = 30
}

async function load() {
  try {
    const r = await fetch(`${API}/etf/signals`)
    if (!r.ok) throw new Error(r.statusText)
    const signals = await r.json()

    // 筛选买入信号
    const buys = signals.filter(s => s.buy_signal)

    const header = `📈 ETF 买入信号 (${buys.length})\n${'─'.repeat(40)}`

    if (buys.length === 0) {
      text.value = header + '\n暂无买入信号'
      return
    }

    const lines = buys.map(s => {
      const price = s.current_price != null ? s.current_price.toFixed(3) : '—'
      const change = (s.daily_return != null ? (s.daily_return >= 0 ? '+' : '') + s.daily_return.toFixed(2) + '%' : '—')
      const ma5 = s.ma5 != null ? s.ma5.toFixed(3) : '—'
      const ma10 = s.ma10 != null ? s.ma10.toFixed(3) : '—'
      const ma20 = s.ma20 != null ? s.ma20.toFixed(3) : '—'
      const reason = s.reason || '—'
      return `◆ ${s.name || s.symbol}（${s.symbol}）\n  ${price} ${change} | MA5=${ma5} MA10=${ma10} MA20=${ma20}\n  → ${reason}`
    })

    text.value = [header, ...lines].join('\n')
    lastRefresh.value = formatTime()
    resetCountdown()
  } catch (e) {
    text.value = '加载失败: ' + e.message
  }
}

onMounted(() => {
  navState.visible = false
  load()
  timer = setInterval(load, 30000)
  countdownTimer = setInterval(() => {
    if (countdown.value > 0) countdown.value--
  }, 1000)
})

onUnmounted(() => {
  navState.visible = true
  if (timer) clearInterval(timer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<style scoped>
.simple-hint {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.2rem;
  opacity: 0.6;
  transition: opacity 0.2s;
}
.simple-hint:hover {
  opacity: 1;
}
.simple-container {
  max-width: 800px;
  margin: 20px auto;
  padding: 0 16px;
}
.simple-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-size: 0.85rem;
  color: #888;
}
.simple-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
#content {
  font-family: monospace;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
