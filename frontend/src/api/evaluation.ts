import { request, USE_MOCK } from './client'
import type { EvaluateResponse, WithDemo } from './types'
export const evaluation = {
  async get(id: number): Promise<WithDemo<EvaluateResponse>> {
    if (USE_MOCK) return (await import('../mocks')).evaluation.get(id)
    return request(`/projects/${id}/evaluate`)
  },
  async run(id: number): Promise<WithDemo<EvaluateResponse>> {
    if (USE_MOCK) return (await import('../mocks')).evaluation.run(id)
    return request(`/projects/${id}/evaluate`, { method: 'POST' })
  },
}
