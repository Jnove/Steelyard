import type { EvalResult } from '../api/types'
import type { QuestionSuggestions } from '../api/generated/QuestionSuggestions'

/** 离线演示根据当前结果组织问题，不冒充真实模型回答。 */
export function offlineQuestions(results: EvalResult[], schemeId?: string): QuestionSuggestions['questions'] {
  const selected = results.find(item => item.scheme_id === schemeId) ?? results[0]
  if (!selected) return ['当前地块应先补充哪些资料再做比选？', '开始评估前，候选方案还需要准备什么信息？']
  const name = (selected.scheme_name || `方案${selected.scheme_id}`).slice(0, 45)
  const issue = selected.compliance?.find(item => item.status === 'failed' || item.status === 'insufficient_data')
  const other = results.find(item => item.scheme_id !== selected.scheme_id)
  const question = issue ? `「${name}」还需补充哪些资料或处理哪些问题？` : `「${name}」的判断依据是什么？`
  const incomplete = Object.values(selected.dimension_coverage ?? {}).some(value => value < 1)
  const coverage = incomplete ? `「${name}」哪些维度的数据覆盖还不足？` : `「${name}」哪些评分依据最值得核实？`
  return other ? [question, `「${name}」与「${(other.scheme_name || `方案${other.scheme_id}`).slice(0, 35)}」的主要取舍是什么？`, coverage]
    : [question, coverage]
}
