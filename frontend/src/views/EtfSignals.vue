<template>
  <div class="container-fluid mt-4 px-3">
    <!-- Toast -->
    <div class="toast-container">
      <div v-for="t in toasts" :key="t.id" class="toast show align-items-center text-white" :class="'bg-' + t.type" role="alert">
        <div class="d-flex">
          <div class="toast-body">{{ t.message }}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="removeToast(t.id)"></button>
        </div>
      </div>
    </div>

    <!-- Filter hint -->
    <div v-if="filterMode !== 'all' || searchQuery" class="alert alert-info py-2 mb-3" style="font-size:0.85rem">
      <i class="bi bi-filter me-1"></i>当前筛选：<strong>{{ filterLabel }}{{ searchQuery ? (filterLabel ? ' + ' : '') + '搜索: ' + searchQuery : '' }}</strong>
      <button class="btn btn-sm btn-outline-info float-end py-0 px-2" @click="clearFilters">清除</button>
    </div>

    <!-- Header Stats -->
    <div class="row mb-4">
      <div class="col-md-3">
        <div class="card text-white clickable-card" :class="filterMode === 'buy' ? 'bg-success border-3 border-dark' : (buyCount > 0 ? 'bg-success' : 'bg-secondary')"
             @click="toggleFilter('buy')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-arrow-up-circle me-2"></i>买入信号</h6>
            <h3 class="mb-0">{{ buyCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white clickable-card" :class="filterMode === 'sell' ? 'bg-danger border-3 border-dark' : (sellCount > 0 ? 'bg-danger' : 'bg-secondary')"
             @click="toggleFilter('sell')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-arrow-down-circle me-2"></i>卖出信号</h6>
            <h3 class="mb-0">{{ sellCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-dark clickable-card" :class="filterMode === 'hold' ? 'bg-warning border-3 border-dark' : 'bg-warning'"
             @click="toggleFilter('hold')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-pause-circle me-2"></i>观望</h6>
            <h3 class="mb-0">{{ holdCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card text-white clickable-card" :class="filterMode === 'holding' ? 'bg-info border-3 border-dark' : 'bg-info'"
             @click="toggleFilter('holding')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-wallet2 me-2"></i>持有</h6>
            <h3 class="mb-0">{{ holdingCount }}</h3>
          </div>
        </div>
      </div>
    </div>

    <!-- Signals Card -->
    <div class="card">
      <!-- Refresh progress bar -->
      <div v-if="refreshing" class="progress-bar-animated" style="height:3px;background:var(--bs-primary);transition:width 0.3s;"></div>

      <div class="card-header d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center gap-2">
          <h5 class="mb-0"><i class="bi bi-activity me-2"></i>量化交易信号 <span class="badge bg-secondary ms-1">{{ signals.length }}</span></h5>
          <span v-if="refreshing" class="spinner-border spinner-border-sm text-primary" role="status"></span>
          <small v-if="lastRefreshText || !refreshing" class="text-muted" style="font-size:0.7rem;">
            {{ lastRefreshText }}
            <span v-if="lastRefreshText"> | </span>{{ nextRefreshText }}
          </small>
          <input v-model="searchQuery" type="text" class="form-control form-control-sm" placeholder="代码/名称搜索" style="width:130px;">
        </div>
        <div>
          <button class="btn btn-outline-primary btn-sm me-2" @click="loadSignals" :disabled="refreshing">
            <i class="bi bi-arrow-clockwise me-1"></i>{{ refreshing ? '刷新中...' : '刷新' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="showAddModal">
            <i class="bi bi-plus-lg me-1"></i>添加
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <!-- Per-ETF refresh progress -->
        <div v-if="refreshing" class="px-3 pt-2">
          <div class="d-flex align-items-center gap-2 mb-2">
            <div class="progress flex-grow-1" style="height:6px;">
              <div class="progress-bar bg-primary" :style="{ width: refreshProgress + '%' }"></div>
            </div>
            <small class="text-muted" style="font-size:0.7rem;min-width:60px;text-align:right;">
              {{ refreshProgress }}%
            </small>
          </div>
          <small class="text-muted" style="font-size:0.7rem;">
            正在更新 {{ refreshSymbol || '...' }} ...
          </small>
        </div>

        <div v-if="loading && signals.length === 0" class="text-center py-5">
          <div class="spinner-border text-primary"></div>
          <p class="mt-2 text-muted">正在计算信号...</p>
        </div>
        <div v-else-if="signals.length === 0" class="text-center text-muted py-5">
          <i class="bi bi-inbox fs-1"></i>
          <p class="mt-2">暂无关注的 ETF，点击「添加 ETF」开始</p>
        </div>
        <div v-else class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>ETF</th>
                <th>信号</th>
                <th>原因</th>
                <th>评分</th>
                <th>趋势强度</th>
                <th>RSI</th>
                <th>ATR止损</th>
                <th>市场</th>
                <th>趋势</th>
                <th>回调</th>
                <th>情绪</th>
                <th>量比信号</th>
                <th>突破</th>
                <th>MA5</th>
                <th>MA10</th>
                <th>MA20</th>
                <th>当前价</th>
                <th>量比</th>
                <th>连涨</th>
                <th>累计涨幅</th>
                <th>成本</th>
                <th>持仓</th>
                <th>盈亏额</th>
                <th>盈亏%</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <EtfSignalRow
                v-for="sig in filteredSignals"
                :key="sig.symbol"
                :sig="sig"
                :refreshing-row="refreshingSymbol === sig.symbol"
                :refreshing="refreshing"
                @edit="openEditModal"
                @remove="removeEtf"
              />
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Add ETF Modal -->
    <div class="modal fade" id="addEtfModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-2"></i>添加到量化列表</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">标的类型</label>
              <div>
                <div class="form-check form-check-inline">
                  <input v-model="addForm.instrument_type" class="form-check-input" type="radio" id="typeEtf" value="ETF">
                  <label class="form-check-label" for="typeEtf">ETF（基金）</label>
                </div>
                <div class="form-check form-check-inline">
                  <input v-model="addForm.instrument_type" class="form-check-input" type="radio" id="typeStock" value="STOCK">
                  <label class="form-check-label" for="typeStock">股票</label>
                </div>
              </div>
              <div class="form-text">ETF使用趋势策略，股票使用突破策略（风控更严格）</div>
            </div>
            <div class="mb-3">
              <label for="etfSymbol" class="form-label">代码</label>
              <input v-model="addForm.symbol" type="text" class="form-control" id="etfSymbol" placeholder="例如：512480、159915、600519、000001">
              <div class="form-text">支持 ETF（510xxx/159xxx）和股票（600xxx/000xxx/300xxx）</div>
            </div>
            <div class="mb-3">
              <label for="etfName" class="form-label">名称（可选）</label>
              <input v-model="addForm.name" type="text" class="form-control" id="etfName" placeholder="自动从行情接口获取">
            </div>
            <div class="mb-3">
              <label for="etfCapital" class="form-label">初始资金（元）</label>
              <input v-model.number="addForm.initial_capital" type="number" class="form-control" id="etfCapital" value="2000" min="100">
            </div>
            <div class="mb-3">
              <label for="etfTemplate" class="form-label">策略模板</label>
              <select v-model="addForm.template_name" class="form-select" id="etfTemplate">
                <option value="CORE">CORE（稳健型）- 止损-5% 止盈5%</option>
                <option value="THEME">THEME（进攻型）- 止损-6% 止盈4%</option>
              </select>
            </div>
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="etfCost" class="form-label">持仓成本（可选）</label>
                  <input v-model.number="addForm.cost" type="number" step="0.001" class="form-control" id="etfCost" placeholder="如：1.234">
                </div>
              </div>
              <div class="col-6">
                <div class="mb-3">
                  <label for="etfQty" class="form-label">持仓股数（可选）</label>
                  <input v-model.number="addForm.quantity" type="number" class="form-control" id="etfQty" placeholder="如：1000">
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="addEtf">确认添加</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Holdings Modal -->
    <div class="modal fade" id="editHoldingsModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-pencil me-2"></i>编辑持仓 - {{ editForm.symbol }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">标的类型</label>
              <div>
                <div class="form-check form-check-inline">
                  <input v-model="editForm.instrument_type" class="form-check-input" type="radio" id="editTypeEtf" value="ETF">
                  <label class="form-check-label" for="editTypeEtf">ETF（基金）</label>
                </div>
                <div class="form-check form-check-inline">
                  <input v-model="editForm.instrument_type" class="form-check-input" type="radio" id="editTypeStock" value="STOCK">
                  <label class="form-check-label" for="editTypeStock">股票</label>
                </div>
              </div>
              <div class="form-text">修改类型后将使用对应的策略计算信号</div>
            </div>
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="editCost" class="form-label">持仓成本</label>
                  <input v-model.number="editForm.cost" type="number" step="0.001" class="form-control" id="editCost" placeholder="如：1.234">
                </div>
              </div>
              <div class="col-6">
                <div class="mb-3">
                  <label for="editQty" class="form-label">持仓股数</label>
                  <input v-model.number="editForm.quantity" type="number" class="form-control" id="editQty" placeholder="如：1000">
                </div>
              </div>
            </div>
            <div class="mb-3">
              <label for="editTemplate" class="form-label">策略模板</label>
              <select v-model="editForm.template_name" class="form-select" id="editTemplate">
                <option value="CORE">CORE（稳健型）- 止损-5% 止盈5%</option>
                <option value="THEME">THEME（进攻型）- 止损-6% 止盈4%</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="editEtfHoldings">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import EtfSignalRow from '../components/EtfSignalRow.vue'

const API = '/api'
const AUTO_REFRESH_INTERVAL = 30 * 1000

const watchList = ref([])
const signals = ref([])
const loading = ref(false)
const toasts = ref([])
const addForm = ref({ symbol: '', name: '', initial_capital: 2000, cost: null, quantity: null, template_name: 'CORE', instrument_type: 'ETF' })
const editForm = ref({ symbol: '', cost: null, quantity: null, template_name: 'CORE', instrument_type: 'ETF' })
const filterMode = ref('all')
const searchQuery = ref('')

const refreshing = ref(false)
const refreshingSymbol = ref('')
const refreshProgress = ref(0)
const refreshSymbol = ref('')
const lastRefresh = ref(null)
const cachedAt = ref(null)
let autoRefreshTimer = null
let countdownTimer = null
const countdownSec = ref(30)

const buyCount = computed(() => signals.value.filter(s => s.buy_signal).length)
const sellCount = computed(() => signals.value.filter(s => s.sell_signal).length)
const holdCount = computed(() => signals.value.filter(s => !s.buy_signal && !s.sell_signal).length)
const holdingCount = computed(() => signals.value.filter(s => s.quantity && s.quantity > 0).length)

const filteredSignals = computed(() => {
  let result = signals.value

  if (filterMode.value === 'buy') result = result.filter(s => s.buy_signal)
  else if (filterMode.value === 'sell') result = result.filter(s => s.sell_signal)
  else if (filterMode.value === 'hold') result = result.filter(s => !s.buy_signal && !s.sell_signal)
  else if (filterMode.value === 'holding') result = result.filter(s => s.quantity && s.quantity > 0)
  else if (filterMode.value === 'no_holding') result = result.filter(s => !s.quantity || s.quantity <= 0)

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    result = result.filter(s =>
      (s.symbol && s.symbol.toLowerCase().includes(q)) ||
      (s.name && s.name.toLowerCase().includes(q))
    )
  }

  return result
})

const filterLabel = computed(() => {
  if (filterMode.value === 'buy') return '买入信号'
  if (filterMode.value === 'sell') return '卖出信号'
  if (filterMode.value === 'hold') return '观望'
  if (filterMode.value === 'holding') return '持有'
  if (filterMode.value === 'no_holding') return '未持股'
  return ''
})

function toggleFilter(mode) {
  filterMode.value = filterMode.value === mode ? 'all' : mode
}

function clearFilters() {
  filterMode.value = 'all'
  searchQuery.value = ''
}

const lastRefreshText = computed(() => {
  if (!cachedAt.value) return ''
  const d = new Date(cachedAt.value)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${h}:${m}:${s}`
})

const nextRefreshText = computed(() => {
  if (refreshing.value) return '刷新中...'
  return `${countdownSec.value}秒后刷新`
})

function showToast(message, type = 'info') {
  const id = Date.now()
  toasts.value.push({ id, message, type })
  setTimeout(() => removeToast(id), 4000)
}
function removeToast(id) { toasts.value = toasts.value.filter(t => t.id !== id) }

function showAddModal() {
  addForm.value = { symbol: '', name: '', initial_capital: 2000, cost: null, quantity: null, template_name: 'CORE', instrument_type: 'ETF' }
  new window.bootstrap.Modal(document.getElementById('addEtfModal')).show()
}

function openEditModal(sig) {
  editForm.value = { symbol: sig.symbol, cost: sig.cost || null, quantity: sig.quantity || null, template_name: sig.template_name || 'CORE', instrument_type: sig.instrument_type || 'ETF' }
  new window.bootstrap.Modal(document.getElementById('editHoldingsModal')).show()
}

async function editEtfHoldings() {
  try {
    const r = await fetch(`${API}/stocks/watch/${editForm.value.symbol}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: editForm.value.symbol,
        cost: editForm.value.cost,
        quantity: editForm.value.quantity,
        template_name: editForm.value.template_name,
        instrument_type: editForm.value.instrument_type,
      })
    })
    if (!r.ok) throw new Error('更新失败')
    window.bootstrap.Modal.getInstance(document.getElementById('editHoldingsModal'))?.hide()
    showToast('持仓已更新', 'success')
    await loadSignals()
  } catch (e) {
    showToast(e.message, 'danger')
  }
}

async function loadWatchList() {
  try {
    const r = await fetch(`${API}/stocks/watch`)
    if (r.ok) watchList.value = await r.json()
  } catch (e) { showToast('加载关注列表失败', 'danger') }
}

async function loadSignals() {
  if (refreshing.value) return
  refreshing.value = true
  refreshProgress.value = 0
  try {
    const r = await fetch(`${API}/stocks/signals`)
    if (!r.ok) throw new Error(await r.text())
    signals.value = await r.json()
    lastRefresh.value = Date.now()
    if (signals.value.length > 0 && signals.value[0].calculated_at) {
      cachedAt.value = signals.value[0].calculated_at
    }
  } catch (e) {
    showToast('刷新信号失败: ' + e.message, 'danger')
  } finally {
    refreshing.value = false
    refreshingSymbol.value = ''
    refreshProgress.value = 0
  }
}

async function addEtf() {
  const sym = addForm.value.symbol.trim().toUpperCase()
  if (!sym) { showToast('请输入代码', 'warning'); return }
  try {
    const r = await fetch(`${API}/stocks/watch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: sym,
        name: addForm.value.name || undefined,
        market: 'CN',
        initial_capital: addForm.value.initial_capital || 2000,
        cost: addForm.value.cost || undefined,
        quantity: addForm.value.quantity || undefined,
        template_name: addForm.value.template_name || 'CORE',
        instrument_type: addForm.value.instrument_type || 'ETF',
      })
    })
    if (!r.ok) {
      const err = await r.json()
      throw new Error(err.detail || '添加失败')
    }
    window.bootstrap.Modal.getInstance(document.getElementById('addEtfModal'))?.hide()
    showToast('添加成功', 'success')
    await loadWatchList()
    await loadSignals()
  } catch (e) { showToast(e.message, 'danger') }
}

async function removeEtf(symbol) {
  if (!confirm(`确定要从关注列表移除 ${symbol} 吗？`)) return
  try {
    const r = await fetch(`${API}/stocks/watch/${symbol}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('删除失败')
    showToast(`${symbol} 已移除`, 'success')
    await loadWatchList()
    await loadSignals()
  } catch (e) { showToast(e.message, 'danger') }
}

function startAutoRefresh() {
  stopAutoRefresh()
  lastRefresh.value = Date.now()
  countdownSec.value = 30
  countdownTimer = setInterval(() => {
    countdownSec.value = Math.max(0, countdownSec.value - 1)
  }, 1000)
  autoRefreshTimer = setInterval(() => {
    lastRefresh.value = Date.now()
    countdownSec.value = 30
    loadSignals()
  }, 30000)
}

function stopAutoRefresh() {
  if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null }
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

onMounted(async () => {
  await loadWatchList()
  await loadSignals()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.table { font-size: 0.875rem; }
.table th { font-weight: 600; white-space: nowrap; }
.clickable-card { cursor: pointer; transition: transform 0.1s, box-shadow 0.1s; }
.clickable-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.border-3 { border-width: 3px !important; }
</style>
