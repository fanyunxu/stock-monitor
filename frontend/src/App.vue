<template>
  <div>
    <NavBar v-if="navState.visible && activeTab !== 'simple'" />
    <component :is="currentView" v-bind="currentProps" />

    <!-- 导航栏隐藏时显示浮动恢复按钮 -->
    <div v-if="!navState.visible && activeTab !== 'simple'" class="float-menu-btn" @click="navState.visible = true">
      <i class="bi bi-list"></i>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, provide, computed } from 'vue'
import NavBar from './components/NavBar.vue'
import Alerts from './views/Alerts.vue'
import Server from './views/Server.vue'
import Logs from './views/Logs.vue'
import Simple from './views/Simple.vue'

const TABS = {
  alerts: { component: Alerts, props: {} },
  server: { component: Server, props: {} },
  logs: { component: Logs, props: {} },
  simple: { component: Simple, props: {} },
}

const activeTab = ref(sessionStorage.getItem('initialTab') || 'alerts')
const navState = reactive({ visible: true })

// Clear the stored tab after reading
sessionStorage.removeItem('initialTab')

// Provide activeTab and switchTab to all descendants via inject
provide('activeTab', activeTab)
provide('navState', navState)

function switchTab(tab, opts = {}) {
  if (tab === 'simple') {
    window.location.href = '/idea'
    return
  }
  activeTab.value = tab
}

provide('switchTab', switchTab)

const currentView = computed(() => TABS[activeTab.value]?.component || Alerts)
const currentProps = computed(() => TABS[activeTab.value]?.props || {})
</script>

<style>
:root {
  --success-color: #198754;
  --danger-color: #dc3545;
}
body {
  background-color: #f8f9fa;
}
body.dark-mode,
body.dark-mode #app {
  background-color: #2b2b2b !important;
}
.card {
  border: none;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.price-up { color: var(--danger-color); }
.price-down { color: var(--success-color); }
.price-unchanged { color: #6c757d; }
.alert-type-rise { color: var(--danger-color); }
.alert-type-fall { color: var(--success-color); }
.toast-container {
  position: fixed;
  top: 80px;
  right: 20px;
  z-index: 1060;
}
.nav-link.active { font-weight: 600; }
.stock-card { transition: transform 0.2s; cursor: pointer; }
.stock-card:hover { transform: translateY(-2px); }
.triggered-badge {
  font-size: 0.6rem;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.acknowledged { opacity: 0.6; }
.float-menu-btn {
  position: fixed;
  top: 10px;
  left: 10px;
  z-index: 9999;
  background: rgba(13, 110, 253, 0.9);
  color: white;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1.2rem;
  opacity: 0.8;
  transition: opacity 0.2s;
}
.float-menu-btn:hover {
  opacity: 1;
}
</style>
