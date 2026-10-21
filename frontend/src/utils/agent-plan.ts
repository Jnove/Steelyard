import type { AgentRequest } from '../api/generated/AgentRequest'
import type { PlanResponse } from '../api/agents'

/** Keep the exact planned request until explicit confirmation; never ask the model to infer it again. */
export function plannedRequest(request: AgentRequest, response: PlanResponse): AgentRequest {
  if (!response?.plan || !['new_eval', 'whatif', 'explain', 'reweight'].includes(response.plan.intent)) {
    throw new Error('服务未返回有效的执行计划，请重新发送。')
  }
  if (response.plan.intent === 'whatif' && (!response.plan.change || !response.proposal)) {
    throw new Error('推演计划缺少参数预览，未执行任何修改。请重新描述调整要求。')
  }
  if (response.plan.intent === 'whatif' && !/^[a-f0-9]{64}$/.test(response.fingerprint)) {
    throw new Error('推演预览缺少数据版本，未执行任何修改。请重新发送。')
  }
  return { ...request, ...response.plan,
    ...(response.plan.intent === 'whatif' ? { expected_fingerprint: response.fingerprint } : {}) }
}

export function previewValue(value: unknown): string {
  if (value == null) return '未填写'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
