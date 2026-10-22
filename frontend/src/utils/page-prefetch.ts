import type { QueryClient } from '@tanstack/react-query'
import { evaluationOptions, projectOptions, roleQueryOptions, schemaOptions, schemeOptions } from './project-queries'

export type ProjectPage = 'schemes' | 'dashboard'

/** Only read existing data. Hovering must never evaluate, rank or invoke the agent. */
export async function prefetchProjectData(client: QueryClient, id: number, page: ProjectPage): Promise<void> {
  if (!Number.isSafeInteger(id) || id <= 0) return
  const shared = client.prefetchQuery(projectOptions(id))
  if (page === 'schemes') {
    await Promise.all([shared, client.prefetchQuery(schemeOptions(id)), client.prefetchQuery(schemaOptions())])
  } else {
    await Promise.all([shared, client.prefetchQuery(evaluationOptions(id)), client.prefetchQuery(roleQueryOptions(id))])
  }
}
