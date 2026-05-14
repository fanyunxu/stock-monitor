<template>
  <div class="modal fade" :id="modalId" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-scrollable">
      <div class="modal-content">
        <div class="modal-header bg-primary text-white">
          <h5 class="modal-title">
            🤖 AI 智能分析 — {{ symbol }}
          </h5>
          <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
        </div>
        <div class="modal-body">
          <!-- Loading -->
          <div v-if="loading" class="text-center py-5">
            <div class="spinner-border text-primary mb-3" role="status"></div>
            <p class="text-muted">正在调用 AI 分析...</p>
            <small class="text-muted">综合分析技术面、消息面、板块热点</small>
          </div>

          <!-- Error -->
          <div v-else-if="error" class="alert alert-warning">
            <i class="bi bi-exclamation-triangle me-2"></i>
            {{ error }}
            <div class="mt-2">
              <small class="text-muted">请确认 config.yaml 中已配置 ai.api_key</small>
            </div>
          </div>

          <!-- Analysis Result -->
          <div v-else-if="analysis" class="ai-analysis-content">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <span class="badge" :class="cached ? 'bg-info' : 'bg-success'">
                {{ cached ? '📦 缓存命中' : '✨ 实时生成' }}
              </span>
              <small class="text-muted">{{ generatedAt }}</small>
            </div>
            <div class="analysis-text" v-html="renderedAnalysis"></div>
          </div>
        </div>
        <div class="modal-footer">
          <div class="d-flex w-100 justify-content-between align-items-center">
            <div>
              <span v-for="tag in conceptTags.slice(0,4)" :key="tag.name"
                    class="badge bg-secondary me-1" style="font-size:0.7rem;">
                {{ tag.name }}
              </span>
            </div>
            <div>
              <button class="btn btn-outline-primary btn-sm me-2" @click="refresh" :disabled="loading">
                <i class="bi bi-arrow-repeat me-1"></i>刷新分析
              </button>
              <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,
  gfm: true,
})

const props = defineProps({
  symbol: String,
  name: String,
  instrumentType: { type: String, default: 'ETF' },
  signalData: { type: Object, default: () => ({}) },
})

const modalId = `aiModal-${props.symbol}`

const loading = ref(false)
const analysis = ref('')
const error = ref('')
const generatedAt = ref('')
const cached = ref(false)
const conceptTags = ref([])
const newsTitles = ref([])

let bsModal = null

const API = '/api'

async function loadAnalysis(force = false) {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`${API}/ai/analyze/${encodeURIComponent(props.symbol)}?name=${encodeURIComponent(props.name || '')}&instrument_type=${props.instrumentType}&force=${force}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: props.name,
        instrument_type: props.instrumentType,
        signal_data: props.signalData,
      }),
    })
    if (!r.ok) {
      const err = await r.json()
      throw new Error(err.detail || 'AI 分析请求失败')
    }
    const data = await r.json()
    analysis.value = data.analysis || '(AI 未返回分析内容)'
    generatedAt.value = data.generated_at || ''
    cached.value = data.cached
    conceptTags.value = data.concept_tags || []
    newsTitles.value = data.news_titles || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function refresh() {
  loadAnalysis(true)
}

const renderedAnalysis = computed(() => {
  if (!analysis.value) return ''
  let text = analysis.value

  // Strip MiniMax thinking tags
  text = text.replace(/<response>[\s\S]*?<\/response>/gi, '')
  text = text.replace(/<think>[\s\S]*?<\/think>/gi, '')
  text = text.replace(/^[\s\S]*?<response>/i, '')
  text = text.replace(/^[\s\S]*?<think>/i, '')

  // Use marked for proper GFM rendering (tables, code, lists, etc.)
  return marked.parse(text)
})

function show() {
  loadAnalysis()
  if (!bsModal) {
    const el = document.getElementById(modalId)
    if (el) bsModal = new bootstrap.Modal(el)
  }
  if (bsModal) bsModal.show()
}

function hide() {
  if (bsModal) bsModal.hide()
}

onMounted(() => {
  const el = document.getElementById(modalId)
  if (el) {
    bsModal = new bootstrap.Modal(el)
    el.addEventListener('shown.bs.modal', () => {
      if (!analysis.value && !loading.value && !error.value) {
        loadAnalysis()
      }
    })
  }
})

onUnmounted(() => {
  if (bsModal) bsModal.dispose()
})

defineExpose({ show, hide })
</script>

<style scoped>
.ai-analysis-content {
  font-size: 0.9rem;
  line-height: 1.8;
  color: #333;
}
.analysis-text :deep(h1) { font-size: 1.2rem; font-weight: 700; margin-top: 1rem; }
.analysis-text :deep(h2) { font-size: 1.1rem; font-weight: 700; margin-top: 1rem; color: #0d6efd; }
.analysis-text :deep(h3) { font-size: 1rem; font-weight: 600; margin-top: 0.8rem; }
.analysis-text :deep(h4) { font-size: 0.9rem; font-weight: 600; margin-top: 0.6rem; }
.analysis-text :deep(ul), .analysis-text :deep(ol) { padding-left: 1.2rem; margin-bottom: 0.5rem; }
.analysis-text :deep(li) { margin-bottom: 0.2rem; }
.analysis-text :deep(strong) { color: #0d6efd; }
.analysis-text :deep(table) {
  width: 100%;
  margin: 0.8rem 0;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.analysis-text :deep(th) {
  background: #f0f4ff;
  padding: 6px 10px;
  border: 1px solid #d0d7e5;
  font-weight: 600;
  text-align: left;
}
.analysis-text :deep(td) {
  padding: 5px 10px;
  border: 1px solid #d0d7e5;
}
.analysis-text :deep(tr:nth-child(even)) { background: #fafbfd; }
.analysis-text :deep(code) {
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.85em;
  color: #d63384;
}
.analysis-text :deep(pre) {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
}
.analysis-text :deep(hr) { margin: 0.8rem 0; border-color: #e0e0e0; }
.analysis-text :deep(blockquote) {
  border-left: 3px solid #0d6efd;
  padding-left: 12px;
  color: #666;
  margin: 0.8rem 0;
}
</style>
