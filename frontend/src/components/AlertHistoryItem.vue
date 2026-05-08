<template>
  <!-- Desktop table row -->
  <tr class="d-none d-md-table-row" :class="{ acknowledged }">
    <td><strong>{{ log.stock_name || log.stock_symbol || '未知' }}</strong><br><small class="text-muted">{{ log.stock_symbol }}</small></td>
    <td>
      <span :class="typeInfo.cls">
        <i :class="typeInfo.icon + ' me-1'"></i>{{ typeInfo.label }}
      </span>
    </td>
    <td>{{ thresholdStr }}</td>
    <td>{{ currencySymbol }}{{ (log.triggered_price || 0).toFixed(2) }}</td>
    <td class="small">{{ formatDate(log.triggered_at) }}</td>
    <td>
      <span v-if="acknowledged" class="badge bg-secondary">
        <i class="bi bi-check me-1"></i>已确认
      </span>
      <span v-else class="badge bg-warning text-dark">
        <i class="bi bi-exclamation me-1"></i>新告警
      </span>
    </td>
    <td>
      <button class="btn btn-outline-primary btn-sm" @click="$emit('detail', log)">
        <i class="bi bi-info-lg"></i>
      </button>
      <button v-if="!acknowledged" class="btn btn-success btn-sm" @click="$emit('acknowledge', log.id)">
        <i class="bi bi-check-lg me-1"></i>
      </button>
    </td>
  </tr>

  <!-- Mobile card -->
  <div class="d-md-none card mb-2" :class="{ 'opacity-75': acknowledged }">
    <div class="card-body py-2">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <strong>{{ log.stock_name || log.stock_symbol || '未知' }}</strong><br><small class="text-muted">{{ log.stock_symbol }}</small>
          <span :class="typeInfo.cls + ' ms-2 small'">
            <i :class="typeInfo.icon"></i>{{ typeInfo.label }}
          </span>
        </div>
        <span v-if="acknowledged" class="badge bg-secondary small">已确认</span>
        <span v-else class="badge bg-warning text-dark small">新告警</span>
      </div>
      <div class="text-muted small mt-1">
        触发价格：{{ currencySymbol }}{{ (log.triggered_price || 0).toFixed(2) }} | {{ thresholdStr }}
      </div>
      <div class="text-muted small">{{ formatDate(log.triggered_at) }}</div>
      <div class="mt-1">
        <button class="btn btn-outline-primary btn-sm py-1 px-2" @click="$emit('detail', log)">详情</button>
        <button v-if="!acknowledged" class="btn btn-success btn-sm py-1 px-2 ms-1" @click="$emit('acknowledge', log.id)">确认</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  log: { type: Object, required: true },
})

defineEmits(['acknowledge', 'detail'])

const acknowledged = computed(() => props.log.acknowledged)

const currencySymbol = computed(() => ({ HK: 'HK$', US: '$' })[props.log.market] || '¥')

const typeMap = {
  rise:  { icon: 'bi-caret-up-fill', cls: 'alert-type-rise', label: '上涨' },
  fall:  { icon: 'bi-caret-down-fill', cls: 'alert-type-fall', label: '下跌' },
  above: { icon: 'bi-caret-up-fill', cls: 'alert-type-rise', label: '突破上限' },
  below: { icon: 'bi-caret-down-fill', cls: 'alert-type-fall', label: '突破下限' },
}

const typeInfo = computed(() => typeMap[props.log.alert_type] || typeMap.rise)

const thresholdStr = computed(() => {
  if (props.log.alert_type === 'above' || props.log.alert_type === 'below') {
    return currencySymbol.value + ((props.log.target_price || 0).toFixed(2))
  }
  return (props.log.threshold_percent || 0) + '%'
})

function formatDate(d) { return d ? new Date(d).toLocaleString('zh-CN') : '-' }
</script>
