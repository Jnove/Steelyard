import { ApiError, request, USE_MOCK } from './client'
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
  async update(id: number, input: Partial<ProjectCreate>): Promise<Project> {
    if (USE_MOCK) throw new ApiError(501, {
      detail: '离线快照不支持编辑地块或切换地区标准，请连接后端后修改并重新评估。',
      code: 'MOCK_PROJECT_UPDATE_UNSUPPORTED',
    })
    return request(`/projects/${id}`, { method: 'PUT', body: input })
  },
}
