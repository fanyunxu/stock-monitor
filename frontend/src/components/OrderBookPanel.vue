<template>
  <div class="card mb-3">
    <div class="card-header py-2 d-flex justify-content-between align-items-center">
      <span>
        <i class="bi bi-list-ol me-2"></i>十档盘口
        <span v-if="orderbook?.source" class="badge ms-2" :class="sourceBadgeClass">
          {{ sourceLabel }}
        </span>
      </span>
      <small v-if="orderbook?.timestamp" class="text-muted">
        {{ formatTime(orderbook.timestamp) }}
      </small>
    </div>

    <div v-if="!orderbook" class="card-body text-center py-4 text-muted">
      <i class="bi bi-hourglass-split d-block mb-2" style="font-size:1.5rem"></i>
      <small>暂无盘口数据</small>
    </div>

    <div v-else class="card-body p-2">
      <!-- Center summary stats -->
      <div class="row g-1 mb-2 text-center small">
        <div class="col">
          <div class="text-muted">委比</div>
          <div :class="orderbook.committee_ratio >= 0 ? 'text-danger fw-bold' : 'text-success fw-bold'">
            {{ orderbook.committee_ratio != null ? (orderbook.committee_ratio >= 0 ? '+' : '') + orderbook.committee_ratio.toFixed(2) + '%' : '-' }}
          </div>
        </div>
        <div class="col">
          <div class="text-muted">委差</div>
          <div :class="orderbook.committee_diff >= 0 ? 'text-danger fw-bold' : 'text-success fw-bold'">
            {{ orderbook.committee_diff != null ? (orderbook.committee_diff >= 0 ? '+' : '') + orderbook.committee_diff.toLocaleString() : '-' }}
          </div>
        </div>
        <div class="col">
          <div class="text-muted">量比</div>
          <div class="fw-bold">{{ orderbook.volume_ratio != null ? orderbook.volume_ratio.toFixed(2) : '-' }}</div>
        </div>
        <div class="col">
          <div class="text-muted">换手率</div>
          <div class="fw-bold">{{ orderbook.turnover_rate != null ? orderbook.turnover_rate.toFixed(2) + '%' : '-' }}</div>
        </div>
        <div class="col">
          <div class="text-muted">成交额</div>
          <div class="fw-bold">{{ formatAmount(orderbook.amount) }}</div>
        </div>
      </div>

      <div class="row g-1 mb-2 text-center small">
        <div class="col">
          <div class="text-muted">内盘</div>
          <div class="text-success fw-bold">{{ formatVolume(orderbook.inner_volume) }}</div>
        </div>
        <div class="col">
          <div class="text-muted">外盘</div>
          <div class="text-danger fw-bold">{{ formatVolume(orderbook.outer_volume) }}</div>
        </div>
        <div class="col">
          <div class="text-muted">委买总量</div>
          <div class="text-danger fw-bold">{{ formatVolume(orderbook.bid_total) }}</div>
        </div>
        <div class="col">
          <div class="text-muted">委卖总量</div>
          <div class="text-success fw-bold">{{ formatVolume(orderbook.ask_total) }}</div>
        </div>
        <div class="col">
          <div class="text-muted">当前价</div>
          <div class="fw-bold">{{ formatPrice(orderbook.current_price) }}</div>
        </div>
      </div>

      <!-- 10-level order book: asks on left (top→down: 卖十→卖一), bids on right (top→down: 买一→买十) -->
      <div class="row g-1 font-mono">
        <!-- Asks (sell side) -->
        <div class="col-6">
          <div class="d-flex small text-muted border-bottom pb-1">
            <div class="flex-grow-1">卖价</div>
            <div style="width:80px;text-align:right">卖量</div>
            <div style="width:60px;text-align:right" class="ms-1">档</div>
          </div>
          <div v-for="(ask, idx) in asksDesc" :key="'ask-' + idx"
               class="d-flex py-0 small ask-row"
               :class="{ 'ask-row-best': idx === asksDesc.length - 1 }">
            <div class="flex-grow-1 text-success">{{ formatPrice(ask?.price) }}</div>
            <div style="width:80px;text-align:right">{{ formatVolume(ask?.volume) }}</div>
            <div style="width:60px;text-align:right" class="ms-1 text-muted">卖{{ asksDesc.length - idx }}</div>
          </div>
        </div>
        <!-- Bids (buy side) -->
        <div class="col-6">
          <div class="d-flex small text-muted border-bottom pb-1">
            <div style="width:60px" class="me-1">档</div>
            <div class="flex-grow-1">买价</div>
            <div style="width:80px;text-align:right">买量</div>
          </div>
          <div v-for="(bid, idx) in bidsAsc" :key="'bid-' + idx"
               class="d-flex py-0 small bid-row"
               :class="{ 'bid-row-best': idx === 0 }">
            <div style="width:60px" class="me-1 text-muted">买{{ idx + 1 }}</div>
            <div class="flex-grow-1 text-danger">{{ formatPrice(bid?.price) }}</div>
            <div style="width:80px;text-align:right">{{ formatVolume(bid?.volume) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  orderbook: { type: Object, default: null },
})

// Asks displayed top→down: 卖十 → 卖一 (reverse so best ask is at bottom, adjacent to best bid)
const asksDesc = computed(() => {
  const asks = props.orderbook?.asks || []
  return [...asks].reverse()  // 卖一 at end, 卖十 at start
})

// Bids displayed top→down: 买一 → 买十
const bidsAsc = computed(() => {
  return props.orderbook?.bids || []
})

const sourceLabel = computed(() => {
  const s = props.orderbook?.source
  if (s === 'eastmoney_level2') return 'Level-2'
  if (s === 'tencent_5level') return '5档'
  if (s === 'yahoo_basic') return 'Yahoo'
  if (s === 'empty') return '无数据'
  return s || '-'
})

const sourceBadgeClass = computed(() => {
  const s = props.orderbook?.source
  if (s === 'eastmoney_level2') return 'bg-danger'
  if (s === 'tencent_5level') return 'bg-warning text-dark'
  return 'bg-secondary'
})

function formatPrice(v) {
  if (v == null) return '-'
  const n = Number(v)
  return n.toFixed(n >= 1 ? 2 : 4)
}

function formatVolume(v) {
  if (v == null) return '-'
  const n = Number(v)
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function formatAmount(v) {
  if (v == null) return '-'
  const n = Number(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万'
  return n.toFixed(0)
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour12: false })
  } catch (e) {
    return ts
  }
}
</script>

<style scoped>
.font-mono {
  font-family: 'SF Mono', 'Monaco', 'Cascadia Mono', 'Roboto Mono', Consolas, 'Courier New', monospace;
  font-size: 0.85rem;
}
.ask-row, .bid-row {
  border-bottom: 1px solid rgba(128, 128, 128, 0.1);
  line-height: 1.5;
}
.ask-row-best {
  background: rgba(25, 135, 84, 0.08);
  font-weight: 600;
}
.bid-row-best {
  background: rgba(220, 53, 69, 0.08);
  font-weight: 600;
}
</style>
