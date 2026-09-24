import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import type { ApiResponse } from '@/types'

export interface AuditResult {
  id: string
  filename: string
  code?: string
  score: number
  vulnerabilities: Vulnerability[]
  gasIssues: GasIssue[]
  timestamp: string
}

export interface Vulnerability {
  type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  line: number
  description: string
  suggestion: string
  code?: string
}

export interface GasIssue {
  functionName: string
  currentGas: number
  optimizedGas: number
  suggestion: string
}

export interface HistoryFilters {
  q: string
  level: '' | 'high' | 'medium' | 'low'
}

export const useAuditStore = defineStore('audit', () => {
  const results = ref<AuditResult[]>([])
  const currentResult = ref<AuditResult | null>(null)
  const patterns = ref<any[]>([])

  async function uploadAndAudit(code: string, filename: string) {
    const res = await axios.post<ApiResponse<AuditResult>>('/api/audit', { code, filename })
    currentResult.value = res.data.data
    // 新记录置于列表最前，保证审计完成后历史里立刻出现
    results.value = [res.data.data, ...results.value]
    return res.data.data
  }

  async function fetchHistory(filters: HistoryFilters = { q: '', level: '' }) {
    const params: Record<string, string> = {}
    if (filters.q.trim()) params.q = filters.q.trim()
    if (filters.level) params.level = filters.level
    const res = await axios.get<ApiResponse<AuditResult[]>>('/api/history', { params })
    results.value = res.data.data
    return res.data.data
  }

  async function fetchAudit(id: string) {
    const res = await axios.get<ApiResponse<AuditResult>>(`/api/audits/${id}`)
    currentResult.value = res.data.data
    return res.data.data
  }

  async function fetchPatterns() {
    const res = await axios.get<ApiResponse<any[]>>('/api/patterns')
    patterns.value = res.data.data
  }

  return { results, currentResult, patterns, uploadAndAudit, fetchHistory, fetchAudit, fetchPatterns }
})
