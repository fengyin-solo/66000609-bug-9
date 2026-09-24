<template>
  <div class="history">
    <h2>审计历史</h2>

    <div class="filter-bar">
      <input
        v-model="keyword"
        class="filter-input"
        type="search"
        placeholder="按文件名搜索..."
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      />
      <select v-model="level" class="filter-select" @change="applyFilters">
        <option value="">全部评分</option>
        <option value="high">高 (≥70)</option>
        <option value="medium">中 (40-69)</option>
        <option value="low">低 (&lt;40)</option>
      </select>
      <button class="btn-search" @click="applyFilters">筛选</button>
      <button v-if="hasActiveFilters" class="btn-reset" @click="resetFilters">重置</button>
      <span class="record-count">共 {{ history.length }} 条</span>
    </div>

    <div v-if="loading" class="state-tip">加载中...</div>
    <div v-else-if="errorMsg" class="state-tip error">{{ errorMsg }}</div>
    <div v-else-if="history.length === 0" class="state-tip">没有匹配的审计记录</div>

    <div v-else class="history-list">
      <div v-for="item in history" :key="item.id" class="history-card">
        <div class="history-file">{{ item.filename }}</div>
        <div class="history-score" :class="scoreLevel(item.score)">{{ item.score }}分</div>
        <div class="history-time">{{ item.timestamp }}</div>
        <button class="btn-sm" @click="openDetail(item.id)">查看详情</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onActivated, nextTick } from "vue"
import { useRouter, useRoute } from "vue-router"
import { useAuditStore, type AuditResult } from "@/store"

defineOptions({ name: "HistoryView" })

const router = useRouter()
const route = useRoute()
const auditStore = useAuditStore()

const history = ref<AuditResult[]>([])
const loading = ref(false)
const errorMsg = ref("")
const keyword = ref("")
const level = ref<"" | "high" | "medium" | "low">("")

// 筛选条件同步到 URL query，刷新/前进后退都能还原
function syncFromRoute() {
  keyword.value = typeof route.query.q === "string" ? route.query.q : ""
  level.value = (route.query.level as "" | "high" | "medium" | "low") || ""
}

const hasActiveFilters = computed(() => keyword.value.trim() !== "" || level.value !== "")

function scoreLevel(score: number) {
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low"
}

async function loadHistory() {
  loading.value = true
  errorMsg.value = ""
  try {
    history.value = await auditStore.fetchHistory({ q: keyword.value, level: level.value })
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail || "历史记录加载失败"
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  sessionStorage.removeItem("history-scroll")
  router.replace({
    path: "/history",
    query: {
      ...(keyword.value.trim() ? { q: keyword.value.trim() } : {}),
      ...(level.value ? { level: level.value } : {}),
    },
  })
}

function resetFilters() {
  keyword.value = ""
  level.value = ""
  sessionStorage.removeItem("history-scroll")
  router.replace({ path: "/history" })
}

function saveScroll() {
  const el = document.querySelector(".main-content") as HTMLElement | null
  sessionStorage.setItem("history-scroll", String(el ? el.scrollTop : window.scrollY))
}

function restoreScroll() {
  const saved = Number(sessionStorage.getItem("history-scroll") || 0)
  if (saved > 0) {
    const el = document.querySelector(".main-content") as HTMLElement | null
    if (el) el.scrollTop = saved
    window.scrollTo(0, saved)
  }
}

async function openDetail(id: string) {
  saveScroll()
  await router.push(`/history/${id}`)
}

async function refreshFromRoute() {
  syncFromRoute()
  await loadHistory()
  await nextTick()
  restoreScroll()
}

// 初次挂载及筛选 URL 变化（含刷新、前进后退）时都按 query 重新拉取
watch(() => route.query, refreshFromRoute, { immediate: true })
// keep-alive 从详情页返回时，还原之前的浏览位置
onActivated(async () => {
  await nextTick()
  restoreScroll()
})
</script>

<style scoped>
.history { max-width: 800px; }
.filter-bar { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; }
.filter-input { padding: 0.5rem 0.875rem; border: 1px solid #d1d5db; border-radius: 8px; flex: 1; min-width: 200px; }
.filter-select { padding: 0.5rem 0.875rem; border: 1px solid #d1d5db; border-radius: 8px; background: white; }
.btn-search { background: #667eea; color: white; border: none; padding: 0.5rem 1.125rem; border-radius: 8px; cursor: pointer; }
.btn-reset { background: #e5e7eb; border: none; padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer; }
.record-count { color: #6b7280; font-size: 0.875rem; margin-left: auto; }
.state-tip { background: white; border-radius: 12px; padding: 2.5rem; text-align: center; color: #6b7280; }
.state-tip.error { color: #dc2626; }
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
