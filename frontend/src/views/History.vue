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
        <h5 class="mb-0">
          <i class="bi bi-clock-history me-2"></i>{{ pageTitle }}
        </h5>
        <div>
          <button class="btn btn-outline-primary btn-sm" @click="loadLogs">
            <i class="bi bi-arrow-clockwise me-1"></i>刷新
          </button>
          <button class="btn btn-outline-danger btn-sm" @click="clearAll">
            <i class="bi bi-trash me-1"></i>清空
          </button>
        </div>
      </div>
      <div class="card-body">
        <!-- Desktop table -->
        <div class="table-responsive d-none d-md-block">
          <table class="table table-hover">
            <thead>
              <tr>
                <th>股票</th>
                <th>告警类型</th>
                <th>阈值</th>
                <th>触发价格</th>
                <th>时间</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="filteredLogs.length === 0">
                <td colspan="7" class="text-center text-muted py-4">
                  <i class="bi bi-inbox fs-1"></i>
                  <p class="mt-2">暂无告警历史</p>
                </td>
              </tr>
              <AlertHistoryItem
                v-for="log in filteredLogs"
                :key="log.id"
                :log="log"
                @acknowledge="acknowledge"
                @detail="showDetail"
              />
            </tbody>
          </table>
        </div>

        <!-- Mobile cards -->
        <div class="d-md-none">
          <div v-if="filteredLogs.length === 0" class="text-center text-muted py-4">
            <i class="bi bi-inbox fs-1"></i>
            <p class="mt-2">暂无告警历史</p>
          </div>
          <AlertHistoryItem
            v-for="log in filteredLogs"
            :key="'m-' + log.id"
            :log="log"
            @acknowledge="acknowledge"
            @detail="showDetail"
          />
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div class="modal fade" id="logDetailModal" tabindex="-1">
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="bi bi-info-circle me-2"></i>触发详情</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body" v-if="detailLog">
            <table class="table table-sm table-borderless mb-0">
              <tr><td class="text-muted small">股票</td><td><strong>{{ detailLog.stock_name || detailLog.stock_symbol }}</strong> ({{ detailLog.stock_symbol }})</td></tr>
              <tr><td class="text-muted small">市场</td><td>{{ detailLog.market }}</td></tr>
              <tr><td class="text-muted small">告警类型</td><td>{{ getTypeLabel(detailLog.alert_type) }}</td></tr>
              <tr><td class="text-muted small">告警条件</td><td>{{ getConditionDesc(detailLog) }}</td></tr>
              <tr><td class="text-muted small">触发价格</td><td><strong>{{ getCurrency(detailLog.market) }}{{ (detailLog.triggered_price || 0).toFixed(2) }}</strong></td></tr>
              <tr><td class="text-muted small">触发时间</td><td>{{ formatDate(detailLog.triggered_at) }}</td></tr>
              <tr><td class="text-muted small">状态</td><td>
                <span v-if="detailLog.acknowledged" class="badge bg-secondary">已确认</span>
                <span v-else class="badge bg-warning text-dark">未确认</span>
              </td></tr>
            </table>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">关闭</button>
            <button v-if="detailLog && !detailLog.acknowledged" type="button" class="btn btn-success btn-sm" @click="ackFromDetail">确认告警</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AlertHistoryItem from '../components/AlertHistoryItem.vue'

const API = '/api'

const props = defineProps({
  stockId: { type: Number, default: null },
  stockName: { type: String, default: '' },
})

const logs = ref([])
const pageTitle = ref('告警历史')
const toasts = ref([])
const detailLog = ref(null)

const filteredLogs = computed(() => {
  if (props.stockId) return logs.value.filter(l => l.stock_id === props.stockId)
  return logs.value
})

function showToast(m, t = 'info') {
  const id = Date.now()
  toasts.value.push({ id, message: m, type: t })
  setTimeout(() => removeToast(id), 4000)
}
function removeToast(id) { toasts.value = toasts.value.filter(x => x.id !== id) }

function getCurrency(market) {
  return { HK: 'HK$', US: '$' }[market] || '¥'
}

function getTypeLabel(type) {
  return { rise: '📈 趋势上涨', fall: '📉 趋势下跌', above: '📈 价格突破上限', below: '📉 价格突破下限' }[type] || type
}

function getConditionDesc(log) {
  if (log.alert_type === 'rise' || log.alert_type === 'fall') {
    return `统计 ${log.days || 1} 天内 ${log.alert_type === 'rise' ? '上涨' : '下跌'}幅度达 ${log.threshold_percent || 0}%`
  }
  return `价格${log.alert_type === 'above' ? '高于' : '低于'} ${getCurrency(log.market)}${(log.target_price || 0).toFixed(2)}`
}

function formatDate(d) { return d ? new Date(d).toLocaleString('zh-CN') : '-' }

async function loadLogs() {
  try {
    const r = await fetch(`${API}/alerts/logs`)
    if (!r.ok) throw new Error('加载告警历史失败')
    logs.value = await r.json()
  } catch (e) { showToast(e.message, 'danger') }
}

async function acknowledge(logId) {
  try {
    const r = await fetch(`${API}/alerts/logs/${logId}/acknowledge`, { method: 'POST' })
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || '确认失败') }
    showToast('告警已确认', 'success')
    await loadLogs()
  } catch (e) { showToast(e.message, 'danger') }
}

async function clearAll() {
  if (!confirm('确定要清空所有告警记录吗？此操作不可恢复。')) return
  try {
    const r = await fetch('/api/alerts/logs/clear_all', { method: 'DELETE' })
    if (r.ok) {
      const d = await r.json()
      showToast(d.message || '已清空', 'success')
      await loadLogs()
    } else { showToast('清空失败', 'danger') }
  } catch (e) { showToast('清空失败', 'danger') }
}

function showDetail(log) {
  detailLog.value = log
  new window.bootstrap.Modal(document.getElementById('logDetailModal')).show()
}

async function ackFromDetail() {
  if (!detailLog.value) return
  await acknowledge(detailLog.value.id)
  window.bootstrap.Modal.getInstance(document.getElementById('logDetailModal'))?.hide()
  detailLog.value = null
}

onMounted(async () => {
  if (props.stockName) {
    pageTitle.value = props.stockName + ' - 触发记录'
  }
  await loadLogs()
})
</script>
