/** T8 回调接口复用统一的 POST SSE 读取器。 */
import { postSSEFrames } from './sse'
export type { AgentOutput, NumberIssue } from './generated/AgentOutput'

export interface AgentEvent {
  name: string
  data: Record<string, unknown>
}

export async function streamAgent(
  projectId: string,
  kind: 'report' | 'chat',
  body: object,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const base = (import.meta.env?.VITE_API_BASE ?? '/api').replace(/\/$/, '')
  for await (const frame of postSSEFrames(`${base}/projects/${encodeURIComponent(projectId)}/${kind}`,
    body as Record<string, unknown>, signal)) {
    onEvent({ name: frame.event, data: JSON.parse(frame.data) as Record<string, unknown> })
  }
}
