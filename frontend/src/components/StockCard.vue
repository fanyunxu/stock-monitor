<template>
  <div class="col-md-4 col-lg-3 mb-3 position-relative">
    <span v-if="hasTriggered"
          class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger triggered-badge"
          style="z-index:5">
      <i class="bi bi-exclamation-triangle-fill"></i>
    </span>
    <div class="card stock-card h-100" @click="$emit('click-card')">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <h5 class="card-title mb-1">
              {{ stock.symbol }}
              <span v-if="ruleCount > 0" class="badge bg-info" style="font-size:0.7rem">
                {{ ruleCount }}条规则
              </span>
            </h5>
            <p class="text-muted small mb-0">{{ stock.name || '' }}</p>
          </div>
          <button class="btn btn-outline-danger btn-sm" @click.stop="$emit('remove', stock.symbol)" title="移除">
            <i class="bi bi-trash"></i>
          </button>
        </div>
        <div class="mt-3">
          <h4 class="mb-1" :class="priceClass">{{ formatPrice }}</h4>
          <span class="small" :class="priceClass">
            <i :class="priceIcon"></i> {{ formatChange }}
          </span>
          <span class="text-muted small ms-2">{{ marketLabel }}</span>
        </div>
      </div>
      <div class="card-footer bg-transparent" @click.stop>
        <button class="btn btn-outline-info btn-sm" @click.stop="$emit('view-history')">
          <i class="bi bi-clock-history me-1"></i>历史
        </button>
        <button class="btn btn-outline-primary btn-sm" @click.stop="$emit('set-alert')">
          <i class="bi bi-bell me-1"></i>设置告警
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stock: { type: Object, required: true },
  ruleCount: { type: Number, default: 0 },
  hasTriggered: { type: Boolean, default: false },
  triggeredLogs: { type: Array, default: () => [] },
})

defineEmits(['remove', 'click-card', 'view-history', 'set-alert'])

const marketLabel = computed(() => ({ CN: 'A股', HK: '港股', US: '美股' })[props.stock.market] || props.stock.market)

const currencySymbol = computed(() => ({ HK: 'HK$', US: '$' })[props.stock.market] || '¥')

const priceClass = computed(() => {
  if (props.stock.price_change_percent > 0) return 'price-up'
  if (props.stock.price_change_percent < 0) return 'price-down'
  return 'price-unchanged'
})

const priceIcon = computed(() => {
  if (props.stock.price_change_percent > 0) return 'bi bi-caret-up-fill'
  if (props.stock.price_change_percent < 0) return 'bi bi-caret-down-fill'
  return 'bi bi-dash'
})

const formatPrice = computed(() => {
  if (props.stock.current_price === null) return 'N/A'
  return currencySymbol.value + props.stock.current_price.toFixed(2)
})

const formatChange = computed(() => {
  if (props.stock.price_change_percent === null) return ''
  const sign = props.stock.price_change_percent > 0 ? '+' : ''
  return sign + props.stock.price_change_percent.toFixed(2) + '%'
})
</script>
