<template>
  <tr :class="refreshingRow ? 'table-warning' : ''">
    <td>
      <strong>{{ sig.symbol }}</strong>
      <span v-if="sig.instrument_type === 'ETF'" class="badge bg-primary ms-1" style="font-size:0.65rem;">ETF</span>
      <span v-else-if="sig.instrument_type === 'STOCK'" class="badge bg-info ms-1" style="font-size:0.65rem;">股票</span>
      <br>
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
    <td class="reason-cell" :title="fullReason(sig)">
      <div class="small fw-semibold text-dark">{{ sig.reason || '—' }}</div>
      <div v-if="sig.strategy_profile" class="small text-muted">
        策略：{{ sig.strategy_profile === 'ETF_TREND' ? 'ETF趋势' : '股票突破' }}
      </div>
      <div class="small text-muted reason-scores">
        买 {{ formatScore(sig.buy_score) }} / 卖 {{ formatScore(sig.sell_score) }} / 风险 {{ formatScore(sig.risk_score) }}
      </div>
      <ul v-if="reasonFactors(sig).length" class="reason-list small text-muted mb-0 ps-3">
        <li v-for="factor in reasonFactors(sig)" :key="factor">{{ factor }}</li>
      </ul>
      <div v-if="sig.market_reason" class="small text-muted mt-1">市场：{{ sig.market_reason }}</div>
    </td>
    <!-- 评分 -->
    <td class="text-center">
      <span class="badge" :class="scoreClass(sig.signal_score)">
        {{ sig.signal_score != null ? sig.signal_score.toFixed(0) : '—' }}
      </span>
      <div v-if="sig.ai_confidence != null" class="small text-muted">{{ (sig.ai_confidence * 100).toFixed(0) }}%</div>
    </td>
    <!-- 趋势强度 -->
    <td class="text-center">
      <span :class="trendStrengthClass(sig.trend_strength)">
        {{ sig.trend_strength != null ? sig.trend_strength.toFixed(0) : '—' }}
      </span>
      <div class="small text-muted">{{ trendLevelLabel(sig.trend_level) }}</div>
    </td>
    <!-- RSI -->
    <td class="text-center">
      <span :class="rsiClass(sig.rsi)">{{ sig.rsi != null ? sig.rsi.toFixed(1) : '—' }}</span>
      <div class="small text-muted">{{ rsiLabel(sig.rsi_signal) }}</div>
    </td>
    <!-- ATR止损 -->
    <td class="text-end">
      <span v-if="sig.dynamic_stop_price != null" :class="sig.stop_loss_triggered ? 'text-danger fw-bold' : 'text-muted'">
        {{ sig.dynamic_stop_price.toFixed(3) }}
      </span>
      <span v-else class="text-muted">—</span>
      <div v-if="sig.atr_pct != null" class="small text-muted">ATR {{ sig.atr_pct.toFixed(1) }}%</div>
    </td>
    <!-- 市场过滤 -->
    <td class="text-center">
      <span class="badge" :class="marketClass(sig.market_filter)">{{ marketLabel(sig.market_filter) }}</span>
      <div v-if="sig.market_score != null" class="small text-muted">沪深300 {{ sig.market_score.toFixed(0) }}</div>
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
      <button class="btn btn-outline-primary btn-sm py-0 px-1 me-1" @click="$emit('ai-analyze', sig)" title="AI 智能分析" :disabled="refreshing">
        <i class="bi bi-robot"></i>
      </button>
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
defineProps({
  sig: { type: Object, required: true },
  refreshingRow: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
})

defineEmits(['edit', 'remove', 'rule', 'ai-analyze'])

function formatScore(score) {
  return score != null ? score.toFixed(0) : '—'
}

function reasonFactors(sig) {
  return Array.isArray(sig.decision_factors) ? sig.decision_factors.slice(0, 4) : []
}

function fullReason(sig) {
  const parts = []
  if (sig.reason) parts.push(sig.reason)
  parts.push(`评分：综合 ${formatScore(sig.signal_score)}，买 ${formatScore(sig.buy_score)}，卖 ${formatScore(sig.sell_score)}，风险 ${formatScore(sig.risk_score)}`)
  if (Array.isArray(sig.decision_factors) && sig.decision_factors.length) {
    parts.push(`关键因子：${sig.decision_factors.join('；')}`)
  }
  if (sig.market_reason) parts.push(`市场过滤：${sig.market_reason}`)
  if (sig.ai_summary) parts.push(`AI摘要：${sig.ai_summary}`)
  return parts.join('\n')
}

function scoreClass(score) {
  if (score == null) return 'bg-secondary'
  if (score >= 75) return 'bg-success'
  if (score >= 55) return 'bg-warning text-dark'
  return 'bg-secondary'
}

function trendStrengthClass(score) {
  if (score == null) return 'text-muted'
  if (score >= 70) return 'text-danger fw-bold'
  if (score >= 55) return 'text-danger'
  if (score < 40) return 'text-success fw-bold'
  return 'text-muted'
}

function trendLevelLabel(level) {
  const labels = {
    STRONG_UP: '强升',
    UP: '上升',
    NEUTRAL: '震荡',
    DOWN: '下降',
    STRONG_DOWN: '强降',
  }
  return labels[level] || '—'
}

function rsiClass(rsi) {
  if (rsi == null) return 'text-muted'
  if (rsi >= 70) return 'text-danger fw-bold'
  if (rsi <= 35) return 'text-success fw-bold'
  return 'text-muted'
}

function rsiLabel(signal) {
  const labels = {
    OVERBOUGHT: '过热',
    OVERSOLD: '超卖',
    NEUTRAL: '正常',
    UNKNOWN: '—',
  }
  return labels[signal] || '—'
}

function marketClass(filter) {
  if (filter === 'PASS') return 'bg-success'
  if (filter === 'CAUTION') return 'bg-warning text-dark'
  if (filter === 'BLOCK') return 'bg-danger'
  return 'bg-secondary'
}

function marketLabel(filter) {
  const labels = {
    PASS: '通过',
    CAUTION: '谨慎',
    BLOCK: '阻断',
  }
  return labels[filter] || '—'
}
</script>

<style scoped>
code { font-size: 0.8rem; color: #333; }
.reason-cell {
  min-width: 240px;
  max-width: 360px;
  white-space: normal;
}
.reason-scores { line-height: 1.2; }
.reason-list {
  line-height: 1.25;
  max-height: 4.8em;
  overflow: hidden;
}
</style>
