/** SSE 传输层；真实事件按 docs/sse-events.md 的 T8 协议适配。 */
import type { NumberIssue } from './agents'
export interface SSEFrame {
  event: string
  data: string
  id?: string
}

/** 增量解析 SSE，支持 CR、LF、跨数据块的 CRLF、注释和多行 data。 */
export function createSSEParser(onFrame: (frame: SSEFrame) => void) {
  let line = ''
  let afterCR = false
  let firstCharacter = true
  let event = ''
  let data: string[] = []
  let id: string | undefined
  let eventSize = 0
  const maxEventSize = 1024 * 1024

  function finishLine() {
    const current = line
    line = ''
    if (current === '') {
      const frame = data.length ? { event: event || 'message', data: data.join('\n'), id } : undefined
      event = ''
      data = []
      eventSize = 0
      if (frame) onFrame(frame)
      return
    }
    if (current.startsWith(':')) return
    const colon = current.indexOf(':')
    const field = colon < 0 ? current : current.slice(0, colon)
    let value = colon < 0 ? '' : current.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'data') data.push(value)
    else if (field === 'event') event = value
    else if (field === 'id' && !value.includes('\0')) id = value
    // 忽略 retry 与未知字段；不会自动重放 POST 请求。
  }

  return {
    push(chunk: string) {
      for (const character of chunk) {
        if (firstCharacter) {
          firstCharacter = false
          if (character === '\uFEFF') continue
        }
        if (afterCR) {
          afterCR = false
          if (character === '\n') continue
        }
        if (++eventSize > maxEventSize) throw new Error('SSE 单个事件过大')
        if (character === '\r' || character === '\n') {
          finishLine()
          afterCR = character === '\r'
        } else line += character
      }
    },
    finish() {
      // 仅在空行处分发事件，不能将末尾截断的事件当作成功完成。
      line = ''
      data = []
      event = ''
      eventSize = 0
      afterCR = false
    },
  }
}

export type ChatStreamEvent =
  | { type: 'token'; text: string; replace?: boolean; attempt?: number }
  | { type: 'tool_start'; id: string; name: string }
  | { type: 'tool_end'; id: string; name: string; result?: unknown }
  | { type: 'node_start'; node: string; attempt?: number }
  | { type: 'citation_warning'; exhausted: boolean; unverified_numbers: NumberIssue[] }
  | { type: 'done'; message?: string; report?: string; unverified_numbers?: NumberIssue[]; cached?: boolean }
  | { type: 'error'; message: string }

/**
 * 将 T8 工具事件转换为页面已有的工具卡事件，兼容本地 Mock 的 tool_start/end。
 * 草稿替换与 done 的最终正文原样保留，不能把不同重写轮次拼接。
 */
export function adaptProvisionalEvent(frame: SSEFrame): ChatStreamEvent {
  let value: unknown
  try {
    value = JSON.parse(frame.data)
  } catch {
    throw new Error(`SSE ${frame.event} 事件不是有效 JSON`)
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('SSE 事件必须是 JSON 对象')
  }
  const payload = value as Record<string, unknown>
  const type = frame.event === 'message' ? payload.type : frame.event
  if (type === 'token' && typeof payload.text === 'string') return {
    type, text: payload.text,
    ...(typeof payload.replace === 'boolean' ? { replace: payload.replace } : {}),
    ...(typeof payload.attempt === 'number' ? { attempt: payload.attempt } : {}),
  }
  if (type === 'node_start' && typeof payload.node === 'string') return {
    type, node: payload.node, ...(typeof payload.attempt === 'number' ? { attempt: payload.attempt } : {}),
  }
  if ((type === 'tool_call' || type === 'tool_result') && typeof payload.node === 'string'
    && typeof payload.tool === 'string') {
    const tool = { id: `${payload.node}:${payload.tool}`, name: payload.tool }
    return type === 'tool_call' ? { type: 'tool_start', ...tool }
      : { type: 'tool_end', ...tool, result: payload.result }
  }
  if (type === 'citation_warning' && typeof payload.exhausted === 'boolean') return {
    type, exhausted: payload.exhausted, unverified_numbers: numberIssues(payload.unverified_numbers ?? []),
  }
  if ((type === 'tool_start' || type === 'tool_end') && typeof payload.id === 'string'
    && payload.id.length > 0 && typeof payload.name === 'string' && payload.name.length > 0) {
    return type === 'tool_start'
      ? { type, id: payload.id, name: payload.name }
      : { type, id: payload.id, name: payload.name, result: payload.result }
  }
  if (type === 'done' && (payload.message === undefined || typeof payload.message === 'string')
    && (payload.report === undefined || typeof payload.report === 'string')) {
    if (typeof payload.report === 'string') return {
      type, report: payload.report, unverified_numbers: numberIssues(payload.unverified_numbers ?? []),
      cached: payload.cached === true,
    }
    return { type, message: payload.message }
  }
  if (type === 'error' && typeof payload.message === 'string') return { type, message: payload.message }
  throw new Error(`无法识别 SSE 事件或字段：${String(type)}`)
}

