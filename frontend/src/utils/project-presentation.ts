import type { Project } from '../api/types'

export function isTeachingCase(project: Pick<Project, 'name'>): boolean {
  return project.name.includes('教学') && !project.name.includes('虚构')
}

/** 优先展示有真实地块背景的教学案例，明确的用户选择优先。 */
export function featuredProject(items: Project[] = [], selectedId?: number): Project | undefined {
  return items.find(project => project.id === selectedId)
    ?? items.find(isTeachingCase)
    ?? items.find(project => project.name.includes('虚构'))
    ?? items[0]
}
