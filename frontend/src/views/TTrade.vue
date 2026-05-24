<template>
  <div class="container-fluid mt-4 px-3" style="max-width: 960px;">

    <!-- Symbol Selection -->
    <div class="card mb-3">
      <div class="card-body py-2">
        <div class="row g-2 align-items-end">
          <div class="col-md-4">
            <label class="form-label small mb-1">选择股票</label>
            <select v-model="selectedSymbol" class="form-select" @change="onSelectHolding">
              <option value="">-- 选择持仓股票 --</option>
              <option v-for="h in holdings" :key="h.symbol" :value="h.symbol">
                {{ h.symbol }} {{ h.name }} ({{ h.quantity }}股 / 成本{{ h.cost?.toFixed(3) || '-' }})
              </option>
              <option value="__manual__">手动输入...</option>
            </select>
          </div>
          <template v-if="selectedSymbol === '__manual__'">
            <div class="col-md-3">
              <label class="form-label small mb-1">股票代码</label>
              <input v-model="symbol" class="form-control" placeholder="如 588000" @keyup.enter="fetchAll">
            </div>
            <div class="col-md-2">
              <label class="form-label small mb-1">市场</label>
              <select v-model="market" class="form-select">
                <option value="CN">A股</option>
                <option value="HK">港股</option>
                <option value="US">美股</option>
              </select>
            </div>
          </template>
          <div class="col-auto">
            <button class="btn btn-primary" @click="fetchAll" :disabled="!currentSymbol || loading">
              <i class="bi bi-search me-1"></i>监测
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab Toggle -->
    <ul class="nav nav-tabs mb-3" v-if="data || intradayData">
      <li class="nav-item">
        <a class="nav-link" :class="{ active: activeTab === 'daily' }" href="#" @click.prevent="switchTab('daily')">
          <i class="bi bi-calendar3 me-1"></i>日线信号
        </a>
      </li>
      <li class="nav-item">
        <a class="nav-link" :class="{ active: activeTab === 'intraday' }" href="#" @click.prevent="switchTab('intraday')">
          <i class="bi bi-graph-up me-1"></i>日内分时
          <span v-if="intradayData?.intraday?.action !== 'HOLD'" class="badge ms-1" :class="intraBadgeClass">
            {{ intradayData?.intraday?.action === 'T_BUY' ? '买' : '卖' }}
          </span>
        </a>
      </li>
      <li class="nav-item ms-auto" v-if="activeTab === 'intraday'">
        <span class="nav-link text-muted small d-flex align-items-center gap-2">
          <input v-model="selectedDate" type="date" class="form-control form-control-sm" style="width:140px" @change="fetchIntradaySignal">
          <i class="bi bi-arrow-repeat me-1" :class="{ 'spin-anim': intraLoading }"></i>
          自动刷新 {{ refreshCountdown }}s
          <button class="btn btn-sm btn-outline-secondary ms-2" @click="fetchIntradaySignal">立即刷新</button>
        </span>
      </li>
    </ul>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-5">
      <div class="spinner-border text-primary mb-2"></div>
      <p class="text-muted">正在计算做T信号...</p>
    </div>

    <!-- Error -->
    <div v-if="error" class="alert alert-warning">
      <i class="bi bi-exclamation-triangle me-2"></i>{{ error }}
    </div>

    <!-- ==================== DAILY SIGNAL DASHBOARD ==================== -->
    <div v-if="data && !loading && activeTab === 'daily'">
      <!-- Top: Price + Recommendation -->
      <div class="row mb-3">
        <div class="col-md-8">
          <div class="card h-100">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start">
                <div>
                  <h5 class="mb-1">{{ data.symbol }} <small class="text-muted">{{ data.name }}</small></h5>
                  <div class="d-flex align-items-baseline gap-3">
                    <span class="display-5 fw-bold">{{ fmtPrice(data.current_price) }}</span>
                    <span v-if="data.daily_return != null" :class="data.daily_return >= 0 ? 'text-danger' : 'text-success'" style="font-size:1.2rem">
                      {{ data.daily_return >= 0 ? '+' : '' }}{{ fmtPct(data.daily_return) }}%
                    </span>
                  </div>
                  <small class="text-muted">实时价格</small>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card h-100" :class="recCardClass">
            <div class="card-body text-center d-flex flex-column justify-content-center">
              <i :class="'bi ' + recIcon + ' display-1 mb-2'"></i>
              <h3 class="mb-1 fw-bold">{{ data.recommendation_label }}</h3>
              <small>{{ data.action }}</small>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Reason -->
      <div v-if="data.action_detail" class="alert" :class="recAlertClass" role="alert">
        <i class="bi bi-info-circle me-2"></i>{{ data.action_detail }}
      </div>

      <!-- Key Indicators -->
      <div class="row mb-3">
        <!-- MA indicators -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header py-2"><i class="bi bi-graph-up me-2"></i>均线系统</div>
            <div class="card-body py-2">
              <table class="table table-sm mb-0">
                <tr>
                  <td>MA5</td>
                  <td><strong>{{ fmtPrice(data.ma5) }}</strong></td>
                  <td :class="maCompareClass(data.current_price, data.ma5)">{{ maCompareText(data.current_price, data.ma5) }}</td>
                </tr>
                <tr>
                  <td>MA10</td>
                  <td><strong>{{ fmtPrice(data.ma10) }}</strong></td>
                  <td :class="maCompareClass(data.current_price, data.ma10)">{{ maCompareText(data.current_price, data.ma10) }}</td>
                </tr>
                <tr>
                  <td>MA20</td>
                  <td><strong>{{ fmtPrice(data.ma20) }}</strong></td>
                  <td :class="maCompareClass(data.current_price, data.ma20)">{{ maCompareText(data.current_price, data.ma20) }}</td>
                </tr>
              </table>
              <small class="text-muted">
                趋势: {{ data.trend || '-' }} |
                强度: {{ fmtPct(data.trend_strength) }} |
                {{ data.trend_level || '' }}
              </small>
            </div>
          </div>
        </div>

        <!-- Oscillators -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header py-2"><i class="bi bi-activity me-2"></i>摆动指标</div>
            <div class="card-body py-2">
              <div class="row">
                <div class="col-6">
                  <div class="mb-2">
                    <small class="text-muted">RSI(14)</small>
                    <h4 :class="rsiClass" class="mb-0">{{ fmtNum(data.rsi) }}</h4>
                    <small>{{ data.rsi_signal || '-' }}</small>
                  </div>
                  <div>
                    <small class="text-muted">成交量比</small>
                    <h5 class="mb-0">{{ fmtNum(data.volume_ratio) }}</h5>
                    <small>{{ data.volume_signal || '-' }}</small>
                  </div>
                </div>
                <div class="col-6">
                  <div class="mb-2">
                    <small class="text-muted">MACD</small>
                    <h5 class="mb-0">{{ fmtNum(data.macd) }}</h5>
                    <small>信号线 {{ fmtNum(data.macd_signal) }} | 柱 {{ fmtNum(data.macd_histogram) }}</small>
                  </div>
                  <div>
                    <small class="text-muted">波动率 ATR</small>
                    <h5 class="mb-0">{{ fmtPrice(data.atr) }} <small>({{ fmtPct(data.atr_pct) }}%)</small></h5>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- T+0 Reference Levels -->
      <div class="row mb-3">
        <div class="col-md-4">
          <div class="card text-white bg-success">
            <div class="card-body py-2 text-center">
              <small>做T支撑位 (布林下轨)</small>
              <h4 class="mb-0">{{ fmtPrice(data.support_level) }}</h4>
              <small v-if="data.current_price && data.support_level">
                距当前 {{ fmtPct((data.current_price - data.support_level) / data.support_level * 100) }}%
              </small>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white bg-secondary">
            <div class="card-body py-2 text-center">
              <small>布林中轨 (MA20)</small>
              <h4 class="mb-0">{{ fmtPrice(data.bollinger_mid) }}</h4>
              <small>布林位 {{ fmtPct(data.bollinger_position) }}%</small>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white bg-danger">
            <div class="card-body py-2 text-center">
              <small>做T压力位 (布林上轨)</small>
              <h4 class="mb-0">{{ fmtPrice(data.resistance_level) }}</h4>
              <small v-if="data.current_price && data.resistance_level">
                距当前 {{ fmtPct((data.resistance_level - data.current_price) / data.current_price * 100) }}%
              </small>
            </div>
          </div>
        </div>
      </div>

      <!-- Signal Quality & Scores -->
      <div class="row">
        <div class="col-md-6">
          <div class="card">
            <div class="card-header py-2"><i class="bi bi-shield-check me-2"></i>信号评分</div>
            <div class="card-body py-2">
              <div class="d-flex justify-content-between mb-1">
                <span>综合评分</span>
                <strong :class="data.signal_score >= 0 ? 'text-danger' : (data.signal_score <= -0.3 ? 'text-success' : '')">{{ fmtPct(data.signal_score) }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>买入评分</span>
                <span class="text-danger">{{ fmtPct(data.buy_score) }}</span>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>卖出评分</span>
                <span class="text-success">{{ fmtPct(data.sell_score) }}</span>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>风险评分</span>
                <span>{{ fmtPct(data.risk_score) }}</span>
              </div>
              <div class="d-flex justify-content-between">
                <span>信号质量</span>
                <strong>{{ data.signal_quality || '-' }}</strong>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="card">
            <div class="card-header py-2"><i class="bi bi-info-circle me-2"></i>其它参考</div>
            <div class="card-body py-2">
              <div class="d-flex justify-content-between mb-1">
                <span>周线趋势</span>
                <strong>{{ data.weekly_trend || '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>突破信号</span>
                <span>{{ data.breakout ? '有突破' : '无' }} {{ data.breakout_quality ? '('+data.breakout_quality+')' : '' }}</span>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>回调位置</span>
                <span>{{ data.pullback ? '回调中' : '否' }}</span>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>市场情绪</span>
                <span>{{ data.sentiment || '-' }}</span>
              </div>
              <div class="d-flex justify-content-between">
                <span>建议仓位比例</span>
                <strong>{{ fmtPct(data.suggested_position_size) }}%</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== INTRADAY SIGNAL PANEL ==================== -->
    <div v-if="intradayData && !loading && activeTab === 'intraday'">
      <!-- Intraday Error -->
      <div v-if="intraError" class="alert alert-warning">
        <i class="bi bi-exclamation-triangle me-2"></i>{{ intraError }}
      </div>

      <!-- Market Status Bar -->
      <div class="alert mb-3" :class="intradayData.is_market_open ? 'alert-success' : 'alert-secondary'" role="alert">
        <i class="bi me-2" :class="intradayData.is_market_open ? 'bi-play-circle' : 'bi-pause-circle'"></i>
        {{ intradayData.is_market_open ? '交易中' : '已收盘/非交易时段' }}
        <span class="ms-2">{{ intradayData.timestamp }}</span>
        <span class="ms-3" v-if="intradayData.daily_trend">
          日线趋势: <strong :class="trendBadgeClass">{{ intradayData.daily_trend }}</strong>
          ({{ fmtPct(intradayData.daily_trend_strength) }})
        </span>
      </div>

      <!-- Top: Price + Intraday Signal -->
      <div class="row mb-3">
        <div class="col-md-8">
          <div class="card h-100">
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start">
                <div>
                  <h5 class="mb-1">{{ intradayData.symbol }} <small class="text-muted">{{ intradayData.name }}</small></h5>
                  <div class="d-flex align-items-baseline gap-3">
                    <span class="display-5 fw-bold">{{ fmtPrice(intradayData.current_price) }}</span>
                    <span v-if="intradayData.prev_close" :class="intradayData.current_price >= intradayData.prev_close ? 'text-danger' : 'text-success'" style="font-size:1.1rem">
                      {{ intradayData.current_price >= intradayData.prev_close ? '+' : '' }}{{ fmtPct((intradayData.current_price - intradayData.prev_close) / intradayData.prev_close * 100) }}%
                    </span>
                  </div>
                  <small class="text-muted">
                    昨收 {{ fmtPrice(intradayData.prev_close) }}
                    <span v-if="intradayData.bar_count"> | 已交易 {{ intradayData.bar_count * 5 }} 分钟</span>
                  </small>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card h-100" :class="intraRecCardClass">
            <div class="card-body text-center d-flex flex-column justify-content-center">
              <i :class="'bi ' + intraRecIcon + ' display-1 mb-2'"></i>
              <h3 class="mb-1 fw-bold">{{ intraActionLabel }}</h3>
              <small>{{ intradayData.intraday?.signal_type }} | {{ intradayData.intraday?.quality }}</small>
            </div>
          </div>
        </div>
      </div>

      <!-- Intraday Reason -->
      <div v-if="intradayData.intraday?.reason" class="alert" :class="intraAlertClass" role="alert">
        <i class="bi bi-info-circle me-2"></i>{{ intradayData.intraday.reason }}
        <small class="ms-2 text-muted">置信度: {{ (intradayData.intraday.confidence * 100).toFixed(0) }}%</small>
      </div>

      <!-- K-line Chart (ECharts) -->
      <div class="card mb-3" v-if="intradayData">
        <div class="card-header py-2 d-flex justify-content-between align-items-center">
          <span><i class="bi bi-candlestick-chart me-2"></i>K线图 (5分钟)
            <small class="text-muted ms-2">{{ intradayData.bar_count || 0 }} 根</small>
          </span>
          <small class="text-muted">
            <span class="text-danger me-2">■ 阴线</span><span class="text-success me-2">■ 阳线</span>
            <span class="text-info me-2">-- VWAP</span><span>▊ 成交量</span>
          </small>
        </div>
        <div class="card-body p-2" v-if="intradayData.bars?.length > 0">
          <v-chart :option="chartOption" autoresize style="height: 400px;" />
        </div>
        <div class="card-body text-center py-5 text-muted" v-else>
          <i class="bi bi-bar-chart d-block mb-2" style="font-size:2rem"></i>
          <span v-if="!intradayData.is_market_open">非交易时段，暂无分时数据</span>
          <span v-else>暂无K线数据</span>
        </div>
      </div>

      <!-- Intraday Indicators Row -->
      <div class="row mb-3">
        <!-- Intraday MAs -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header py-2"><i class="bi bi-bar-chart me-2"></i>分钟内均线</div>
            <div class="card-body py-2">
              <table class="table table-sm mb-0">
                <tr>
                  <td>VWAP</td>
                  <td><strong>{{ fmtPrice(intradayData.indicators?.vwap) }}</strong></td>
                  <td :class="intraCompareClass(intradayData.indicators?.price_vs_vwap_pct)">
                    {{ intradayData.indicators?.price_vs_vwap_pct != null ? (intradayData.indicators.price_vs_vwap_pct >= 0 ? '+' : '') + fmtPct(intradayData.indicators.price_vs_vwap_pct) + '%' : '-' }}
                  </td>
                </tr>
                <tr>
                  <td>MA5</td>
                  <td><strong>{{ fmtPrice(intradayData.indicators?.intra_ma5) }}</strong></td>
                  <td :class="maCompareClass(intradayData.current_price, intradayData.indicators?.intra_ma5)">{{ maCompareText(intradayData.current_price, intradayData.indicators?.intra_ma5) }}</td>
                </tr>
                <tr>
                  <td>MA20</td>
                  <td><strong>{{ fmtPrice(intradayData.indicators?.intra_ma20) }}</strong></td>
                  <td :class="maCompareClass(intradayData.current_price, intradayData.indicators?.intra_ma20)">{{ maCompareText(intradayData.current_price, intradayData.indicators?.intra_ma20) }}</td>
                </tr>
                <tr>
                  <td>MA60</td>
                  <td><strong>{{ fmtPrice(intradayData.indicators?.intra_ma60) }}</strong></td>
                  <td :class="maCompareClass(intradayData.current_price, intradayData.indicators?.intra_ma60)">{{ maCompareText(intradayData.current_price, intradayData.indicators?.intra_ma60) }}</td>
                </tr>
              </table>
            </div>
          </div>
        </div>

        <!-- Intraday Oscillators + Opening Range -->
        <div class="col-md-6">
          <div class="card h-100">
            <div class="card-header py-2"><i class="bi bi-activity me-2"></i>摆动指标 &amp; 区间</div>
            <div class="card-body py-2">
              <div class="row">
                <div class="col-6">
                  <div class="mb-2">
                    <small class="text-muted">RSI(14)</small>
                    <h4 :class="intraRsiClass(14)" class="mb-0">{{ fmtNum(intradayData.indicators?.intra_rsi_14) }}</h4>
                    <small>{{ intradayData.factors?.rsi_signal || '-' }}</small>
                  </div>
                  <div>
                    <small class="text-muted">量比</small>
                    <h5 class="mb-0">{{ fmtNum(intradayData.indicators?.volume_ratio) }}</h5>
                    <small>{{ intradayData.factors?.volume_signal || '-' }}</small>
                  </div>
                </div>
                <div class="col-6">
                  <div class="mb-2">
                    <small class="text-muted">开盘区间高</small>
                    <h6 class="mb-0 text-danger">{{ fmtPrice(intradayData.indicators?.opening_range_high) }}</h6>
                  </div>
                  <div class="mb-2">
                    <small class="text-muted">开盘区间低</small>
                    <h6 class="mb-0 text-success">{{ fmtPrice(intradayData.indicators?.opening_range_low) }}</h6>
                  </div>
                  <div>
                    <small class="text-muted">区间突破</small>
                    <h6 class="mb-0">{{ intradayData.factors?.range_signal || '-' }}</h6>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- T-Trade Reference Levels -->
      <div class="row mb-3">
        <div class="col-md-4">
          <div class="card text-white bg-success">
            <div class="card-body py-2 text-center">
              <small>做T支撑位</small>
              <h4 class="mb-0">{{ fmtPrice(intradayData.intraday?.support_level) }}</h4>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white" :class="intradayData.indicators?.price_vs_vwap_pct >= 0 ? 'bg-secondary' : 'bg-warning text-dark'">
            <div class="card-body py-2 text-center">
              <small>VWAP 均价</small>
              <h4 class="mb-0">{{ fmtPrice(intradayData.intraday?.vwap) }}</h4>
              <small v-if="intradayData.indicators?.price_vs_vwap_pct != null">
                偏离 {{ intradayData.indicators.price_vs_vwap_pct >= 0 ? '+' : '' }}{{ fmtPct(intradayData.indicators.price_vs_vwap_pct) }}%
              </small>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="card text-white bg-danger">
            <div class="card-body py-2 text-center">
              <small>做T压力位</small>
              <h4 class="mb-0">{{ fmtPrice(intradayData.intraday?.resistance_level) }}</h4>
            </div>
          </div>
        </div>
      </div>

      <!-- Intraday Factors & Context -->
      <div class="row">
        <div class="col-md-6">
          <div class="card">
            <div class="card-header py-2"><i class="bi bi-lightning-charge me-2"></i>日内因子</div>
            <div class="card-body py-2">
              <div class="d-flex justify-content-between mb-1">
                <span>VWAP信号</span>
                <strong>{{ intradayData.factors?.vwap_signal || '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>开盘区间</span>
                <strong>{{ intradayData.factors?.range_signal || '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>微观趋势</span>
                <strong :class="intraMicroTrendClass">{{ intradayData.factors?.micro_trend || '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>动量</span>
                <strong>{{ intradayData.factors?.momentum_signal || '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between">
                <span>连涨/连跌</span>
                <strong>
                  <span class="text-danger">{{ intradayData.indicators?.consecutive_up_bars }}↑</span> /
                  <span class="text-success">{{ intradayData.indicators?.consecutive_down_bars }}↓</span>
                </strong>
              </div>
            </div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="card">
            <div class="card-header py-2"><i class="bi bi-info-circle me-2"></i>其它参考</div>
            <div class="card-body py-2">
              <div class="d-flex justify-content-between mb-1">
                <span>日内涨幅</span>
                <strong :class="intradayData.indicators?.session_return_pct >= 0 ? 'text-danger' : 'text-success'">
                  {{ intradayData.indicators?.session_return_pct != null ? (intradayData.indicators.session_return_pct >= 0 ? '+' : '') + fmtPct(intradayData.indicators.session_return_pct) + '%' : '-' }}
                </strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>日内振幅</span>
                <strong>{{ intradayData.indicators?.range_pct != null ? fmtPct(intradayData.indicators.range_pct) + '%' : '-' }}</strong>
              </div>
              <div class="d-flex justify-content-between mb-1">
                <span>累计成交</span>
                <strong>{{ formatVolume(intradayData.indicators?.cumulative_volume) }}</strong>
              </div>
              <div class="d-flex justify-content-between">
                <span>RSI(7) 快线</span>
                <strong :class="intraRsiClass(7)">{{ fmtNum(intradayData.indicators?.intra_rsi_7) }}</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!data && !intradayData && !loading && !error" class="text-center py-5 text-muted">
      <i class="bi bi-search display-3 d-block mb-3"></i>
      <p>输入股票代码，查看实时买卖点信号</p>
      <small>基于多因子信号引擎：趋势 + 动量 + 成交量 + 波动率 + 布林带</small>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, MarkPointComponent,
  MarkLineComponent, DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, CandlestickChart, BarChart, LineChart,
  GridComponent, TooltipComponent, MarkPointComponent, MarkLineComponent, DataZoomComponent])

const holdings = ref([])
const selectedSymbol = ref('')
const symbol = ref('')
const market = ref('CN')
const data = ref(null)
const loading = ref(false)
const error = ref('')
const activeTab = ref('intraday')
const selectedDate = ref(new Date().toISOString().split('T')[0])

const intradayData = ref(null)
const intraLoading = ref(false)
const intraError = ref('')
const refreshCountdown = ref(5)
let refreshTimer = null
let countdownTimer = null

const currentSymbol = computed(() => {
  if (selectedSymbol.value && selectedSymbol.value !== '__manual__') return selectedSymbol.value
  return symbol.value.trim().toUpperCase()
})

function onSelectHolding() {
  data.value = null
  intradayData.value = null
  error.value = ''
  intraError.value = ''
  selectedDate.value = new Date().toISOString().split('T')[0]
  if (selectedSymbol.value && selectedSymbol.value !== '__manual__') {
    symbol.value = ''
    const h = holdings.value.find(x => x.symbol === selectedSymbol.value)
    if (h) market.value = h.market || 'CN'
    fetchAll()
  }
}

function fmtPrice(v) { return v != null ? Number(v).toFixed(v >= 1 ? 2 : 4) : '-' }
function fmtPct(v) { return v != null ? Number(v).toFixed(2) : '-' }
function fmtNum(v) { return v != null ? Number(v).toFixed(2) : '-' }

function formatVolume(v) {
  if (v == null) return '-'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

function maCompareClass(price, ma) {
  if (price == null || ma == null) return ''
  return price > ma ? 'text-danger' : 'text-success'
}
function maCompareText(price, ma) {
  if (price == null || ma == null) return '-'
  const pct = ((price - ma) / ma * 100)
  return (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%'
}

function intraCompareClass(pct) {
  if (pct == null) return ''
  return pct >= 0 ? 'text-danger' : 'text-success'
}

const rsiClass = computed(() => {
  if (data.value?.rsi == null) return ''
  if (data.value.rsi > 70) return 'text-danger'
  if (data.value.rsi < 30) return 'text-success'
  return ''
})

function intraRsiClass(period) {
  const val = period === 7 ? intradayData.value?.indicators?.intra_rsi_7 : intradayData.value?.indicators?.intra_rsi_14
  if (val == null) return ''
  if (val > 75) return 'text-danger'
  if (val < 30) return 'text-success'
  return ''
}

const recCardClass = computed(() => {
  if (!data.value) return ''
  return {
    buy: 'bg-danger text-white',
    sell: 'bg-success text-white',
    hold: 'bg-warning text-dark',
  }[data.value.recommendation] || 'bg-secondary text-white'
})
const recAlertClass = computed(() => {
  if (!data.value) return 'alert-info'
  return {
    buy: 'alert-danger',
    sell: 'alert-success',
    hold: 'alert-warning',
  }[data.value.recommendation] || 'alert-info'
})
const recIcon = computed(() => {
  if (!data.value) return 'bi-question-circle'
  return {
    buy: 'bi-caret-up-fill',
    sell: 'bi-caret-down-fill',
    hold: 'bi-dash-circle-fill',
  }[data.value.recommendation] || 'bi-question-circle'
})

// Intraday computed
const intraRecCardClass = computed(() => {
  const a = intradayData.value?.intraday?.action
  if (a === 'T_BUY') return 'bg-danger text-white'
  if (a === 'T_SELL') return 'bg-success text-white'
  return 'bg-secondary text-white'
})
const intraRecIcon = computed(() => {
  const a = intradayData.value?.intraday?.action
  if (a === 'T_BUY') return 'bi-caret-up-fill'
  if (a === 'T_SELL') return 'bi-caret-down-fill'
  return 'bi-dash-circle-fill'
})
const intraActionLabel = computed(() => {
  const a = intradayData.value?.intraday?.action
  if (a === 'T_BUY') return 'T买入'
  if (a === 'T_SELL') return 'T卖出'
  return '观望'
})
const intraAlertClass = computed(() => {
  const a = intradayData.value?.intraday?.action
  if (a === 'T_BUY') return 'alert-danger'
  if (a === 'T_SELL') return 'alert-success'
  return 'alert-secondary'
})
const intraBadgeClass = computed(() => {
  const a = intradayData.value?.intraday?.action
  if (a === 'T_BUY') return 'bg-danger'
  if (a === 'T_SELL') return 'bg-success'
  return 'bg-secondary'
})
const trendBadgeClass = computed(() => {
  const t = intradayData.value?.daily_trend
  if (t === 'UP') return 'text-danger'
  if (t === 'DOWN') return 'text-success'
  return ''
})
const intraMicroTrendClass = computed(() => {
  const t = intradayData.value?.factors?.micro_trend
  if (t === 'UP') return 'text-danger'
  if (t === 'DOWN') return 'text-success'
  return ''
})

// ECharts option
const chartOption = computed(() => {
  const bars = intradayData.value?.bars || []
  if (bars.length === 0) return {}

  const times = bars.map(b => b.time)
  const ohlc = bars.map(b => [b.open, b.close, b.low, b.high])
  const volumes = bars.map((b, i) => {
    const isUp = b.close >= b.open
    return { value: b.volume, itemStyle: { color: isUp ? '#ef5350' : '#26a69a' } }
  })
  const vwap = intradayData.value?.intraday?.vwap

  // VWAP line data (same value across all bars)
  const vwapData = vwap != null ? times.map(() => vwap) : []

  // Signal markers for markPoint
  const buyMarkers = []
  const sellMarkers = []
  const markers = intradayData.value?.signal_markers || []
  for (const m of markers) {
    const label = m.action === 'T_BUY' ? '买入' : '卖出'
    const data = {
      name: label + ' ' + m.signal_type,
      coord: [m.bar_index, m.price],
      value: label,
      symbol: 'pin',
      symbolSize: 40,
      label: { show: true, fontSize: 11, fontWeight: 'bold', formatter: label + '\n' + m.signal_type },
    }
    if (m.action === 'T_BUY') {
      data.itemStyle = { color: '#26a69a' }
      data.symbol = 'arrow'
      data.symbolRotate = 0
      buyMarkers.push(data)
    } else {
      data.itemStyle = { color: '#ef5350' }
      data.symbol = 'arrow'
      data.symbolRotate = 180
      sellMarkers.push(data)
    }
  }
  const allMarkers = [...buyMarkers, ...sellMarkers]

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const k = params.find(p => p.seriesName === 'K线')
        const v = params.find(p => p.seriesName === '成交量')
        const vw = params.find(p => p.seriesName === 'VWAP')
        if (!k) return ''
        const data = k.data
        let html = `<b>${k.axisValue}</b><br/>`
        html += `开 ${data[1].toFixed(3)} 高 ${data[3].toFixed(3)}<br/>`
        html += `收 ${data[2].toFixed(3)} 低 ${data[2].toFixed(3)}<br/>`
        if (vw && vw.value != null) html += `VWAP ${vw.value.toFixed(3)}<br/>`
        if (v) html += `量 ${(v.value/10000).toFixed(1)}万`
        return html
      },
    },
    grid: [
      { top: 10, left: 60, right: 20, height: '60%' },
      { top: '75%', left: 60, right: 20, height: '15%' },
    ],
    xAxis: [
      { type: 'category', data: times, gridIndex: 0, axisLabel: { fontSize: 10 }, axisLine: { lineStyle: { color: '#ccc' } } },
      { type: 'category', data: times, gridIndex: 1, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#ccc' } } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitNumber: 5, axisLabel: { fontSize: 10, formatter: v => v.toFixed(v >= 10 ? 1 : 3) } },
      { type: 'value', gridIndex: 1, scale: true, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0, yAxisIndex: 0,
        data: ohlc,
        itemStyle: { color: '#ef5350', color0: '#26a69a', borderColor: '#ef5350', borderColor0: '#26a69a' },
        markPoint: allMarkers.length > 0 ? {
          data: allMarkers,
          label: { show: true, fontSize: 10, fontWeight: 'bold' },
        } : undefined,
      },
      ...(vwap != null ? [{
        name: 'VWAP',
        type: 'line',
        xAxisIndex: 0, yAxisIndex: 0,
        data: vwapData,
        lineStyle: { color: '#0dcaf0', width: 1, type: 'dashed' },
        symbol: 'none',
      }] : []),
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1, yAxisIndex: 1,
        data: volumes,
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], zoomOnMouseWheel: true, moveOnMouseMove: true },
    ],
  }
})

// Data fetching
async function loadHoldings() {
  try {
    const r = await fetch('/api/ttrade/holdings')
    if (r.ok) {
      holdings.value = await r.json()
      // 默认选择第一只持仓股票
      if (holdings.value.length > 0 && !selectedSymbol.value) {
        selectedSymbol.value = holdings.value[0].symbol
        const h = holdings.value[0]
        if (h) market.value = h.market || 'CN'
        await fetchAll()
      }
    }
  } catch (e) { /* ignore */ }
}

async function fetchSignal() {
  const s = currentSymbol.value
  if (!s) return
  loading.value = true
  error.value = ''
  data.value = null
  try {
    const r = await fetch(`/api/ttrade/signal/${encodeURIComponent(s)}?market=${market.value}`)
    if (!r.ok) {
      const msg = await r.json().catch(() => ({}))
      error.value = msg.detail || `请求失败 (${r.status})`
      return
    }
    data.value = await r.json()
  } catch (e) {
    error.value = '网络错误: ' + e.message
  } finally {
    loading.value = false
  }
}

async function fetchIntradaySignal() {
  const s = currentSymbol.value
  if (!s) return
  intraLoading.value = true
  intraError.value = ''
  try {
    const dateParam = selectedDate.value ? `&req_date=${selectedDate.value}` : ''
    const r = await fetch(`/api/ttrade/intraday/${encodeURIComponent(s)}?market=${market.value}${dateParam}`)
    if (!r.ok) {
      const msg = await r.json().catch(() => ({}))
      intraError.value = msg.detail || `请求失败 (${r.status})`
      return
    }
    intradayData.value = await r.json()
    // Restart countdown
    refreshCountdown.value = 5
  } catch (e) {
    intraError.value = '网络错误: ' + e.message
  } finally {
    intraLoading.value = false
  }
}

async function fetchAll() {
  await Promise.all([fetchSignal(), fetchIntradaySignal()])
  startIntradayRefresh()
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'intraday') {
    if (!intradayData.value) fetchIntradaySignal()
    startIntradayRefresh()
  } else {
    stopIntradayRefresh()
  }
}

function startIntradayRefresh() {
  stopIntradayRefresh()
  // Only auto-refresh when viewing today's data
  const today = new Date().toISOString().split('T')[0]
  if (selectedDate.value !== today) return
  refreshCountdown.value = 5

  countdownTimer = setInterval(() => {
    refreshCountdown.value--
    if (refreshCountdown.value <= 0) {
      refreshCountdown.value = 5
      fetchIntradaySignal()
    }
  }, 1000)
}

function stopIntradayRefresh() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

onMounted(() => {
  loadHoldings()
})

onUnmounted(() => {
  stopIntradayRefresh()
})
</script>

<style scoped>
.spin-anim {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.nav-tabs .nav-link {
  cursor: pointer;
}
</style>
