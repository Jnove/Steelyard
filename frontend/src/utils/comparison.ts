import type { EvalResult, RankResponse } from '../api/types'
import { dimensions, type DimensionKey } from '../constants/dimensions'
import { schemeColor } from '../theme'
import { schemeNameParts } from './presentation-names'

export type ComparisonView = 'map' | 'pair' | 'matrix'
export type MatrixDataset = 'scores' | 'compliance'
export type ScoreMode = 'score' | 'difference'
export interface ComparisonScheme {
  id: string
  name: string
  badge: string
  color: string
  evaluation: EvalResult
  ranked?: RankResponse['ranking'][number]
  excluded: boolean
  reason?: string
}
export interface ComparisonRow {
  key: string
  name: string
  kind: 'dimension' | 'metric' | 'compliance'
  dimension?: DimensionKey
  metricCount?: number
}
export interface ComparisonSelection { schemeId: string; row: ComparisonRow }

export const finiteScore = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
export const scoreText = (value: unknown) => finiteScore(value) ? value.toFixed(1) : '—'
export function scoreDifference(value: unknown, baseline: unknown): number | null {
  return finiteScore(value) && finiteScore(baseline) ? value - baseline : null
}
export function signedScore(value: unknown): string {
  if (!finiteScore(value)) return '—'
  // 差值用原数做差后再格式化；舍入到零时不显示 -0.0 或 +0.0。
  const rounded = value.toFixed(1)
  return Number(rounded) === 0 ? '0.0' : `${value > 0 ? '+' : ''}${rounded}`
}

export function comparisonSchemes(results: EvalResult[], ranking: RankResponse): ComparisonScheme[] {
  const identities = [...new Set(results.map(result => result.scheme_id))].sort((a, b) => a.localeCompare(b, 'en', { numeric: true }))
  return results.map(evaluation => {
    const id = evaluation.scheme_id
    const index = identities.indexOf(id)
    const name = evaluation.scheme_name || id
    const ranked = ranking.ranking.find(entry => entry.scheme_id === id)
    const excluded = ranking.excluded.find(entry => entry.scheme_id === id)
    return { id, name, badge: /^[A-Za-z](?:\s|$)/.test(name) ? name[0].toUpperCase() : String(index + 1).padStart(2, '0'),
      color: schemeColor(id), evaluation, ranked, excluded: !ranked,
      reason: excluded?.reason ?? (!ranked ? '未参与当前排名' : undefined) }
  })
}

export function dimensionScore(scheme: ComparisonScheme | undefined, key: DimensionKey): number | null {
  if (!scheme || scheme.evaluation.dimension_coverage?.[key] === 0) return null
  const score = scheme.evaluation.dimension_scores?.[key]
  return finiteScore(score) ? score : null
}
export function rowScore(row: ComparisonRow, scheme: ComparisonScheme | undefined): number | null {
  if (!scheme) return null
  if (row.kind === 'dimension') return row.dimension ? dimensionScore(scheme, row.dimension) : null
  if (row.kind !== 'metric') return null
  const metric = scheme.evaluation.metrics?.[row.key]
  if (metric?.status === 'insufficient_data' || metric?.status === 'not_applicable') return null
  return finiteScore(metric?.score) ? metric.score : null
}
export function rowStatus(row: ComparisonRow, scheme: ComparisonScheme | undefined): string {
  if (row.kind === 'compliance') {
    return ({ passed: '通过', failed: '未通过', insufficient_data: '数据不足', not_applicable: '不适用' })[
      scheme?.evaluation.compliance?.find(item => item.rule_id === row.key)?.status ?? 'insufficient_data']
  }
  if (row.kind === 'metric' && scheme?.evaluation.metrics?.[row.key]?.status === 'not_applicable') return '不适用'
  return '数据不足'
}
export function rowValue(row: ComparisonRow, scheme: ComparisonScheme | undefined): number | null {
  const value = row.kind === 'metric' ? scheme?.evaluation.metrics?.[row.key]?.value
    : scheme?.evaluation.compliance?.find(item => item.rule_id === row.key)?.value
  return finiteScore(value) ? value : null
}

export function comparisonRows(results: EvalResult[], dataset: MatrixDataset, expanded: Set<DimensionKey>, filter: DimensionKey | 'all', search: string): ComparisonRow[] {
  const query = search.trim().toLocaleLowerCase()
  const matches = (row: ComparisonRow) => !query || `${row.key} ${row.name}`.toLocaleLowerCase().includes(query)
  if (dataset === 'compliance') {
    const checks = new Map<string, ComparisonRow>()
    results.forEach(result => result.compliance?.forEach(item => {
      checks.set(item.rule_id, { key: item.rule_id, name: item.name, kind: 'compliance' })
    }))
    return [...checks.values()].filter(matches)
  }
  const metrics = new Map<string, ComparisonRow>()
  results.forEach(result => Object.values(result.metrics ?? {}).forEach(metric => {
    metrics.set(metric.rule_id, { key: metric.rule_id, name: metric.name, kind: 'metric', dimension: metric.dimension })
  }))
  return dimensions.flatMap(dim => {
    if (filter !== 'all' && dim.key !== filter) return []
    const children = [...metrics.values()].filter(metric => metric.dimension === dim.key)
    const parent: ComparisonRow = { key: `dim-${dim.key}`, name: dim.label, kind: 'dimension', dimension: dim.key, metricCount: children.length }
    const hits = children.filter(matches)
    if (query && !matches(parent) && !hits.length) return []
    return [parent, ...(expanded.has(dim.key) || query ? (query && !matches(parent) ? hits : children) : [])]
  })
}

export function orderSchemes(schemes: ComparisonScheme[], order: 'rank' | 'name'): ComparisonScheme[] {
  return [...schemes].sort((a, b) => order === 'rank'
    ? (a.ranked?.rank ?? Infinity) - (b.ranked?.rank ?? Infinity) || a.name.localeCompare(b.name, 'zh', { numeric: true })
    : a.name.localeCompare(b.name, 'zh', { numeric: true }))
}

export function pairSummary(first: ComparisonScheme | undefined, second: ComparisonScheme | undefined): string {
  if (!first || !second) return '需要两套方案才能比较。'
  const compared = dimensions.map(dim => ({ label: dim.label, difference: scoreDifference(dimensionScore(first, dim.key), dimensionScore(second, dim.key)) }))
  const more = compared.filter(item => finiteScore(item.difference) && item.difference > 1e-8).map(item => item.label)
  const less = compared.filter(item => finiteScore(item.difference) && item.difference < -1e-8).map(item => item.label)
  const equal = compared.filter(item => finiteScore(item.difference) && Math.abs(item.difference) <= 1e-8).map(item => item.label)
  const missing = compared.filter(item => !finiteScore(item.difference)).map(item => item.label)
  return [more.length ? `${schemeNameParts(first.name).title}在${more.join('、')}得分更高` : '', less.length ? `${schemeNameParts(second.name).title}在${less.join('、')}得分更高` : '',
    equal.length ? `${equal.join('、')}得分相同` : '', missing.length ? `${missing.join('、')}缺少可比较的分数` : ''].filter(Boolean).join('；') + '。'
}
