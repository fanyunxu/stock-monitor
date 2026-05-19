<template>
  <div>
    <!-- 全屏极简内容 -->
    <div class="simple-container" @dblclick="hidden = !hidden">
      <div class="simple-meta" v-show="!hidden">
        <span class="simple-meta-item">
          <i class="bi bi-clock"></i> {{ lastRefresh }}
        </span>
        <span class="simple-meta-item">
          <i class="bi bi-arrow-repeat"></i> {{ countdown }}s
        </span>
        <span class="switch-btn" @click="goIdea" title="切换到Idea模式">Idea模式 ↗</span>
      </div>
      <pre id="content" v-show="!hidden">{{ text || '加载中...' }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const API = '/api'
const text = ref('')
const countdown = ref(30)
const lastRefresh = ref('—')
const hidden = ref(false)
let timer = null
let countdownTimer = null

function formatTime() {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resetCountdown() {
  countdown.value = 30
}

function goIdea() {
  window.location.href = '/idea'
}

async function fetchKoreaIndex() {
  try {
    const r = await fetch(`${API}/korea_index`)
    if (!r.ok) throw new Error(r.statusText)
    return await r.json()
  } catch {
    return null
  }
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
    // Fallback: 直接调用腾讯接口获取上证指数
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
    // 并行获取指数和ETF信号
    const [indexData, koreaIndexData, signalsRes] = await Promise.all([
      fetchIndex(),
      fetchKoreaIndex(),
      fetch(`${API}/stocks/signals`).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json() })
    ])

    const signals = signalsRes

    // 持股 ETF（quantity > 0）
    const holdings = signals.filter(s => s.quantity && s.quantity > 0)

    // 买入信号
    const buys = signals.filter(s => s.buy_signal)

    // 构建文本
    const lines = []

    // 上证指数
    if (indexData) {
      const idxChange = indexData.change >= 0 ? `+${indexData.change.toFixed(2)}%` : `${indexData.change.toFixed(2)}%`
      lines.push(`${indexData.name} ${indexData.price} ${idxChange}`)
    }

    // 韩指
    if (koreaIndexData) {
      const kChange = koreaIndexData.change >= 0 ? `+${koreaIndexData.change.toFixed(2)}%` : `${koreaIndexData.change.toFixed(2)}%`
      lines.push(`${koreaIndexData.name} ${koreaIndexData.price} ${kChange}`)
    }

    // 关注
    if (holdings.length > 0) {
      lines.push(`📦 关注 (${holdings.length})`)
      lines.push('─'.repeat(40))
      holdings.forEach(s => {
        const price = s.current_price != null ? s.current_price.toFixed(3) : '—'
        const change = s.daily_return != null
          ? (s.daily_return >= 0 ? `+${s.daily_return.toFixed(2)}%` : `${s.daily_return.toFixed(2)}%`)
          : '—'
        const profit = s.profit_loss != null
          ? (s.profit_loss >= 0 ? `+${s.profit_loss.toFixed(0)}` : `${s.profit_loss.toFixed(0)}`)
          : '—'
        lines.push(`${s.name || s.symbol}（${s.symbol}）${price} ${change} | ${profit}元`)
      })
    }

    // 重点关注
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
    // Use cached data time instead of frontend time
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
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<style scoped>
body {
  background: #2b2b2b;
}
.simple-hint {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 9999;
  background: #3c3c3c;
  color: #afafaf;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  border: 1px solid #505050;
  transition: opacity 0.2s;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.simple-hint:hover {
  background: #4c4c4c;
  color: #d0d0d0;
}
.simple-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 16px;
  background: #2b2b2b;
  border-radius: 0;
  border: none;
  min-height: 100vh;
}
.simple-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 0;
  font-size: 0.8rem;
  color: #6a6a6a;
  border-bottom: 1px solid #3c3c3c;
  padding: 10px 0;
}
.simple-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.switch-btn {
  margin-left: auto;
  cursor: pointer;
  color: #6a6a6a;
  font-size: 0.8rem;
  text-decoration: none;
  transition: color 0.2s;
}
.switch-btn:hover {
  color: #d4d4d4;
}
#content {
  font-family: "JetBrains Mono", "Fira Code", "Consolas", "Monaco", monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  color: #d4d4d4;
  background: transparent;
}
</style>
