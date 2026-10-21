import type { RankInput } from '../api/types'

export interface DecisionContext {
  projectId: number
  role: string
  weights?: number[]
  schemeId?: string
}
export const roleLabels: Record<string, string> = {
  government: '政府', resident: '住户', developer: '开发企业',
  contractor: '施工单位', design: '设计单位', custom: '自定义权重',
}
export const defaultContext = (projectId: number): DecisionContext => ({ projectId, role: 'government' })
export const contextKey = (projectId: number) => `zhuheng:decision-context:v1:${projectId}`

/** Stored preferences are untrusted; only four finite, nonnegative weights are accepted. */
export function normalizeContext(value: unknown, projectId: number): DecisionContext {
  const fallback = defaultContext(projectId)
  if (!value || typeof value !== 'object') return fallback
  const input = value as Record<string, unknown>
  if (input.projectId !== projectId || typeof input.role !== 'string') return fallback
  const role = input.role === 'residents' ? 'resident' : input.role === 'construction' ? 'contractor' : input.role
  if (!Object.hasOwn(roleLabels, role)) return fallback
  const schemeId = typeof input.schemeId === 'string' && input.schemeId.length > 0 && input.schemeId.length <= 100
    ? input.schemeId : undefined
  if (role !== 'custom') return { projectId, role, schemeId }
  if (!Array.isArray(input.weights) || input.weights.length !== 4
    || !input.weights.every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0)) return fallback
  const total = input.weights.reduce((sum, value: number) => sum + value, 0)
  if (!Number.isFinite(total) || total <= 0) return fallback
  return { projectId, role: 'custom', weights: input.weights.map(value => value / total), schemeId }
}

export function readContext(projectId: number, storage?: Pick<Storage, 'getItem'>): DecisionContext {
  try {
    return normalizeContext(JSON.parse((storage ?? window.sessionStorage).getItem(contextKey(projectId)) ?? 'null'), projectId)
  } catch { return defaultContext(projectId) }
}
export function writeContext(context: DecisionContext, storage?: Pick<Storage, 'setItem'>): void {
  try { (storage ?? window.sessionStorage).setItem(contextKey(context.projectId), JSON.stringify(normalizeContext(context, context.projectId))) }
  catch { /* Private browsing/storage quota must not prevent decision work. */ }
}
export function decisionInput(context: DecisionContext): RankInput {
  return context.role === 'custom' ? { weights: context.weights } : { role: context.role }
}
export function decisionLabel(context: DecisionContext): string {
  const normalized = normalizeContext(context, context.projectId)
  if (normalized.role !== 'custom') return `${roleLabels[normalized.role]}视角`
  return `自定义权重 · ${(normalized.weights ?? []).map(value => `${(value * 100).toFixed(1)}%`).join(' / ')}`
}
