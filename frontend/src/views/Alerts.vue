<template>
  <div class="container mt-4">
    <!-- Toast -->
    <div class="toast-container">
      <div v-for="t in toasts" :key="t.id" class="toast show align-items-center text-white" :class="'bg-' + t.type" role="alert">
        <div class="d-flex">
          <div class="toast-body">{{ t.message }}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="removeToast(t.id)"></button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="mb-0"><i class="bi bi-bell me-2"></i>告警规则</h5>
        <button class="btn btn-primary btn-sm" @click="showCreateModal">
          <i class="bi bi-plus-lg me-1"></i>创建规则
        </button>
      </div>
      <div class="card-body">
        <!-- Desktop view -->
        <div v-if="filteredRules.length > 0" class="row d-none d-md-flex">
          <AlertRuleItem
            v-for="rule in filteredRules"
            :key="rule.id"
            :rule="rule"
            :currency-fn="getCurrency"
            @toggle="toggleRule"
            @edit="editRule"
            @delete="deleteRule"
          />
        </div>

        <!-- Mobile view -->
        <div class="d-md-none">
          <div v-if="filteredRules.length === 0" class="text-center text-muted py-5">
            <i class="bi bi-inbox fs-1"></i>
            <p class="mt-2">暂无告警规则，点击「创建规则」添加</p>
          </div>
          <AlertRuleItem
            v-for="rule in filteredRules"
            :key="'m-' + rule.id"
            :rule="rule"
            :currency-fn="getCurrency"
            @toggle="toggleRule"
            @edit="editRule"
            @delete="deleteRule"
          />
        </div>

        <div v-if="filteredRules.length === 0" class="d-none d-md-block col-12 text-center text-muted py-5">
          <i class="bi bi-inbox fs-1"></i>
          <p class="mt-2">暂无告警规则，点击「创建规则」添加</p>
        </div>
      </div>
    </div>

    <!-- Rule Modal -->
    <div class="modal fade" id="ruleModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">
              <i :class="isEditing ? 'bi bi-pencil me-2' : 'bi bi-plus-circle me-2'"></i>{{ isEditing ? '编辑告警规则' : '创建告警规则' }}
            </h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <input type="hidden" v-model="form.ruleId">

            <div class="mb-3" v-if="!preSelectedStock || isEditing">
              <label for="ruleStock" class="form-label">股票</label>
              <select v-model="form.stockId" class="form-select" id="ruleStock">
                <option value="">请选择股票...</option>
                <option v-for="s in stocks" :key="s.id" :value="s.id">{{ s.symbol }} - {{ s.name || s.symbol }}</option>
              </select>
            </div>

            <div class="mb-3" v-else>
              <label class="form-label">股票</label>
              <div>
                <span class="stock-tag">{{ preSelectedStock.symbol }} {{ preSelectedStock.name || '' }}</span>
                <span class="text-success fw-bold ms-2" v-if="preSelectedStock.current_price">
                  当前价：{{ getCurrency(preSelectedStock.market) }}{{ preSelectedStock.current_price.toFixed(2) }}
                </span>
              </div>
            </div>

            <div class="mb-3">
              <label for="ruleAlertType" class="form-label">告警类型</label>
              <select v-model="form.alertType" class="form-select" id="ruleAlertType">
                <option value="rise">📈 趋势上涨（几天内涨幅超阈值）</option>
                <option value="fall">📉 趋势下跌（几天内跌幅超阈值）</option>
                <option value="above">🚨 价格高于（突破指定价格上限）</option>
                <option value="below">🔻 价格低于（跌破指定价格下限）</option>
              </select>
            </div>

            <div v-show="form.alertType === 'rise' || form.alertType === 'fall'">
              <div class="mb-3">
                <label for="ruleThreshold" class="form-label">涨跌幅阈值 (%)</label>
                <input v-model="form.threshold" type="number" class="form-control" id="ruleThreshold" step="0.1" min="0.1" placeholder="5">
                <div class="form-text">价格变动超过此百分比时触发告警</div>
              </div>
              <div class="mb-3">
                <label for="ruleDays" class="form-label">统计天数</label>
                <input v-model="form.days" type="number" class="form-control" id="ruleDays" min="1" placeholder="1">
                <div class="form-text">计算价格变动的天数周期</div>
              </div>
            </div>

            <div v-show="form.alertType === 'above' || form.alertType === 'below'">
              <div class="mb-3">
                <label for="ruleTargetPrice" class="form-label">目标价格</label>
                <input v-model="form.targetPrice" type="number" class="form-control" id="ruleTargetPrice" step="0.01" min="0.01" placeholder="100.00">
                <div class="form-text">当价格突破此值时触发告警</div>
              </div>
            </div>

            <div class="mb-3">
              <label for="ruleCooldown" class="form-label">重复触发冷却（分钟）</label>
              <input v-model="form.cooldown" type="number" class="form-control" id="ruleCooldown" value="0" min="0" placeholder="0=不限制">
              <div class="form-text">0=每次满足条件都记录；>0=上次触发后等待指定分钟才再次记录</div>
            </div>

            <div class="mb-3" v-show="form.alertType === 'rise' || form.alertType === 'fall'">
              <label for="ruleFollowup" class="form-label">续警阈值 (%)</label>
              <input v-model="form.followupThreshold" type="number" class="form-control" id="ruleFollowup" step="0.1" min="0.1" placeholder="1">
              <div class="form-text">首次预警后，价格再波动超过此比例则续警（默认1%）</div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="saveRule">保存规则</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AlertRuleItem from '../components/AlertRuleItem.vue'

