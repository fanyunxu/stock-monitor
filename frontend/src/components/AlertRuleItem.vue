<template>
  <!-- Desktop card -->
  <div class="col-md-6 col-lg-4 mb-3 d-none d-md-block">
    <div class="card rule-card h-100">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start mb-3">
          <div>
            <h5 class="mb-1">{{ rule.stock_symbol || '未知' }}</h5>
            <p class="text-muted small mb-0">{{ rule.stock_name || '' }}</p>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" :checked="rule.enabled" @change="$emit('toggle', rule.id)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="alert-info p-2 rounded bg-light">
          <div class="d-flex align-items-center" :class="typeInfo.cls">
            <i :class="typeInfo.icon + ' me-2'"></i>
            <strong>{{ typeInfo.label }}</strong>
          </div>
          <div class="mt-1 small text-muted">{{ desc }}</div>
        </div>
      </div>
      <div class="card-footer bg-transparent">
        <button class="btn btn-outline-primary btn-sm" @click="$emit('edit', rule.id)"><i class="bi bi-pencil me-1"></i>编辑</button>
        <button class="btn btn-outline-danger btn-sm" @click="$emit('delete', rule.id)"><i class="bi bi-trash me-1"></i>删除</button>
      </div>
    </div>
  </div>

  <!-- Mobile card -->
  <div class="d-md-none mb-2">
    <div class="card">
      <div class="card-body py-2">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <strong>{{ rule.stock_symbol || '未知' }}</strong>
            <span class="text-muted small ms-2">{{ rule.stock_name || '' }}</span>
          </div>
          <label class="toggle-switch" style="transform: scale(0.8)">
            <input type="checkbox" :checked="rule.enabled" @change="$emit('toggle', rule.id)">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="mt-2 small">
          <span :class="typeInfo.cls">
            <i :class="typeInfo.icon"></i> {{ typeInfo.label }}
          </span>
          <span class="text-muted ms-2">{{ desc }}</span>
        </div>
        <div class="mt-2">
          <button class="btn btn-outline-primary btn-sm py-1 px-2" @click="$emit('edit', rule.id)"><i class="bi bi-pencil"></i> 编辑</button>
          <button class="btn btn-outline-danger btn-sm py-1 px-2 ms-1" @click="$emit('delete', rule.id)"><i class="bi bi-trash"></i> 删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  rule: { type: Object, required: true },
  currencyFn: { type: Function, default: () => '¥' },
})

defineEmits(['toggle', 'edit', 'delete'])

const typeMap = {
  rise:  { icon: 'bi-caret-up-fill', cls: 'alert-type-rise', label: '趋势上涨', desc: r => `上涨超过 ${r.threshold_percent}%（${r.days}天）${r.followup_threshold ? '，续警' + r.followup_threshold + '%' : ''}` },
  fall:  { icon: 'bi-caret-down-fill', cls: 'alert-type-fall', label: '趋势下跌', desc: r => `下跌超过 ${r.threshold_percent}%（${r.days}天）${r.followup_threshold ? '，续警' + r.followup_threshold + '%' : ''}` },
  above: { icon: 'bi-arrow-up-circle-fill', cls: 'alert-type-rise', label: '价格高于', desc: r => `突破 ${props.currencyFn('CN')}${r.target_price}` },
  below: { icon: 'bi-arrow-down-circle-fill', cls: 'alert-type-fall', label: '价格低于', desc: r => `跌破 ${props.currencyFn('CN')}${r.target_price}` },
}

const typeInfo = computed(() => typeMap[props.rule.alert_type] || typeMap.rise)
const desc = computed(() => typeInfo.value.desc(props.rule).replace('¥', props.currencyFn('CN')))
</script>

<style scoped>
.toggle-switch { position: relative; width: 50px; height: 26px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: 0.3s; border-radius: 34px; }
.toggle-slider:before { position: absolute; content: ""; height: 20px; width: 20px; left: 3px; bottom: 3px; background-color: white; transition: 0.3s; border-radius: 50%; }
input:checked + .toggle-slider { background-color: var(--success-color); }
input:checked + .toggle-slider:before { transform: translateX(24px); }
.rule-card { transition: all 0.2s; }
.rule-card:hover { transform: translateY(-2px); }
</style>
