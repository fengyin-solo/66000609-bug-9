<template>
  <div class="detail">
    <div class="detail-header">
      <button class="btn-back" @click="goBack">← 返回列表</button>
      <h2>审计详情</h2>
    </div>

    <div v-if="loading" class="detail-empty">加载中...</div>
    <div v-else-if="notFound" class="detail-empty">未找到该审计记录</div>

    <template v-else-if="record">
      <div class="detail-meta">
        <div class="meta-item"><span class="meta-label">文件名</span>{{ record.filename }}</div>
        <div class="meta-item"><span class="meta-label">审计时间</span>{{ formatTime(record.timestamp) }}</div>
        <button class="btn-primary" :disabled="exporting" @click="exportReport">
          {{ exporting ? "导出中..." : "导出PDF报告" }}
        </button>
      </div>

      <div class="score-card" :class="scoreClass">
        <div class="score-label">安全评分</div>
        <div class="score-value">{{ record.score }}</div>
        <div class="score-grade">{{ scoreGrade }}</div>
      </div>

      <div class="vulnerabilities">
        <h3>发现漏洞 ({{ record.vulnerabilities.length }})</h3>
        <div v-if="record.vulnerabilities.length === 0" class="detail-empty">未发现漏洞</div>
        <div v-for="(v, i) in record.vulnerabilities" :key="i + '-' + v.type" class="vuln-card" :class="v.severity">
          <div class="vuln-header">
            <span class="vuln-type">{{ v.type }}</span>
            <span class="vuln-severity">{{ v.severity }}</span>
          </div>
          <div class="vuln-line">行号: {{ v.line }}</div>
          <div class="vuln-desc">{{ v.description }}</div>
          <div class="vuln-suggest">建议: {{ v.suggestion }}</div>
          <pre v-if="v.code" class="vuln-code">{{ v.code }}</pre>
        </div>
      </div>

      <div v-if="record.gasIssues.length > 0" class="gas-section">
        <h3>Gas优化建议</h3>
        <div v-for="(g, i) in record.gasIssues" :key="i + '-' + g.functionName" class="gas-card">
          <div class="gas-fn">{{ g.functionName }}</div>
          <div class="gas-info">当前: {{ g.currentGas }} → 优化后: {{ g.optimizedGas }} ({{ Math.round((1 - g.optimizedGas / g.currentGas) * 100) }}%节省)</div>
          <div class="gas-suggest">{{ g.suggestion }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuditStore, type AuditResult } from "@/store"

defineOptions({ name: "HistoryDetailView" })

const route = useRoute()
const router = useRouter()
const store = useAuditStore()

const record = ref<AuditResult | null>(null)
const loading = ref(true)
const notFound = ref(false)
const exporting = ref(false)

const scoreClass = computed(() => {
  if (!record.value) return ""
  if (record.value.score >= 80) return "score-high"
  if (record.value.score >= 50) return "score-medium"
  return "score-low"
})

const scoreGrade = computed(() => {
  if (!record.value) return ""
  if (record.value.score >= 90) return "Excellent"
  if (record.value.score >= 70) return "Good"
  if (record.value.score >= 50) return "Fair"
  return "Poor"
})

function formatTime(ts: string) {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function goBack() {
  router.push("/history")
}

async function exportReport() {
  if (!record.value) return
  exporting.value = true
  try {
    const { url } = await store.generateReport(record.value.id)
    window.open(url, "_blank")
  } catch {
    alert("报告生成失败，请稍后重试")
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  const id = route.params.id as string
  try {
    record.value = await store.fetchAuditDetail(id)
  } catch {
    notFound.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.detail { max-width: 1000px; }
.detail-header { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.detail-header h2 { margin: 0; }
.btn-back { background: #e5e7eb; border: none; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; font-size: 0.875rem; }
.btn-back:hover { background: #d1d5db; }
.detail-empty { padding: 2rem; text-align: center; color: #6b7280; background: white; border-radius: 12px; }
.detail-meta { display: flex; align-items: center; gap: 2rem; background: white; border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
.meta-item { color: #374151; }
.meta-label { color: #6b7280; font-size: 0.875rem; margin-right: 0.5rem; }
.btn-primary { margin-left: auto; background: #8b5cf6; color: white; border: none; padding: 0.5rem 1.25rem; border-radius: 8px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.score-card { border-radius: 16px; padding: 2rem; text-align: center; color: white; margin-bottom: 2rem; }
.score-high { background: linear-gradient(135deg, #10b981, #059669); }
.score-medium { background: linear-gradient(135deg, #f59e0b, #d97706); }
.score-low { background: linear-gradient(135deg, #ef4444, #dc2626); }
.score-label { font-size: 0.875rem; opacity: 0.9; margin-bottom: 0.5rem; }
.score-value { font-size: 4rem; font-weight: 800; }
.score-grade { font-size: 1.25rem; opacity: 0.9; }
.vulnerabilities h3, .gas-section h3 { margin-bottom: 1rem; font-size: 1.125rem; }
.vuln-card { background: white; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; border-left: 4px solid; }
.vuln-card.critical { border-color: #dc2626; }
.vuln-card.high { border-color: #f59e0b; }
.vuln-card.medium { border-color: #3b82f6; }
.vuln-card.low { border-color: #6b7280; }
.vuln-header { display: flex; justify-content: space-between; margin-bottom: 0.75rem; }
.vuln-type { font-weight: 600; }
.vuln-severity { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; background: #fee2e2; color: #dc2626; }
.vuln-line { font-size: 0.75rem; color: #9ca3af; margin-bottom: 0.5rem; }
.vuln-desc { color: #374151; margin-bottom: 0.5rem; }
.vuln-suggest { font-size: 0.875rem; color: #6b7280; }
.vuln-code { margin-top: 0.75rem; background: #1e1e1e; color: #d4d4d4; padding: 0.75rem; border-radius: 8px; font-size: 0.75rem; overflow-x: auto; }
.gas-card { background: white; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; }
.gas-fn { font-weight: 600; color: #7c3aed; margin-bottom: 0.5rem; }
.gas-info { color: #059669; font-size: 0.875rem; margin-bottom: 0.5rem; }
.gas-suggest { font-size: 0.875rem; color: #6b7280; }
</style>
