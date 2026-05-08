<template>
  <div class="container mt-4">
    <div class="row">
      <!-- 主机信息 -->
      <div class="col-md-4">
        <div class="card">
          <div class="card-header bg-primary text-white">📍 主机信息</div>
          <div class="card-body">
            <table class="table table-sm table-borderless mb-0">
              <tr><td class="text-muted">主机名</td><td class="fw-bold">{{ sysInfo.hostname || '-' }}</td></tr>
              <tr><td class="text-muted">CPU 型号</td><td class="fw-bold text-primary" style="font-size:0.85rem">{{ sysInfo.cpu?.model || '-' }}</td></tr>
              <tr><td class="text-muted">物理核心</td><td>{{ sysInfo.cpu?.count || '-' }}</td></tr>
              <tr><td class="text-muted">逻辑核心</td><td>{{ sysInfo.cpu?.count_logical || '-' }}</td></tr>
            </table>
          </div>
        </div>
      </div>

      <!-- CPU -->
      <div class="col-md-4">
        <div class="card">
          <div class="card-header bg-warning text-dark">🧠 CPU 利用率</div>
          <div class="card-body text-center">
            <div class="display-4 fw-bold" :class="cpuPercent > 80 ? 'text-danger' : cpuPercent > 60 ? 'text-warning' : 'text-primary'">
              {{ sysInfo.cpu?.percent ?? '-' }}%
            </div>
            <div class="progress mt-3 cpu-bar">
              <div class="progress-bar" :class="cpuBarClass" :style="{ width: (sysInfo.cpu?.percent || 0) + '%' }">{{ sysInfo.cpu?.percent || 0 }}%</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 温度 -->
      <div class="col-md-4">
        <div class="card">
          <div class="card-header bg-danger text-white">🌡️ CPU 温度</div>
          <div class="card-body text-center">
            <div class="display-4 fw-bold" :class="sysInfo.cpu?.temperature_c > 80 ? 'text-danger' : 'text-success'">
              {{ sysInfo.cpu?.temperature_c ?? 'N/A' }}
            </div>
            <div class="text-muted">°C</div>
            <div class="mt-2 badge" :class="sysInfo.cpu?.temperature_c > 80 ? 'bg-danger' : 'bg-success'">
              {{ sysInfo.cpu?.temperature_c > 80 ? '⚠️ 过热' : sysInfo.cpu?.temperature_c != null ? '✅ 正常' : '无法获取' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="row">
      <!-- 内存 -->
      <div class="col-md-6">
        <div class="card">
          <div class="card-header bg-success text-white">🧬 内存使用情况</div>
          <div class="card-body">
            <div class="d-flex justify-content-between mb-2">
              <span class="fw-bold">{{ sysInfo.memory?.used_gb || '-' }} GB</span>
              <span class="text-muted">/</span>
              <span class="text-muted">{{ sysInfo.memory?.total_gb || '-' }} GB<span v-if="sysInfo.memory?.slots" class="text-muted ms-1">({{ sysInfo.memory?.slots }}条)</span></span>
            </div>
            <div class="progress mem-bar">
              <div class="progress-bar" :class="memBarClass" :style="{ width: (sysInfo.memory?.percent || 0) + '%' }">{{ sysInfo.memory?.percent || 0 }}%</div>
            </div>
            <div class="mt-2 d-flex justify-content-between">
              <span class="text-muted">可用: <span class="fw-bold">{{ sysInfo.memory?.available_gb || '-' }}</span> GB</span>
              <span class="fw-bold" :class="memPercentClass">{{ sysInfo.memory?.percent || '-' }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 磁盘 -->
      <div class="col-md-6">
        <div class="card">
          <div class="card-header bg-info text-white">💾 磁盘使用情况</div>
          <div class="card-body p-0">
            <div v-if="sysInfo.disks?.length" class="px-3 py-2">
              <div v-for="d in sysInfo.disks" :key="d.device" class="disk-row">
                <div class="d-flex justify-content-between align-items-center">
                  <div>
                    <span v-if="d.model" class="fw-bold" style="font-size:0.85rem">{{ d.model }}</span>
                    <span v-else class="disk-name">{{ d.device }}</span>
                    <span class="disk-mount">({{ d.mountpoint }})</span>
                  </div>
                  <span class="fw-bold" :class="d.percent > 80 ? 'text-danger' : 'text-success'">{{ d.percent }}%</span>
                </div>
                <div class="progress progress-bar-small mt-1">
                  <div class="progress-bar" :class="d.percent > 80 ? 'bg-danger' : d.percent > 60 ? 'bg-warning' : 'bg-info'" :style="{ width: d.percent + '%' }"></div>
                </div>
                <div class="d-flex justify-content-between text-muted mt-1" style="font-size:0.8rem">
                  <span>已用 {{ d.used_gb }} GB</span>
                  <span>空闲 {{ d.free_gb }} GB</span>
                </div>
              </div>
            </div>
            <div v-else class="text-center text-muted py-3">未找到磁盘信息</div>
          </div>
        </div>
      </div>
    </div>

    <div class="text-center text-muted mt-2">
      <small>自动刷新: <span>{{ countdown }}</span>秒 | <a href="#" @click.prevent="refreshNow">立即刷新</a></small>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const API = '/api'
const REFRESH_SEC = 30

const sysInfo = ref({})
const countdown = ref(REFRESH_SEC)
let timer = null

const cpuPercent = computed(() => sysInfo.value.cpu?.percent ?? 0)
const cpuBarClass = computed(() => {
  const p = cpuPercent.value
  return p > 80 ? 'bg-danger' : p > 60 ? 'bg-warning' : 'bg-primary'
})
const memPercent = computed(() => sysInfo.value.memory?.percent ?? 0)
const memBarClass = computed(() => {
  const p = memPercent.value
  return p > 80 ? 'bg-danger' : p > 60 ? 'bg-warning' : 'bg-success'
})
const memPercentClass = computed(() => {
  const p = memPercent.value
  return p > 80 ? 'text-danger' : p > 60 ? 'text-warning' : 'text-success'
})

async function loadInfo() {
  try {
    const r = await fetch(`${API}/system/info`)
    if (!r.ok) return
    sysInfo.value = await r.json()
  } catch (e) { console.error(e) }
}

function tick() {
  countdown.value--
  if (countdown.value <= 0) {
    countdown.value = REFRESH_SEC
    loadInfo()
  }
}

function refreshNow() {
  countdown.value = REFRESH_SEC
  loadInfo()
}

onMounted(async () => {
  await loadInfo()
  timer = setInterval(tick, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.progress { height: 1.5rem; }
.progress-bar-small { height: 1rem; font-size: 0.75rem; }
.disk-row { border-bottom: 1px solid #eee; padding: 0.75rem 0; }
.disk-row:last-child { border-bottom: none; }
.disk-name { font-weight: 600; color: #333; }
.disk-mount { color: #888; font-size: 0.85rem; }
.cpu-bar, .mem-bar { height: 2rem; font-size: 1rem; }
</style>
