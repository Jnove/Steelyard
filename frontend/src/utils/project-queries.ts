import { queryOptions } from '@tanstack/react-query'
import { projects } from '../api/projects'
import { schemes } from '../api/schemes'
import { evaluation } from '../api/evaluation'
import { ranking } from '../api/ranking'
import { schema } from '../api/schema'

export const projectOptions = (id: number) => queryOptions({
  queryKey: ['project', id], queryFn: () => projects.get(id),
})
export const schemeOptions = (id: number) => queryOptions({
  queryKey: ['schemes', id], queryFn: () => schemes.list(id),
})
export const evaluationOptions = (id: number) => queryOptions({
  queryKey: ['evaluation', id], queryFn: () => evaluation.get(id),
})
export const roleQueryOptions = (id: number) => queryOptions({
  queryKey: ['roles', id], queryFn: () => ranking.roles(id),
})
export const schemaOptions = () => queryOptions({
  queryKey: ['schema'], queryFn: () => schema.get(), staleTime: 5 * 60_000,
})