const API = '/api'

const props = defineProps({
  preselectedStock: { type: Object, default: null },
})

const stocks = ref([])
const rules = ref([])
const toasts = ref([])
const preSelectedStock = ref(null)
const preSelectedStockId = ref(null)

const form = ref({ ruleId: null, stockId: '', alertType: 'rise', threshold: 5, days: 1, targetPrice: '', cooldown: 0, followupThreshold: 1 })
const isEditing = computed(() => !!form.value.ruleId)

const filteredRules = computed(() => {
  if (preSelectedStockId.value) {
    return rules.value.filter(r => r.stock_id === preSelectedStockId.value)
  }
  return rules.value
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

function showCreateModal() {
  form.value = { ruleId: null, stockId: '', alertType: 'rise', threshold: 5, days: 1, targetPrice: '', cooldown: 0, followupThreshold: 1 }
  new window.bootstrap.Modal(document.getElementById('ruleModal')).show()
}

async function editRule(ruleId) {
  await loadStocks()
  const rule = rules.value.find(r => r.id === ruleId)
  if (!rule) { showToast('规则不存在', 'danger'); return }
  form.value = {
    ruleId: rule.id,
    stockId: rule.stock_id,
    alertType: rule.alert_type,
    threshold: rule.threshold_percent || 5,
    days: rule.days || 1,
    targetPrice: rule.target_price || '',
    cooldown: rule.cooldown_minutes || 0,
    followupThreshold: rule.followup_threshold || 1
  }
  new window.bootstrap.Modal(document.getElementById('ruleModal')).show()
}

async function saveRule() {
  const isEdit = !!form.value.ruleId
  let stockId

  if (preSelectedStockId.value && !isEdit) {
    stockId = preSelectedStockId.value
  } else {
    stockId = parseInt(form.value.stockId)
    if (!stockId) { showToast('请选择股票', 'warning'); return }
  }

  const data = { stock_id: stockId, alert_type: form.value.alertType, enabled: true }

  if (form.value.alertType === 'rise' || form.value.alertType === 'fall') {
    const tp = parseFloat(form.value.threshold)
    const days = parseInt(form.value.days)
    if (!tp || tp <= 0) { showToast('请输入有效的涨跌幅阈值', 'warning'); return }
    if (!days || days < 1) { showToast('统计天数至少为1', 'warning'); return }
    data.threshold_percent = tp
    data.days = days
  } else {
    const tp = parseFloat(form.value.targetPrice)
    if (!tp || tp <= 0) { showToast('请输入有效的目标价格', 'warning'); return }
    data.target_price = tp
    data.threshold_percent = 0
    data.days = 1
  }
  data.cooldown_minutes = parseInt(form.value.cooldown) || 0
  data.followup_threshold = parseFloat(form.value.followupThreshold) || 1.0

  try {
    const url = isEdit ? `${API}/alerts/${form.value.ruleId}` : `${API}/alerts`
    const method = isEdit ? 'PUT' : 'POST'
    const r = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
    if (!r.ok) {
      const err = await r.json()
      throw new Error(err.detail || '保存规则失败')
    }
    window.bootstrap.Modal.getInstance(document.getElementById('ruleModal'))?.hide()
    showToast(isEdit ? '规则更新成功' : '规则创建成功', 'success')
    if (!isEdit) {
      preSelectedStockId.value = null
      preSelectedStock.value = null
    }
    await loadRules()
  } catch (e) { showToast(e.message, 'danger') }
}

async function toggleRule(ruleId) {
  try {
    const r = await fetch(`${API}/alerts/${ruleId}/toggle`, { method: 'POST' })
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '切换失败') }
    showToast('告警规则已切换', 'success')
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

async function loadStocks() {
  try {
    const r = await fetch(`${API}/stocks`)
    if (r.ok) stocks.value = await r.json()
  } catch (e) { showToast('加载股票失败', 'danger') }
}

async function loadRules() {
  try {
    const r = await fetch(`${API}/alerts`)
    if (!r.ok) throw new Error('加载告警规则失败')
    rules.value = await r.json()
  } catch (e) { showToast(e.message, 'danger') }
}

onMounted(async () => {
  if (props.preselectedStock) {
    preSelectedStockId.value = props.preselectedStock.id
    preSelectedStock.value = props.preselectedStock
  }
  await Promise.all([loadStocks(), loadRules()])
})
</script>

<style scoped>
.stock-tag { display: inline-block; padding: 0.35em 0.7em; background: #e9ecef; border-radius: 1rem; font-size: 0.875rem; font-weight: 500; }
</style>
