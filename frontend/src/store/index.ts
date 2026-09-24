import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import type { ApiResponse } from '@/types'

export interface AuditResult {
  id: string
  filename: string
  score: number
  vulnerabilities: Vulnerability[]
  gasIssues: GasIssue[]
  timestamp: string
}

export interface AuditRecordSummary {
  id: string
  filename: string
  score: number
  timestamp: string
  vulnerabilityCount: number
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

export const useAuditStore = defineStore('audit', () => {
  const results = ref<AuditResult[]>([])
  const currentResult = ref<AuditResult | null>(null)
  const patterns = ref<any[]>([])

  async function uploadAndAudit(code: string, filename: string) {
    const res = await axios.post<ApiResponse<AuditResult>>('/api/audit', { code, filename })
    currentResult.value = res.data.data
    results.value.unshift(res.data.data)
    return res.data.data
  }

  async function fetchPatterns() {
    const res = await axios.get<ApiResponse<any[]>>('/api/patterns')
    patterns.value = res.data.data
  }

  async function fetchHistory() {
    const res = await axios.get<ApiResponse<AuditRecordSummary[]>>('/api/history')
    return res.data.data
  }

  async function fetchAuditDetail(id: string) {
    const res = await axios.get<ApiResponse<AuditResult>>(`/api/history/${id}`)
    return res.data.data
  }

  async function generateReport(id: string) {
    const res = await axios.post<ApiResponse<{ url: string }>>(`/api/report/${id}`)
    return res.data.data
  }

  return {
    results,
    currentResult,
    patterns,
    uploadAndAudit,
    fetchPatterns,
    fetchHistory,
    fetchAuditDetail,
    generateReport
  }
})
