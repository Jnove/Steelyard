import { request, USE_MOCK } from './client'
import type { Project, ProjectCreate } from './types'
export const projects = {
  async list(): Promise<Project[]> {
    if (USE_MOCK) return (await import('../mocks')).projects.list()
    return request('/projects')
  },
  async get(id: number): Promise<Project> {
    if (USE_MOCK) return (await import('../mocks')).projects.get(id)
    return request(`/projects/${id}`)
  },
  async create(input: ProjectCreate): Promise<Project> {
    if (USE_MOCK) return (await import('../mocks')).projects.create(input)
    return request('/projects', { method: 'POST', body: input })
  },
}
