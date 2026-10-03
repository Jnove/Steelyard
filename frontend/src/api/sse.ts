/** SSE 传输层；T8 暂定事件协议集中在下方适配器中。 */
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
  | { type: 'token'; text: string }
  | { type: 'tool_start'; id: string; name: string }
  | { type: 'tool_end'; id: string; name: string; result?: unknown }
  | { type: 'done'; message?: string }
  | { type: 'error'; message: string }

/**
 * T8 暂定协议适配器：后端协议确定后，仅在此处调整事件映射。
 * 命名事件的 JSON 数据为 token {text}、tool_start/tool_end {id,name,result?}、
 * done {message?}、error {message}；默认 message 事件支持 {type,...payload}。
 * 不推断 [DONE]、不强制转换文本、不猜测字段别名，也不静默回退到 Mock。
 */
export function adaptProvisionalEvent(frame: SSEFrame): ChatStreamEvent {
  let value: unknown
  try {
    value = JSON.parse(frame.data)
  } catch {
    throw new Error(`SSE ${frame.event} 事件不是有效 JSON（T8 暂定协议）`)
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('SSE 事件必须是 JSON 对象（T8 暂定协议）')
  }
  const payload = value as Record<string, unknown>
  const type = frame.event === 'message' ? payload.type : frame.event
  if (type === 'token' && typeof payload.text === 'string') return { type, text: payload.text }
  if ((type === 'tool_start' || type === 'tool_end') && typeof payload.id === 'string'
    && payload.id.length > 0 && typeof payload.name === 'string' && payload.name.length > 0) {
    return type === 'tool_start'
      ? { type, id: payload.id, name: payload.name }
      : { type, id: payload.id, name: payload.name, result: payload.result }
  }
  if (type === 'done' && (payload.message === undefined || typeof payload.message === 'string')) {
    return { type, message: payload.message }
  }
  if (type === 'error' && typeof payload.message === 'string') return { type, message: payload.message }
  throw new Error(`无法识别 SSE 事件或字段：${String(type)}（T8 暂定协议）`)
}

/** 读取真实 POST 流；非 SSE 响应、HTTP 失败和提前断流均作为错误抛出。 */
export async function* postSSE(
  url: string,
  body: Record<string, unknown>,
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
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
        const event = adaptProvisionalEvent(frame)
        yield event
        if (event.type === 'done' || event.type === 'error') return
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

/** 可取消的逐字显示间隔，供真实流和确定性的本地流共用。 */
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
