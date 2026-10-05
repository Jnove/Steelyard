import { request, USE_MOCK } from './client'
import type { SchemaResponse } from './types'
export const schema = {
  async get(): Promise<SchemaResponse> {
    if (USE_MOCK) return (await import('../mocks')).schema.get()
    return request('/schema')
  },
}
