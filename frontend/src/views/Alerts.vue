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
      <div class="col-md-2">
        <div class="card text-white clickable-card" :class="filterMode === 'buy' ? 'bg-success border-3 border-dark' : (buyCount > 0 ? 'bg-success' : 'bg-secondary')"
             @click="toggleFilter('buy')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-arrow-up-circle me-2"></i>买入信号</h6>
            <h3 class="mb-0">{{ buyCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card text-white clickable-card" :class="filterMode === 'sell' ? 'bg-danger border-3 border-dark' : (sellCount > 0 ? 'bg-danger' : 'bg-secondary')"
             @click="toggleFilter('sell')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-arrow-down-circle me-2"></i>卖出信号</h6>
            <h3 class="mb-0">{{ sellCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card text-dark clickable-card" :class="filterMode === 'hold' ? 'bg-warning border-3 border-dark' : 'bg-warning'"
             @click="toggleFilter('hold')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-pause-circle me-2"></i>观望</h6>
            <h3 class="mb-0">{{ holdCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-2">
        <div class="card text-white clickable-card" :class="filterMode === 'holding' ? 'bg-info border-3 border-dark' : 'bg-info'"
             @click="toggleFilter('holding')">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-wallet2 me-2"></i>持有</h6>
            <h3 class="mb-0">{{ holdingCount }}</h3>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card" :class="totalProfitLoss >= 0 ? 'border-danger' : 'border-success'" style="border-width:2px;">
          <div class="card-body py-2">
            <h6 class="card-title mb-1"><i class="bi bi-currency-exchange me-2"></i>总盈亏</h6>
            <h3 class="mb-0" :class="totalProfitLoss >= 0 ? 'text-danger' : 'text-success'">
              {{ totalProfitLoss >= 0 ? '+' : '' }}{{ totalProfitLoss.toFixed(0) }} 元
            </h3>
          </div>
        </div>
      </div>
    </div>

    <!-- Signals Card -->
    <div class="card mb-4">

      <div class="card-header d-flex justify-content-between align-items-center">
        <div class="d-flex align-items-center gap-2">
          <h5 class="mb-0"><i class="bi bi-activity me-2"></i>股票信号 <span class="badge bg-secondary ms-1">{{ signals.length }}</span></h5>
          <small v-if="lastRefreshText || !refreshing" class="text-muted" style="font-size:0.7rem;">
            {{ lastRefreshText }}
            <span v-if="lastRefreshText"> | </span>{{ nextRefreshText }}
          </small>
          <input v-model="searchQuery" type="text" class="form-control form-control-sm" placeholder="代码/名称搜索" style="width:130px;">
        </div>
        <div>
          <button class="btn btn-outline-secondary btn-sm me-2" @click="showAiSettings" title="AI 配置">
            <i class="bi bi-gear me-1"></i>
          </button>
          <button class="btn btn-outline-primary btn-sm me-2" @click="loadSignals" :disabled="refreshing">
            <i class="bi bi-arrow-clockwise me-1"></i>{{ refreshing ? '刷新中...' : '刷新' }}
          </button>
          <button class="btn btn-primary btn-sm" @click="showAddModal">
            <i class="bi bi-plus-lg me-1"></i>添加
          </button>
        </div>
      </div>
      <div class="card-body p-0">
        <div v-if="loading && signals.length === 0" class="text-center py-5">
          <div class="spinner-border text-primary"></div>
          <p class="mt-2 text-muted">正在计算信号...</p>
        </div>
        <div v-else-if="signals.length === 0" class="text-center text-muted py-5">
          <i class="bi bi-inbox fs-1"></i>
          <p class="mt-2">暂无关注的股票，点击「添加」开始</p>
        </div>
        <div v-else class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-light">
              <tr>
                <th>代码</th>
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
                @remove="removeItem"
                @ai-analyze="openAiModal"

              />
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Add/Edit Stock Modal -->
    <div class="modal fade" id="addModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-plus-circle me-2"></i>添加股票</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label for="stockSymbol" class="form-label">代码</label>
              <input v-model="addForm.symbol" type="text" class="form-control" id="stockSymbol" placeholder="例如：512480、159915、600000">
              <div class="form-text">ETF（510xxx/159xxx）或股票（600xxx/000xxx）</div>
            </div>
            <div class="mb-3">
              <label for="stockType" class="form-label">类型</label>
              <select v-model="addForm.instrument_type" class="form-select" id="stockType">
                <option value="ETF">ETF（指数基金）</option>
                <option value="STOCK">股票（个股）</option>
              </select>
            </div>
            <div class="mb-3">
              <label for="stockTemplate" class="form-label">策略模板</label>
              <select v-model="addForm.template_name" class="form-select" id="stockTemplate">
                <option value="CORE">CORE（稳健型）- 止损-5% 止盈5%</option>
                <option value="THEME">THEME（进攻型）- 止损-6% 止盈4%</option>
              </select>
            </div>
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="stockCost" class="form-label">持仓成本（可选）</label>
                  <input v-model.number="addForm.cost" type="number" step="0.001" class="form-control" id="stockCost" placeholder="如：1.234">
                </div>
              </div>
              <div class="col-6">
                <div class="mb-3">
                  <label for="stockQty" class="form-label">持仓数量（可选）</label>
                  <input v-model.number="addForm.quantity" type="number" class="form-control" id="stockQty" placeholder="如：1000">
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="addItem">确认添加</button>
          </div>
        </div>
      </div>
    </div>

    <!-- AI Analysis Modal -->
    <AiAnalysisModal
      v-if="aiModal.symbol"
      :ref="el => aiModalRef = el"
      :symbol="aiModal.symbol"
      :name="aiModal.name"
      :instrument-type="aiModal.instrument_type"
      :signal-data="aiModal.signal_data"
    />

    <!-- AI Settings Modal -->
    <div class="modal fade" id="aiSettingsModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-gear me-2"></i>AI 分析配置</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label for="aiApiKey" class="form-label">API Key <span class="text-danger">*</span></label>
              <input v-model="aiSettings.api_key" type="password" class="form-control" id="aiApiKey"
                     placeholder="输入 MiniMax API Key">
              <div class="form-text">当前: {{ aiSettingsStatus }}</div>
            </div>
            <div class="mb-3">
              <label for="aiBaseUrl" class="form-label">Base URL</label>
              <input v-model="aiSettings.base_url" type="text" class="form-control" id="aiBaseUrl"
                     placeholder="https://api.minimax.chat/v1">
            </div>
            <div class="mb-3">
              <label for="aiModel" class="form-label">模型</label>
              <input v-model="aiSettings.model" type="text" class="form-control" id="aiModel"
                     placeholder="minimax-text-01">
            </div>
            <div class="form-check form-switch mb-3">
              <input v-model="aiSettings.enabled" class="form-check-input" type="checkbox" id="aiEnabled">
              <label class="form-check-label" for="aiEnabled">启用 AI 分析</label>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="saveAiSettings">保存配置</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Holdings Modal -->
    <div class="modal fade" id="editModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-pencil me-2"></i>编辑持仓 - {{ editForm.symbol }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="row">
              <div class="col-6">
                <div class="mb-3">
                  <label for="editCost" class="form-label">持仓成本</label>
                  <input v-model.number="editForm.cost" type="number" step="0.001" class="form-control" id="editCost" placeholder="如：1.234">
                </div>
              </div>
              <div class="col-6">
                <div class="mb-3">
                  <label for="editQty" class="form-label">持仓数量</label>
                  <input v-model.number="editForm.quantity" type="number" class="form-control" id="editQty" placeholder="如：1000">
                </div>
              </div>
            </div>
            <div class="mb-3">
              <label for="editType" class="form-label">类型</label>
              <select v-model="editForm.instrument_type" class="form-select" id="editType">
                <option value="ETF">ETF（指数基金）</option>
                <option value="STOCK">股票（个股）</option>
              </select>
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
            <button type="button" class="btn btn-primary" @click="saveEdit">保存</button>
          </div>
        </div>
      </div>
    </div>
</div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import EtfSignalRow from '../components/EtfSignalRow.vue'
import AiAnalysisModal from '../components/AiAnalysisModal.vue'

const API = '/api'

const signals = ref([])
const loading = ref(false)
const toasts = ref([])
const addForm = ref({ symbol: '', template_name: 'CORE', cost: null, quantity: null, instrument_type: 'ETF' })
const editForm = ref({ symbol: '', template_name: 'CORE', cost: null, quantity: null, instrument_type: 'ETF' })
const filterMode = ref('all')
const searchQuery = ref('')
const aiModalRef = ref(null)
const aiModal = ref({ symbol: '', name: '', instrument_type: 'ETF', signal_data: {} })
const aiSettings = ref({ api_key: '', base_url: 'https://api.minimax.chat/v1', model: 'minimax-text-01', enabled: true })
const aiSettingsStatus = ref('加载中...')

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
const totalProfitLoss = computed(() => signals.value.reduce((sum, s) => sum + (s.profit_loss || 0), 0))

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

function getCurrency(market) {
  return { HK: 'HK$', US: '$' }[market] || '¥'
}

// ----- Stock/ETF watch list -----
function showAddModal() {
  addForm.value = { symbol: '', template_name: 'CORE', cost: null, quantity: null }
  new window.bootstrap.Modal(document.getElementById('addModal')).show()
}

function openEditModal(sig) {
  editForm.value = { symbol: sig.symbol, template_name: sig.template_name || 'CORE', cost: sig.cost || null, quantity: sig.quantity || null, instrument_type: sig.instrument_type || 'ETF' }
  new window.bootstrap.Modal(document.getElementById('editModal')).show()
}

function openAiModal(sig) {
  aiModal.value = { symbol: sig.symbol, name: sig.name || '', instrument_type: sig.instrument_type || 'ETF', signal_data: { ...sig } }
  setTimeout(() => { if (aiModalRef.value) aiModalRef.value.show() }, 50)
}

async function showAiSettings() {
  try {
    const r = await fetch(`${API}/ai/settings`)
    if (r.ok) {
      const data = await r.json()
      aiSettings.value.api_key = ''
      aiSettings.value.base_url = data.base_url || 'https://api.minimax.chat/v1'
      aiSettings.value.model = data.model || 'minimax-text-01'
      aiSettings.value.enabled = data.enabled !== false
      aiSettingsStatus.value = data.configured ? '已配置 ' + data.api_key : '未配置'
    }
  } catch (e) { aiSettingsStatus.value = '读取失败' }
  new bootstrap.Modal(document.getElementById('aiSettingsModal')).show()
}

async function saveAiSettings() {
  const body = {}
  if (aiSettings.value.api_key) body.api_key = aiSettings.value.api_key
  body.base_url = aiSettings.value.base_url
  body.model = aiSettings.value.model
  body.enabled = aiSettings.value.enabled
  try {
    const r = await fetch(`${API}/ai/settings`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error('保存失败')
    bootstrap.Modal.getInstance(document.getElementById('aiSettingsModal'))?.hide()
    showToast('AI 配置已保存', 'success')
  } catch (e) { showToast(e.message, 'danger') }
}

async function openRuleModal(sig) {
  let stock = stocks.value.find(s => s.symbol === sig.symbol)
  if (!stock) {
    // 先尝试添加到 stocks 表
    try {
      const r = await fetch(`${API}/stocks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: sig.symbol, market: 'CN' }),
      })
      if (!r.ok) throw new Error('添加股票失败')
      const created = await r.json()
      stock = { id: created.id, symbol: sig.symbol, name: sig.name }
      stocks.value.push(stock)
    } catch (e) {
      showToast(`无法为此股票创建告警规则: ${e.message}`, 'danger')
      return
    }
  }
  editingRuleId.value = null
  ruleForm.value = { ruleId: null, stockId: stock.id, alertType: 'rise', threshold: 5, days: 1, targetPrice: '', cooldown: 0, followupThreshold: 1 }
  new window.bootstrap.Modal(document.getElementById('ruleModal')).show()
}

async function saveEdit() {
  try {
    const r = await fetch(`${API}/stocks/watch/${editForm.value.symbol}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol: editForm.value.symbol, cost: editForm.value.cost, quantity: editForm.value.quantity, template_name: editForm.value.template_name, instrument_type: editForm.value.instrument_type })
    })
    if (!r.ok) throw new Error('更新失败')
    window.bootstrap.Modal.getInstance(document.getElementById('editModal'))?.hide()
    showToast('持仓已更新', 'success')
    await loadSignals()
  } catch (e) { showToast(e.message, 'danger') }
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

async function addItem() {
  const sym = addForm.value.symbol.trim().toUpperCase()
  if (!sym) { showToast('请输入代码', 'warning'); return }
  try {
    const r = await fetch(`${API}/stocks/watch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: sym, market: 'CN', initial_capital: 2000,
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
    window.bootstrap.Modal.getInstance(document.getElementById('addModal'))?.hide()
    showToast(`${sym} 添加成功`, 'success')
    await loadSignals()
  } catch (e) { showToast(e.message, 'danger') }
}

async function removeItem(symbol) {
  if (!confirm(`确定要从列表移除 ${symbol} 吗？`)) return
  try {
    const r = await fetch(`${API}/stocks/watch/${symbol}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('删除失败')
    showToast(`${symbol} 已移除`, 'success')
    await loadSignals()
  } catch (e) { showToast(e.message, 'danger') }
}

// ----- Alert Rules -----
async function loadStocks() {
  try {
    const r = await fetch(`${API}/stocks`)
    if (r.ok) stocks.value = await r.json()
  } catch (e) { showToast('加载股票列表失败', 'danger') }
}

async function loadRules() {
  try {
    const r = await fetch(`${API}/alerts`)
    if (!r.ok) throw new Error('加载告警规则失败')
    rules.value = await r.json()
  } catch (e) { showToast(e.message, 'danger') }
}

function showRuleModal(ruleId) {
  if (ruleId) {
    const rule = rules.value.find(r => r.id === ruleId)
    if (!rule) return
    editingRuleId.value = ruleId
    ruleForm.value = {
      ruleId: rule.id,
      stockId: rule.stock_id,
      alertType: rule.alert_type,
      threshold: rule.threshold_percent || 5,
      days: rule.days || 1,
      targetPrice: rule.target_price || '',
      cooldown: rule.cooldown_minutes || 0,
      followupThreshold: rule.followup_threshold || 1,
    }
  } else {
    editingRuleId.value = null
    ruleForm.value = { ruleId: null, stockId: '', alertType: 'rise', threshold: 5, days: 1, targetPrice: '', cooldown: 0, followupThreshold: 1 }
  }
  new window.bootstrap.Modal(document.getElementById('ruleModal')).show()
}

async function saveRule() {
  if (!ruleForm.value.stockId) { showToast('请选择股票', 'warning'); return }
  const isEdit = !!editingRuleId.value

  const data = {
    stock_id: parseInt(ruleForm.value.stockId),
    alert_type: ruleForm.value.alertType,
    enabled: true,
    cooldown_minutes: parseInt(ruleForm.value.cooldown) || 0,
    followup_threshold: parseFloat(ruleForm.value.followupThreshold) || 1.0,
  }

  if (ruleForm.value.alertType === 'rise' || ruleForm.value.alertType === 'fall') {
    const tp = parseFloat(ruleForm.value.threshold)
    const days = parseInt(ruleForm.value.days)
    if (!tp || tp <= 0) { showToast('请输入有效的涨跌幅阈值', 'warning'); return }
    if (!days || days < 1) { showToast('统计天数至少为1', 'warning'); return }
    data.threshold_percent = tp
    data.days = days
  } else {
    const tp = parseFloat(ruleForm.value.targetPrice)
    if (!tp || tp <= 0) { showToast('请输入有效的目标价格', 'warning'); return }
    data.target_price = tp
    data.threshold_percent = 0
    data.days = 1
  }

  try {
    const url = isEdit ? `${API}/alerts/${editingRuleId.value}` : `${API}/alerts`
    const method = isEdit ? 'PUT' : 'POST'
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    if (!r.ok) {
      const err = await r.json()
      throw new Error(err.detail || '保存失败')
    }
    window.bootstrap.Modal.getInstance(document.getElementById('ruleModal'))?.hide()
    showToast(isEdit ? '规则更新成功' : '规则创建成功', 'success')
    await loadRules()
  } catch (e) { showToast(e.message, 'danger') }
}

async function toggleRule(ruleId) {
  try {
    const r = await fetch(`${API}/alerts/${ruleId}/toggle`, { method: 'POST' })
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '切换失败') }
    showToast('已切换状态', 'success')
    await loadRules()
  } catch (e) { showToast(e.message, 'danger') }
}

async function deleteRule(ruleId) {
  if (!confirm('确定要删除这条告警规则吗？')) return
  try {
    const r = await fetch(`${API}/alerts/${ruleId}`, { method: 'DELETE' })
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '删除失败') }
    showToast('规则已删除', 'success')
    await loadRules()
  } catch (e) { showToast(e.message, 'danger') }
}

// ----- Auto refresh -----
function startAutoRefresh() {
  stopAutoRefresh()
  lastRefresh.value = Date.now()
  countdownSec.value = 30
  countdownTimer = setInterval(() => { countdownSec.value = Math.max(0, countdownSec.value - 1) }, 1000)
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

onMounted(async () => { await loadSignals()
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
