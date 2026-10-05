import { request, USE_MOCK } from './client'
import type { RankInput, RankResponse, RolesResponse, WithDemo } from './types'
export const ranking = {
  async roles(id: number): Promise<WithDemo<RolesResponse>> {
    if (USE_MOCK) return (await import('../mocks')).ranking.roles(id)
    return request(`/projects/${id}/rank/roles`)
  },
  async run(id: number, input: RankInput = {}): Promise<RankResponse> {
    if (USE_MOCK) return (await import('../mocks')).ranking.run(id, input)
    return request(`/projects/${id}/rank`, { method: 'POST', body: input })
  },
}
