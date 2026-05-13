<template>
  <div>
    <div v-if="loading" class="spinner-overlay">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">加载中...</span>
      </div>
    </div>

    <div class="toast-container">
      <div v-for="toast in toasts" :key="toast.id"
           class="toast show align-items-center text-white"
           :class="'bg-' + toast.type" role="alert">
        <div class="d-flex">
          <div class="toast-body">{{ toast.message }}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="removeToast(toast.id)"></button>
        </div>
      </div>
    </div>

    <div class="container mt-4">
      <div class="row mb-4">
        <div class="col-md-4">
          <div class="card text-white bg-primary">
            <div class="card-body">
              <h5 class="card-title"><i class="bi bi-collection me-2"></i>关注列表</h5>
              <h2>{{ stocks.length }}</h2>
              <p class="card-text text-white-50">只股票正在监控</p>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white bg-success">
            <div class="card-body">
              <h5 class="card-title"><i class="bi bi-check-circle me-2"></i>已启用告警</h5>
              <h2>{{ activeAlertCount }}</h2>
              <p class="card-text text-white-50">条规则已启用</p>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white bg-warning">
            <div class="card-body">
              <h5 class="card-title"><i class="bi bi-exclamation-triangle me-2"></i>今日触发</h5>
              <h2>{{ triggeredToday }}</h2>
              <p class="card-text text-white-50">条告警已触发</p>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header d-flex justify-content-between align-items-center">
          <h5 class="mb-0">
            <i class="bi bi-list-check me-2"></i>股票关注列表
          </h5>
          <button class="btn btn-primary btn-sm" @click="showAddStockModal">
            <i class="bi bi-plus-lg me-1"></i>添加股票
          </button>
        </div>
        <div class="card-body p-0">
          <div v-if="stocks.length > 0">
            <div class="row p-3">
              <StockCard
                v-for="stock in stocks"
                :key="stock.id"
                :stock="stock"
                :rule-count="getRuleCount(stock.symbol)"
                :has-triggered="hasTriggered(stock.symbol)"
                @remove="removeStock"
                @view-history="switchTab('history', { stockId: stock.id, stockName: stock.name || stock.symbol })"
                @set-alert="switchTab('alerts', { stock })"
              />
            </div>
          </div>
          <div v-else class="text-center text-muted py-5">
            <i class="bi bi-inbox fs-1"></i>
            <p class="mt-2">关注列表为空，点击「添加股票」开始</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Stock Modal -->
    <div class="modal fade" id="addStockModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-2"></i>添加股票</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label for="stockSymbol" class="form-label">股票代码</label>
              <input v-model="newStock.symbol" type="text" class="form-control" id="stockSymbol" placeholder="如：AAPL、00700.HK、600000">
            </div>
            <div class="mb-3">
              <label for="stockMarket" class="form-label">市场</label>
              <select v-model="newStock.market" class="form-select" id="stockMarket">
                <option value="CN">A股 CNY</option>
                <option value="US">美股 USD</option>
                <option value="HK">港股 HKD</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="addStock">添加</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, inject } from 'vue'
import StockCard from '../components/StockCard.vue'

const API = '/api'
const switchTab = inject('switchTab')

const loading = ref(false)
const stocks = ref([])
const alerts = ref([])
const logs = ref([])
const etfSignals = ref([])
const toasts = ref([])
const refreshInterval = ref(localStorage.getItem('stock_monitor_refresh') || '300')
let refreshTimer = null

const newStock = ref({ symbol: '', market: 'CN' })

const activeAlertCount = computed(() => alerts.value.filter(a => a.enabled).length)
const triggeredToday = computed(() => {
  const today = new Date().toDateString()
  return logs.value.filter(l => new Date(l.triggered_at).toDateString() === today).length
})

