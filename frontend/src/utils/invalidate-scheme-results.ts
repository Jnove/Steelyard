import type { QueryClient } from '@tanstack/react-query'

/** Discard in-flight preloads before invalidation, so pre-edit responses cannot restore stale results. */
export async function invalidateSchemeResults(client: QueryClient, projectId: number, refetchType: 'active' | 'none' = 'active') {
  const predicate = (query: { queryKey: readonly unknown[] }) =>
    ['schemes', 'evaluation', 'rank'].includes(String(query.queryKey[0])) && query.queryKey[1] === projectId
  await client.cancelQueries({ predicate })
  await client.invalidateQueries({ predicate, refetchType })
}
