<template>
  <!-- Desktop: returns <td> cells only, parent provides <tr> -->
  <template class="d-none d-md-table-row">
    <td><span class="text-muted">{{ log.timestamp || '-' }}</span></td>
    <td>{{ log.stock_count || '-' }}</td>
    <td>{{ log.triggered || '-' }}</td>
    <td>
      <span class="badge" :class="badgeClass">{{ log.status || '-' }}</span>
    </td>
  </template>

  <!-- Mobile: returns a card div -->
  <div class="d-md-none card mb-2">
    <div class="card-body py-2">
      <div class="d-flex justify-content-between align-items-center">
        <span class="text-muted small">{{ log.timestamp || '-' }}</span>
        <span class="badge" :class="badgeClass">{{ log.status || '-' }}</span>
      </div>
      <div class="mt-1">
        <span class="text-muted small">检查股票：</span><span>{{ log.stock_count || '-' }}</span>
        <span class="text-muted small ms-2">触发：</span><span>{{ log.triggered || '-' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  log: { type: Object, required: true },
})

const badgeClass = computed(() => {
  if (!props.log.status) return 'bg-secondary'
  const s = props.log.status.toLowerCase()
  if (s.includes('error')) return 'bg-danger'
  if (s.includes('warn')) return 'bg-warning text-dark'
  return 'bg-success'
})
</script>
