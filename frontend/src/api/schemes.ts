import { ApiError, request, USE_MOCK } from './client'
import type { ImportResponse, Scheme, SchemeCreate, WithDemo } from './types'
export const schemes = {
  async remove(id: number, schemeId: number): Promise<void> {
    if (USE_MOCK) throw new ApiError(501, { detail: '离线快照不支持删除方案，请连接后端。' })
    return request(`/projects/${id}/schemes/${schemeId}`, { method: 'DELETE' })
  },
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