function numberIssues(value: unknown): NumberIssue[] {
  if (!Array.isArray(value) || value.some(item => !item || typeof item.text !== 'string'
    || !Number.isInteger(item.start) || !Number.isInteger(item.end)
    || item.start < 0 || item.end < item.start)) throw new Error('引用校验位置无效')
  return value as NumberIssue[]
}

/** 读取真实 POST 流；非 SSE 响应、HTTP 失败和提前断流均作为错误抛出。 */
export async function* postSSEFrames(
  url: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
): AsyncGenerator<SSEFrame> {
  signal.throwIfAborted()
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    await response.body?.cancel()
    throw new Error(`流式接口请求失败：HTTP ${response.status}。请检查后端是否已实现此接口。`)
  }
  if (response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() !== 'text/event-stream') {
    await response.body?.cancel()
    throw new Error('流式接口未返回 text/event-stream，请检查后端接口与代理配置。')
  }
  if (!response.body) throw new Error('流式接口没有响应体')
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8', { fatal: true })
  const frames: SSEFrame[] = []
  const parser = createSSEParser((frame) => frames.push(frame))
  const abort = () => { void reader.cancel().catch(() => undefined) }
  signal.addEventListener('abort', abort, { once: true })
  try {
    while (true) {
      signal.throwIfAborted()
      const { done, value } = await reader.read()
      signal.throwIfAborted()
      parser.push(done ? decoder.decode() : decoder.decode(value, { stream: true }))
      for (const frame of frames) {
        signal.throwIfAborted()
        yield frame
        if (frame.event === 'done' || frame.event === 'error') return
      }
      frames.length = 0
      if (done) throw new Error('连接提前结束：尚未收到 done 事件。已接收的内容可能不完整。')
    }
  } finally {
    signal.removeEventListener('abort', abort)
    parser.finish()
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}

/** 页面事件与 T8 回调客户端共享同一套严格、可取消的 POST 流读取器。 */
export async function* postSSE(url: string, body: Record<string, unknown>, signal: AbortSignal): AsyncGenerator<ChatStreamEvent> {
  for await (const frame of postSSEFrames(url, body, signal)) {
    const event = adaptProvisionalEvent(frame)
    yield event
    if (event.type === 'done' || event.type === 'error') return
  }
}

/** 可取消的逐字显示间隔，供确定性的本地演示流使用。 */
export function streamDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  signal.throwIfAborted()
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', abort)
      reject(signal.reason ?? new DOMException('Aborted', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', abort)
      resolve()
    }, milliseconds)
    signal.addEventListener('abort', abort, { once: true })
  })
}

/** 此处不内置演示数值，文本和工具结果必须由调用方根据查询数据提供。 */
export async function* mockSSE(
  text: string,
  toolResult: unknown,
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  signal.throwIfAborted()
  const tool = { id: 'mock-fixture-read', name: '演示：读取已返回的评估与排序数据' }
  yield { type: 'tool_start', ...tool }
  await streamDelay(240, signal)
  yield { type: 'tool_end', ...tool, result: toolResult }
  for (const character of text) {
    signal.throwIfAborted()
    yield { type: 'token', text: character }
  }
  signal.throwIfAborted()
  yield { type: 'done' }
}
