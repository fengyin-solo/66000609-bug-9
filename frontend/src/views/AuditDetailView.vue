<template>
  <div class="detail">
    <div class="top-bar">
      <button class="btn-back" @click="goBack">← 返回历史</button>
    </div>

    <div v-if="loading" class="state-tip">加载中...</div>
    <div v-else-if="errorMsg" class="state-tip error">{{ errorMsg }}</div>

    <template v-else-if="result">
      <div class="detail-header">
        <h2>{{ result.filename }}</h2>
        <div class="detail-meta">
          <span class="history-time">{{ result.timestamp }}</span>
          <span class="history-score" :class="scoreLevel(result.score)">{{ result.score }}分</span>
        </div>
      </div>

      <div class="score-card" :class="scoreClass">
        <div class="score-label">安全评分</div>
        <div class="score-value">{{ result.score }}</div>
        <div class="score-grade">{{ scoreGrade }}</div>
      </div>

      <div v-if="result.code" class="code-section">
        <h3>合约代码</h3>
        <pre class="code-block">{{ result.code }}</pre>
      </div>

      <div class="vulnerabilities">
        <h3>发现漏洞 ({{ result.vulnerabilities.length }})</h3>
        <div v-for="(v, i) in result.vulnerabilities" :key="v.line + v.type + i" class="vuln-card" :class="v.severity">
          <div class="vuln-header">
            <span class="vuln-type">{{ v.type }}</span>
            <span class="vuln-severity">{{ v.severity }}</span>
          </div>
          <div class="vuln-line">第 {{ v.line }} 行</div>
          <div class="vuln-desc">{{ v.description }}</div>
          <div class="vuln-suggest">建议: {{ v.suggestion }}</div>
        </div>
        <div v-if="result.vulnerabilities.length === 0" class="empty-tip">未发现明显漏洞模式</div>
      </div>

      <div v-if="result.gasIssues.length > 0" class="gas-section">
        <h3>Gas优化建议</h3>
        <div v-for="g in result.gasIssues" :key="g.functionName" class="gas-card">
          <div class="gas-fn">{{ g.functionName }}</div>
          <div class="gas-info">当前: {{ g.currentGas }} → 优化后: {{ g.optimizedGas }} ({{ Math.round((1-g.optimizedGas/g.currentGas)*100) }}%节省)</div>
          <div class="gas-suggest">{{ g.suggestion }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { useRouter, useRoute } from "vue-router"
import { useAuditStore, type AuditResult } from "@/store"

defineOptions({ name: "AuditDetailView" })

const router = useRouter()
const route = useRoute()
const auditStore = useAuditStore()

const loading = ref(false)
const errorMsg = ref("")
const result = ref<AuditResult | null>(null)

function scoreLevel(score: number) {
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low"
}

const scoreClass = computed(() => {
  if (!result.value) return ""
  if (result.value.score >= 80) return "score-high"
  if (result.value.score >= 50) return "score-medium"
  return "score-low"
})

const scoreGrade = computed(() => {
  if (!result.value) return ""
  if (result.value.score >= 90) return "Excellent"
  if (result.value.score >= 70) return "Good"
  if (result.value.score >= 50) return "Fair"
  return "Poor"
})

async function load() {
  const id = String(route.params.id)
  loading.value = true
  errorMsg.value = ""
  try {
    result.value = await auditStore.fetchAudit(id)
  } catch (e: any) {
    errorMsg.value = e?.response?.status === 404 ? "该审计记录不存在或已被删除" : "详情加载失败"
  } finally {
    loading.value = false
  }
}

function goBack() {
  // 从历史列表进入则返回列表（筛选条件保留在 URL query 中）；
  // 直接打开详情页（无历史栈）时兜底跳到历史页
  if (window.history.state && window.history.state.back) {
    router.back()
  } else {
    router.push("/history")
  }
}

onMounted(load)
</script>

<style scoped>
.detail { max-width: 1000px; }
.top-bar { margin-bottom: 1rem; }
.btn-back { background: #e5e7eb; border: none; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; font-size: 0.875rem; }
.btn-back:hover { background: #d1d5db; }
.state-tip { background: white; border-radius: 12px; padding: 2.5rem; text-align: center; color: #6b7280; }
.state-tip.error { color: #dc2626; }
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.5rem; }
.detail-header h2 { margin: 0; }
.detail-meta { display: flex; align-items: center; gap: 0.75rem; }
.history-time { color: #6b7280; font-size: 0.875rem; }
.history-score { padding: 0.25rem 0.75rem; border-radius: 8px; font-weight: 600; font-size: 0.875rem; }
.history-score.high { background: #d1fae5; color: #065f46; }
.history-score.medium { background: #fef3c7; color: #92400e; }
.history-score.low { background: #fee2e2; color: #991b1b; }
.score-card { border-radius: 16px; padding: 2rem; text-align: center; color: white; margin-bottom: 2rem; }
.score-high { background: linear-gradient(135deg, #10b981, #059669); }
.score-medium { background: linear-gradient(135deg, #f59e0b, #d97706); }
.score-low { background: linear-gradient(135deg, #ef4444, #dc2626); }
.score-label { font-size: 0.875rem; opacity: 0.9; margin-bottom: 0.5rem; }
.score-value { font-size: 4rem; font-weight: 800; }
.score-grade { font-size: 1.25rem; opacity: 0.9; }
.code-section { margin-bottom: 2rem; }
.code-section h3, .vulnerabilities h3, .gas-section h3 { margin-bottom: 1rem; font-size: 1.125rem; }
.code-block { background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 12px; font-family: "Fira Code", monospace; font-size: 0.8125rem; overflow-x: auto; white-space: pre; }
.vuln-card { background: white; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; border-left: 4px solid; }
.vuln-card.critical { border-color: #dc2626; }
.vuln-card.high { border-color: #f59e0b; }
.vuln-card.medium { border-color: #3b82f6; }
.vuln-card.low { border-color: #6b7280; }
.vuln-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; }
.vuln-type { font-weight: 600; }
.vuln-severity { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; background: #fee2e2; color: #dc2626; }
.vuln-line { font-size: 0.8125rem; color: #6b7280; margin-bottom: 0.5rem; }
.vuln-desc { color: #374151; margin-bottom: 0.5rem; }
.vuln-suggest { font-size: 0.875rem; color: #6b7280; }
.empty-tip { color: #6b7280; font-size: 0.875rem; padding: 1rem 0; }
.gas-card { background: white; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; }
.gas-fn { font-weight: 600; color: #7c3aed; margin-bottom: 0.5rem; }
.gas-info { color: #059669; font-size: 0.875rem; margin-bottom: 0.5rem; }
.gas-suggest { font-size: 0.875rem; color: #6b7280; }
</style>
