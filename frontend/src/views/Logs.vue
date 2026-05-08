<template>
  <div class="container mt-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h4 class="mb-0"><i class="bi bi-journal-text me-2"></i>告警检查运行日志</h4>
      <button class="btn btn-outline-primary btn-sm" @click="loadLogs">
        <i class="bi bi-arrow-clockwise me-1"></i>刷新
      </button>
    </div>

    <div class="card mb-3">
      <div class="card-body py-2">
        <div class="row text-muted small">
          <div class="col-12 col-md-4 mb-1 mb-md-0"><i class="bi bi-clock me-1"></i>保留最近100条</div>
          <div class="col-6 col-md-4"><i class="bi bi-info-circle me-1"></i>每次检查后记录</div>
          <div class="col-6 col-md-4"><i class="bi bi-server me-1"></i>/app/logs/alert_check.log</div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-5 text-muted">
      <div class="spinner-border spinner-border-sm me-2" role="status"></div>
      加载中...
    </div>

    <!-- Empty -->
    <div v-else-if="logs.length === 0" class="text-center py-5">
      <i class="bi bi-inbox fs-1 text-muted"></i>
      <p class="text-muted mt-2">暂无日志记录</p>
    </div>

    <!-- Table (Desktop) -->
    <div v-if="logs.length > 0" class="card d-none d-md-block">
      <div class="table-responsive">
        <table class="table table-hover log-table mb-0">
          <thead>
            <tr>
              <th style="width:160px"><i class="bi bi-clock me-1"></i>时间</th>
              <th style="width:180px"><i class="bi bi-collection me-1"></i>检查股票</th>
              <th style="width:160px"><i class="bi bi-bell me-1"></i>触发告警</th>
              <th><i class="bi bi-circle-fill me-1" style="font-size:0.5rem"></i>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(log, i) in reversedLogs" :key="i">
              <td><span class="text-muted">{{ log.timestamp || '-' }}</span></td>
              <td>{{ log.stock_count || '-' }}</td>
              <td>{{ log.triggered || '-' }}</td>
              <td><span class="badge" :class="getBadgeClass(log.status)">{{ log.status || '-' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Cards (Mobile) -->
    <div v-if="logs.length > 0" class="d-md-none">
      <div v-for="(log, i) in reversedLogs" :key="'m-' + i" class="card mb-2">
        <div class="card-body py-2">
          <div class="d-flex justify-content-between align-items-center">
            <span class="text-muted small">{{ log.timestamp || '-' }}</span>
            <span class="badge" :class="getBadgeClass(log.status)">{{ log.status || '-' }}</span>
          </div>
          <div class="mt-1">
            <span class="text-muted small">检查股票：</span><span>{{ log.stock_count || '-' }}</span>
            <span class="text-muted small ms-2">触发：</span><span>{{ log.triggered || '-' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="alert alert-danger mt-3">
      <i class="bi bi-exclamation-triangle me-2"></i>{{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const API = '/api'

const logs = ref([])
const loading = ref(true)
const error = ref('')
let timer = null

const reversedLogs = computed(() => [...logs.value].reverse())

function getBadgeClass(status) {
  if (!status) return 'bg-secondary'
  const s = status.toLowerCase()
  if (s.includes('error')) return 'bg-danger'
  if (s.includes('warn')) return 'bg-warning text-dark'
  return 'bg-success'
}

async function loadLogs() {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`${API}/logs`)
    if (!r.ok) throw new Error('获取日志失败')
    logs.value = await r.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadLogs()
  timer = setInterval(loadLogs, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.log-table { font-size: 0.9rem; }
</style>
