import { request, USE_MOCK } from './client'
import type { ImportResponse, Scheme, SchemeCreate, WithDemo } from './types'
export const schemes = {
  async list(id: number): Promise<Scheme[]> {
    if (USE_MOCK) return (await import('../mocks')).schemes.list(id)
    return request(`/projects/${id}/schemes`)
  },
  async create(id: number, input: SchemeCreate): Promise<Scheme> {
    if (USE_MOCK) return (await import('../mocks')).schemes.create(id, input)
    return request(`/projects/${id}/schemes`, { method: 'POST', body: input })
  },
  async update(id: number, schemeId: number, input: Partial<SchemeCreate>): Promise<Scheme> {
    if (USE_MOCK) return (await import('../mocks')).schemes.update(id, schemeId, input)
    return request(`/projects/${id}/schemes/${schemeId}`, { method: 'PUT', body: input })
  },
  async importExcel(id: number, file: File): Promise<WithDemo<ImportResponse>> {
    if (USE_MOCK) return (await import('../mocks')).schemes.importExcel(id, file)
    const body = new FormData()
    body.append('file', file)
    return request(`/projects/${id}/schemes/import`, { method: 'POST', body })
  },
}
