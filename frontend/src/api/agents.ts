/** T8 回调接口复用统一的 POST SSE 读取器。 */
import { postSSEFrames } from './sse'
import { API_BASE } from './base'
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
  for await (const frame of postSSEFrames(`${API_BASE}/projects/${encodeURIComponent(projectId)}/${kind}`,
    body as Record<string, unknown>, signal)) {
    onEvent({ name: frame.event, data: JSON.parse(frame.data) as Record<string, unknown> })
  }
}
