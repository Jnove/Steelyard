import type { QueryClient } from '@tanstack/react-query'
import type { Project, Scheme } from '../api/types'

const derived = ['evaluation', 'rank', 'agent', 'agent-results', 'report', 'chat', 'suggestions']

export async function clearDeletedData(client: QueryClient, projectId: number, schemeId?: number): Promise<void> {
  const scoped = (query: { queryKey: readonly unknown[] }) =>
    [...derived, 'project', 'schemes'].includes(String(query.queryKey[0])) && query.queryKey[1] === projectId
  await client.cancelQueries({ predicate: scoped })
  client.removeQueries({ predicate: query => scoped(query)
    && (schemeId === undefined || derived.includes(String(query.queryKey[0]))) })
  if (schemeId === undefined) {
    await client.cancelQueries({ queryKey: ['projects'] })
    client.setQueryData<Project[]>(['projects'], current => current?.filter(project => project.id !== projectId))
    await client.invalidateQueries({ queryKey: ['projects'] })
  } else {
    client.setQueryData<Scheme[]>(['schemes', projectId], current => current?.filter(scheme => scheme.id !== schemeId))
    await client.invalidateQueries({ queryKey: ['schemes', projectId] })
  }
}
