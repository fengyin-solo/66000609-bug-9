<template>
  <div class="history">
    <h2>审计历史</h2>
    <div class="filter-bar">
      <input
        v-model="keyword"
        class="filter-input"
        placeholder="按文件名搜索..."
      />
      <select v-model="scoreLevel" class="filter-select">
        <option value="all">全部分值</option>
        <option value="high">高分 (≥70)</option>
        <option value="medium">中分 (40-69)</option>
        <option value="low">低分 (&lt;40)</option>
      </select>
    </div>
    <div v-if="loading" class="history-empty">加载中...</div>
    <div v-else-if="filteredHistory.length === 0" class="history-empty">
      {{ history.length === 0 ? "暂无审计记录" : "没有符合筛选条件的记录" }}
    </div>
    <div v-else class="history-list">
      <div v-for="item in filteredHistory" :key="item.id" class="history-card">
        <div class="history-file">{{ item.filename }}</div>
        <div class="history-score" :class="scoreClass(item.score)">{{ item.score }}分</div>
        <div class="history-time">{{ formatTime(item.timestamp) }}</div>
        <button class="btn-sm" @click="openDetail(item)">查看详情</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onActivated } from "vue"
import { useRouter } from "vue-router"
import { useAuditStore, type AuditRecordSummary } from "@/store"

defineOptions({ name: "HistoryView" })

const FILTER_STORAGE_KEY = "audit-history-filters"

const router = useRouter()
const store = useAuditStore()

const history = ref<AuditRecordSummary[]>([])
const loading = ref(false)
const keyword = ref("")
const scoreLevel = ref("all")

// Restore filters so they survive page refreshes.
try {
  const saved = JSON.parse(localStorage.getItem(FILTER_STORAGE_KEY) || "{}")
  if (typeof saved.keyword === "string") keyword.value = saved.keyword
  if (typeof saved.scoreLevel === "string") scoreLevel.value = saved.scoreLevel
} catch {
  // ignore corrupted cache
}

watch([keyword, scoreLevel], () => {
  localStorage.setItem(
    FILTER_STORAGE_KEY,
    JSON.stringify({ keyword: keyword.value, scoreLevel: scoreLevel.value })
  )
})

const filteredHistory = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return history.value.filter(item => {
    if (kw && !item.filename.toLowerCase().includes(kw)) return false
    if (scoreLevel.value === "high") return item.score >= 70
    if (scoreLevel.value === "medium") return item.score >= 40 && item.score < 70
    if (scoreLevel.value === "low") return item.score < 40
    return true
  })
})

function scoreClass(score: number) {
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low"
}

function formatTime(ts: string) {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadHistory() {
  loading.value = true
  try {
    history.value = await store.fetchHistory()
  } finally {
    loading.value = false
  }
}

function openDetail(item: AuditRecordSummary) {
  router.push(`/history/${item.id}`)
}

onMounted(loadHistory)
// Refresh whenever the view is re-entered (e.g. after a new audit or
// returning from the detail page) so new records show up immediately.
onActivated(loadHistory)
</script>

<style scoped>
.history { max-width: 800px; }
.filter-bar { display: flex; gap: 0.75rem; margin: 1rem 0; }
.filter-input { flex: 1; padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 8px; }
.filter-select { padding: 0.5rem 1rem; border: 1px solid #d1d5db; border-radius: 8px; background: white; }
.history-empty { padding: 2rem; text-align: center; color: #6b7280; background: white; border-radius: 12px; }
.history-list { display: flex; flex-direction: column; gap: 1rem; }
.history-card { background: white; border-radius: 12px; padding: 1.25rem; display: flex; align-items: center; gap: 1rem; }
.history-file { flex: 1; font-weight: 600; }
.history-score { padding: 0.25rem 0.75rem; border-radius: 8px; font-weight: 600; font-size: 0.875rem; }
.history-score.high { background: #d1fae5; color: #065f46; }
.history-score.medium { background: #fef3c7; color: #92400e; }
.history-score.low { background: #fee2e2; color: #991b1b; }
.history-time { color: #6b7280; font-size: 0.875rem; }
.btn-sm { background: #e5e7eb; border: none; padding: 0.25rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-sm:hover { background: #d1d5db; }
</style>
