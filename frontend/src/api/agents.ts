/** POST SSE 读取；支持跨网络分块与报告替换。 */
export interface NumberIssue {
  text: string
  start: number
  end: number
}

export interface AgentOutput {
  report: string
  intent: 'new_eval' | 'whatif' | 'explain' | 'reweight'
  unverified_numbers: NumberIssue[]
  cached: boolean
}

export interface AgentEvent {
  name: string
  data: Record<string, unknown>
}

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api'

export async function streamAgent(
  projectId: string,
  kind: 'report' | 'chat',
  body: object,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/${kind}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）：${await response.text()}`)
  const reader = response.body?.getReader()
  if (!reader) throw new Error('浏览器未提供响应流')
  const decoder = new TextDecoder()
  let buffer = ''
  let terminal = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let boundary: RegExpExecArray | null
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, boundary.index)
        buffer = buffer.slice(boundary.index + boundary[0].length)
        const lines = block.split(/\r?\n/)
        const name = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
        const data = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n')
        if (name && data) {
          if (name === 'done' || name === 'error') terminal = true
          onEvent({ name, data: JSON.parse(data) as Record<string, unknown> })
        }
      }
      if (done) break
    }
    if (!terminal) throw new Error('事件流提前结束，请重新请求')
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
