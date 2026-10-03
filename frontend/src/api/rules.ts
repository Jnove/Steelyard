import { request, USE_MOCK } from './client'
import type { RulesResponse, WithDemo } from './types'
export const rules = {
  async get(): Promise<WithDemo<RulesResponse>> {
    if (USE_MOCK) return (await import('../mocks')).rules.get()
    return request('/rules')
  },
}
