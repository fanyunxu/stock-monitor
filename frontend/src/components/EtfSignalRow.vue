<template>
  <tr :class="refreshingRow ? 'table-warning' : ''">
    <td>
      <strong>{{ sig.symbol }}</strong><br>
      <small class="text-muted">{{ sig.name || '' }}</small>
    </td>
    <!-- 信号 -->
    <td>
      <span v-if="sig.buy_signal" class="badge bg-success">买入</span>
      <span v-else-if="sig.sell_signal" class="badge bg-danger">卖出</span>
      <span v-else class="badge bg-secondary">观望</span>
      <div class="small text-muted mt-1">{{ sig.action || '—' }}</div>
    </td>
    <!-- 原因 -->
    <td>
      <small class="text-muted" style="max-width:120px;display:block;">{{ sig.reason || '—' }}</small>
    </td>
    <!-- 趋势 -->
    <td>
      <i class="bi" :class="sig.trend === 'UP' ? 'bi-arrow-up text-success' : 'bi-arrow-down text-danger'"></i>
      {{ sig.trend === 'UP' ? '上升' : '下降' }}
    </td>
    <!-- 回调 -->
    <td>
      <span :class="sig.pullback ? 'text-success' : 'text-muted'">
        {{ sig.pullback ? '✓ 回踩' : '—' }}
      </span>
    </td>
    <!-- 情绪 -->
    <td>
      <span class="badge" :class="sig.sentiment === 'NORMAL' ? 'bg-info' : 'bg-warning'">
        {{ sig.sentiment === 'NORMAL' ? '正常' : '过热' }}
      </span>
    </td>
    <!-- 量比信号 -->
    <td>
      <span v-if="sig.volume_signal === 'STRONG'" class="badge bg-danger">强</span>
      <span v-else-if="sig.volume_signal === 'WEAK'" class="badge bg-secondary">弱</span>
      <span v-else-if="sig.volume_signal === 'RISK'" class="badge bg-warning text-dark">险</span>
      <span v-else-if="sig.volume_signal === 'NORMAL'" class="badge bg-success">常</span>
      <span v-else class="text-muted">—</span>
    </td>
    <!-- 突破 -->
    <td>
      <span v-if="sig.breakout" class="text-success fw-bold">✓</span>
      <span v-else class="text-muted">—</span>
    </td>
    <!-- MA -->
    <td class="text-end"><code>{{ sig.ma5 != null ? sig.ma5.toFixed(3) : '—' }}</code></td>
    <td class="text-end"><code>{{ sig.ma10 != null ? sig.ma10.toFixed(3) : '—' }}</code></td>
    <td class="text-end"><code>{{ sig.ma20 != null ? sig.ma20.toFixed(3) : '—' }}</code></td>
    <!-- 当前价 -->
    <td class="text-end">
      <strong>{{ sig.current_price != null ? sig.current_price.toFixed(3) : '—' }}</strong>
      <div v-if="sig.daily_return != null" class="small" :class="sig.daily_return >= 0 ? 'text-danger' : 'text-success'">
        {{ sig.daily_return >= 0 ? '+' : '' }}{{ sig.daily_return.toFixed(2) }}%
      </div>
    </td>
    <!-- 量比 -->
    <td class="text-center">
      <span :class="sig.volume_ratio > 1.5 ? 'text-danger fw-bold' : sig.volume_ratio > 1 ? 'text-warning' : ''">
        {{ sig.volume_ratio != null ? sig.volume_ratio.toFixed(2) : '—' }}
      </span>
    </td>
    <!-- 连涨 -->
    <td class="text-center">
      <span v-if="sig.consecutive_up_days >= 3" class="badge bg-danger">{{ sig.consecutive_up_days }}天</span>
      <span v-else-if="sig.consecutive_up_days > 0" class="badge bg-warning">{{ sig.consecutive_up_days }}天</span>
      <span v-else class="text-muted">—</span>
    </td>
    <!-- 累计涨幅 -->
    <td class="text-end">
      <span :class="sig.cumulative_return >= 3 ? 'text-danger fw-bold' : sig.cumulative_return >= 0 ? 'text-dark' : 'text-success'">
        {{ sig.cumulative_return != null ? sig.cumulative_return.toFixed(2) + '%' : '—' }}
      </span>
    </td>
    <!-- 成本 -->
    <td class="text-end">
      <span v-if="sig.cost" class="small">{{ sig.cost.toFixed(3) }}</span>
      <span v-else class="text-muted small">—</span>
    </td>
    <!-- 持仓 -->
    <td class="text-end">
      <span v-if="sig.quantity" class="small">{{ sig.quantity }}股</span>
      <span v-else class="text-muted small">—</span>
    </td>
    <!-- 盈亏额 -->
    <td class="text-end">
      <span v-if="sig.profit_loss != null" :class="sig.profit_loss >= 0 ? 'text-danger fw-bold' : 'text-success'">
        {{ sig.profit_loss >= 0 ? '+' : '' }}{{ sig.profit_loss.toFixed(0) }}
      </span>
      <span v-else class="text-muted">—</span>
    </td>
    <!-- 盈亏% -->
    <td class="text-end">
      <span v-if="sig.profit_loss_pct != null" :class="sig.profit_loss_pct >= 0 ? 'text-danger fw-bold' : 'text-success'">
        {{ sig.profit_loss_pct >= 0 ? '+' : '' }}{{ sig.profit_loss_pct.toFixed(1) }}%
      </span>
      <span v-else class="text-muted">—</span>
    </td>
    <!-- 操作 -->
    <td>
      <button class="btn btn-outline-primary btn-sm py-0 px-1 me-1" @click="$emit('edit', sig)" title="编辑持仓" :disabled="refreshing">
        <i class="bi bi-pencil"></i>
      </button>
      <button class="btn btn-outline-warning btn-sm py-0 px-1 me-1" @click="$emit('rule', sig)" title="告警规则" :disabled="refreshing">
        <i class="bi bi-bell"></i>
      </button>
      <button class="btn btn-outline-danger btn-sm py-0 px-1" @click="$emit('remove', sig.symbol)" :disabled="refreshing">
        <i class="bi bi-trash"></i>
      </button>
    </td>
  </tr>
</template>

<script setup>
const props = defineProps({
  sig: { type: Object, required: true },
  refreshingRow: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
})

defineEmits(['edit', 'remove', 'rule'])
</script>

<style scoped>
code { font-size: 0.8rem; color: #333; }
</style>
