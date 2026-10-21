import { useRef, useState } from 'react'
import { normalizeContext, readContext, writeContext, type DecisionContext } from './decision-context'

/** Pages are keyed by project ID, so state and in-flight work never cross projects. */
export function useDecisionContext(projectId: number) {
  const [context, setContext] = useState(() => readContext(projectId))
  const current = useRef(context)
  const updateContext = (update: Partial<DecisionContext>) => {
    const next = normalizeContext({ ...current.current, ...update, projectId }, projectId)
    current.current = next
    writeContext(next)
    setContext(next)
  }
  return [context, updateContext] as const
}
