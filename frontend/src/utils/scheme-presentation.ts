import type { EvalResult, SchemeParams } from '../api/types'
import { dimensions } from '../constants/dimensions'

/** 展示只读取参数和当前评估；方案名称不构成工程结论。 */
export function parameterSummary(params: SchemeParams) {
  const facts = [
    params.buildings != null ? `${params.buildings} 栋` : null,
    params.floors != null ? `${params.floors} 层` : null,
    params.floor_height != null ? `层高 ${params.floor_height} m` : null,
  ].filter(Boolean)
  return { title: params.structure_type || '待录入结构', desc: facts.join(' · ') || '补充方案参数后，可进入评估与比较。' }
}

export function evaluationSummary(evaluation: EvalResult) {
  const failures = (evaluation.compliance ?? []).filter(item => item.status === 'failed' && item.severity === 'error')
  if (failures.length) return { title: '当前规则未通过', desc: `${failures.length} 项硬约束未通过；查看规则与待核定来源。` }
  const scores = dimensions.map(d => ({ ...d, score: evaluation.dimension_scores?.[d.key] }))
    .filter((d): d is typeof d & { score: number } => d.score != null && Number.isFinite(d.score))
    .sort((a, b) => b.score - a.score)
  if (!scores.length) return { title: '等待评估', desc: '得分由已录入参数和当前规则计算。' }
  return { title: `${scores[0].short}得分较高`, desc: `${scores[0].label} ${scores[0].score.toFixed(1)} 分，基于当前评分规则。` }
}

export function scoreTradeoff(selected: EvalResult | undefined, candidates: EvalResult[]) {
  if (!selected) return '当前评估尚未返回，暂不提炼维度取舍。'
  const gaps = dimensions.flatMap(d => {
    const score = selected.dimension_scores?.[d.key]
    const alternatives = candidates.filter(e => e.scheme_id !== selected.scheme_id)
      .map(e => ({ name: e.scheme_name || e.scheme_id, score: e.dimension_scores?.[d.key] }))
      .filter((e): e is typeof e & { score: number } => e.score != null && Number.isFinite(e.score))
      .sort((a, b) => b.score - a.score)
    return score != null && Number.isFinite(score) && alternatives[0] && alternatives[0].score > score
      ? [{ label: d.label, score, other: alternatives[0], gap: alternatives[0].score - score }] : []
  }).sort((a, b) => b.gap - a.gap)
  const gap = gaps[0]
  return gap ? `${gap.label}为 ${gap.score.toFixed(1)} 分，低于 ${gap.other.name} 的 ${gap.other.score.toFixed(1)} 分。可追溯该维度，讨论是否接受这项取舍。`
    : '当前可比较的评分中，未发现更高的单维得分；仍需结合数据覆盖率、规则来源和实际需求复核。'
}