function showToast(message, type = 'info') {
  const id = Date.now()
  toasts.value.push({ id, message, type })
  setTimeout(() => removeToast(id), 4000)
}
function removeToast(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

function getSectorBadge(name) {
  if (!name) return 'bg-secondary text-white'
  if (name.includes('航空') || name.includes('航天')) return 'bg-primary text-white'
  if (name.includes('军工')) return 'bg-danger text-white'
  if (name.includes('5G') || name.includes('通信')) return 'bg-info text-dark'
  if (name.includes('半导体') || name.includes('芯片')) return 'bg-dark text-white'
  if (name.includes('人工智能') || name.includes('AI')) return 'bg-success text-white'
  if (name.includes('光伏') || name.includes('电池')) return 'bg-warning text-dark'
  if (name.includes('新能源')) return 'bg-success text-white'
  if (name.includes('稀土')) return 'bg-warning text-dark'
  if (name.includes('碳中和')) return 'bg-info text-dark'
  if (name.includes('电力')) return 'bg-secondary text-white'
  if (name.includes('消费电子') || name.includes('电子')) return 'bg-danger text-white'
  if (name.includes('科创')) return 'bg-primary text-white'
  if (name.includes('养殖')) return 'bg-secondary text-white'
  if (name.includes('TMT')) return 'bg-primary text-white'
  return 'bg-secondary text-white'
}
function getSector(name) {
  if (!name) return '—'
  const MANAGERS = '华夏|易方达|国泰|广发|南方|博时|嘉实|华安|华宝|华泰柏瑞|景顺|平安|天弘|建信|中银|富国|汇添富|鹏华|招商|工银|申万菱信|永赢|民生加银|大成|交银|银华|前海开源|等权重|国联安|国寿'
  const cleaned = name.replace(/ETF/gi, '').trim()
  const m = cleaned.match(new RegExp(`^(.+?)[\s\u00A0]*(${MANAGERS})+$`))
  if (m) return m[1].trim() || '—'
  return cleaned
}
function hasTriggered(symbol) {
  const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000)
  return logs.value.some(l =>
    l.stock_symbol === symbol && !l.acknowledged && new Date(l.triggered_at) >= oneDayAgo
  )
}
function getRuleCount(symbol) {
  return alerts.value.filter(a => a.stock_symbol === symbol).length
}

async function loadStocks() {
  try {
    const [sr, ar, lr, er] = await Promise.all([
      fetch(`${API}/stocks`),
      fetch(`${API}/alerts`),
      fetch(`${API}/alerts/logs`),
      fetch(`${API}/stocks/signals`),
    ])
    stocks.value = await sr.json()
    alerts.value = ar.ok ? await ar.json() : []
    logs.value = lr.ok ? await lr.json() : []
    etfSignals.value = er.ok ? await er.json() : []
  } catch (e) {
    showToast(e.message, 'danger')
  }
}

function showAddStockModal() {
  newStock.value = { symbol: '', market: 'CN' }
  new window.bootstrap.Modal(document.getElementById('addStockModal')).show()
}

async function addStock() {
  const symbol = newStock.value.symbol.trim()
  if (!symbol) { showToast('请输入股票代码', 'warning'); return }
  loading.value = true
  try {
    const r = await fetch(`${API}/stocks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newStock.value),
    })
    if (!r.ok) {
      const e = await r.json()
      throw new Error(e.detail || '添加股票失败')
    }
    window.bootstrap.Modal.getInstance(document.getElementById('addStockModal'))?.hide()
    showToast(`股票 ${symbol} 添加成功`, 'success')
    await loadStocks()
  } catch (e) {
    showToast(e.message, 'danger')
  } finally {
    loading.value = false
  }
}

async function removeStock(symbol) {
  if (!confirm(`确定要从关注列表移除 ${symbol}？`)) return
  loading.value = true
  try {
    const r = await fetch(`${API}/stocks/${symbol}`, { method: 'DELETE' })
    if (!r.ok) {
      const e = await r.json()
      throw new Error(e.detail || '移除股票失败')
    }
    showToast(`股票 ${symbol} 已移除`, 'success')
    await loadStocks()
  } catch (e) {
    showToast(e.message, 'danger')
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  localStorage.setItem('stock_monitor_refresh', refreshInterval.value)
  if (refreshTimer) clearInterval(refreshTimer)
  const interval = parseInt(refreshInterval.value)
  if (interval > 0) {
    refreshTimer = setInterval(loadStocks, interval * 1000)
  }
}

onMounted(async () => {
  await loadStocks()
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

// Expose for parent
defineExpose({ loadStocks })
</script>
