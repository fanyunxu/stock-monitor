<template>
  <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
    <div class="container">
      <button class="navbar-brand btn btn-link text-decoration-none text-white p-0" @click="switchTab('quant')">
        <i class="bi bi-graph-up-arrow me-2"></i>量化助手
        <span class="badge bg-warning text-dark ms-1" style="font-size: 0.65rem" title="前端版本">前{{ frontendVersion }}</span>
        <span class="badge bg-dark ms-1" style="font-size: 0.65rem" title="后端版本">后{{ backendVersion || '—' }}</span>
      </button>
      <div class="d-flex align-items-center">
        <button class="btn btn-outline-light btn-sm me-2" @click="navState.visible = false" title="隐藏导航栏">
          <i class="bi bi-chevron-double-up"></i>
        </button>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
          <span class="navbar-toggler-icon"></span>
        </button>
      </div>
      <div class="collapse navbar-collapse" id="navbarNav">
        <ul class="navbar-nav ms-auto">
          <li class="nav-item" v-for="item in navItems" :key="item.tab">
            <button class="nav-link btn btn-link text-white" :class="{ active: activeTab === item.tab }" @click="switchTab(item.tab)">
              <i :class="item.icon + ' me-1'"></i>{{ item.label }}
            </button>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref, inject, onMounted } from 'vue'
import { FRONTEND_VERSION } from '../config.js'

const frontendVersion = FRONTEND_VERSION
const backendVersion = ref('')
const activeTab = inject('activeTab')
const navState = inject('navState')
const switchTab = inject('switchTab')

const navItems = [
  { tab: 'alerts',    label: '股票', icon: 'bi bi-bar-chart-fill' },
  { tab: 'ttrade',    label: '做T', icon: 'bi bi-arrow-left-right' },
  { tab: 'server',    label: '服务器监控', icon: 'bi bi-server' },
  { tab: 'logs',      label: '运行日志', icon: 'bi bi-journal-text' },
  { tab: 'simple',    label: '极简模式', icon: 'bi bi-text-left' },
]

onMounted(async () => {
  try {
    const r = await fetch('/api/version')
    if (r.ok) backendVersion.value = (await r.json()).backend_version || ''
  } catch (e) {}
})
</script>
