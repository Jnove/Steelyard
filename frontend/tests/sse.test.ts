import assert from 'node:assert/strict'
import { getEventListeners } from 'node:events'
import test from 'node:test'
import {
  adaptProvisionalEvent, createSSEParser, mockSSE, postSSE, streamDelay,
  type ChatStreamEvent, type SSEFrame,
} from '../src/api/sse.ts'

const encoder = new TextEncoder()
const signal = () => new AbortController().signal
test('SSE errors preserve valid HTTP status for recovery and support older payloads', () => {
  const adapt = (payload: Record<string, unknown>) => adaptProvisionalEvent({ event: 'error', data: JSON.stringify(payload) })
  assert.deepEqual(adapt({ message: '重新预览', status: 409 }), { type: 'error', message: '重新预览', status: 409 })
  assert.deepEqual(adapt({ message: '失败' }), { type: 'error', message: '失败' })
  for (const status of [200, 600, 409.5, '409', null]) {
    assert.deepEqual(adapt({ message: '失败', status }), { type: 'error', message: '失败' })
  }
})
const wireEvent = (event: string, data: unknown, newline = '\n') =>
  `event: ${event}${newline}data: ${JSON.stringify(data)}${newline}${newline}`
async function collect<T>(stream: AsyncIterable<T>) {
  const result: T[] = []
  for await (const event of stream) result.push(event)
  return result
}
function responseWithChunks(chunks: Uint8Array[], onCancel = () => {}) {
  let index = 0
  return new Response(new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) controller.enqueue(chunks[index++])
      else controller.close()
    },
    cancel: onCancel,
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

test('在每个字符边界拆包均正确解析 CRLF、多行数据、BOM 和注释', () => {
  const source = '\uFEFF: heartbeat\r\nevent: token\r\nid: one\r\nretry: 100\r\nunknown: ignored\r\n'
    + 'data: {\r\ndata:  "text": "你好🌊"\r\ndata: }\r\n\r\n'
    + 'event: done\ndata: {}\n\n'
  const expected: SSEFrame[] = [
    { event: 'token', data: '{\n "text": "你好🌊"\n}', id: 'one' },
    { event: 'done', data: '{}', id: 'one' },
  ]
  for (let split = 0; split <= source.length; split++) {
    const frames: SSEFrame[] = []
    const parser = createSSEParser((frame) => frames.push(frame))
    parser.push(source.slice(0, split))
    parser.push(source.slice(split))
    parser.finish()
    assert.deepEqual(frames, expected, `拆包位置：${split}`)
  }
  const frames: SSEFrame[] = []
  const parser = createSSEParser((frame) => frames.push(frame))
  for (const character of source) parser.push(character)
  assert.deepEqual(frames, expected)
})

test('支持单独 CR、空数据、无冒号字段、ID 重置及单个可选空格', () => {
  const frames: SSEFrame[] = []
  const parser = createSSEParser((frame) => frames.push(frame))
  parser.push('id: kept\r\rdata\r\revent: custom\rdata:  leading\rdata:\rid: bad\0id\r\r')
  parser.push('id:\revent:\rdata: last\r\r')
  assert.deepEqual(frames, [
    { event: 'message', data: '', id: 'kept' },
    { event: 'custom', data: ' leading\n', id: 'kept' },
    { event: 'message', data: 'last', id: '' },
  ])
})

test('不分发注释、空事件及结束时尚未完整接收的事件', () => {
  const frames: SSEFrame[] = []
  const parser = createSSEParser((frame) => frames.push(frame))
  parser.push(': hello\n\nevent: token\n\n\n')
  parser.push('data: {"text":"unfinished"}\n')
  parser.finish()
  parser.finish()
  assert.deepEqual(frames, [])
})

test('限制未终止或超大事件的长度', () => {
  const parser = createSSEParser(() => assert.fail('不得分发超大事件'))
  assert.throws(() => parser.push('data: ' + 'x'.repeat(1024 * 1024)), /事件过大/)
})

test('SSE 适配器校验命名事件和带类型字段的事件，不强制转换数据', () => {
  const adapt = (event: string, data: unknown) => adaptProvisionalEvent({ event, data: JSON.stringify(data) })
  assert.deepEqual(adapt('token', { text: '' }), { type: 'token', text: '' })
  assert.deepEqual(adapt('message', { type: 'token', text: '中文' }), { type: 'token', text: '中文' })
  assert.deepEqual(adapt('tool_start', { id: 'a', name: '评估' }), { type: 'tool_start', id: 'a', name: '评估' })
  assert.deepEqual(adapt('tool_end', { id: 'a', name: '评估', result: { score: 82.5 } }),
    { type: 'tool_end', id: 'a', name: '评估', result: { score: 82.5 } })
  assert.deepEqual(adapt('done', { message: '完成' }), { type: 'done', message: '完成' })
  assert.deepEqual(adapt('error', { message: '引擎不可用' }), { type: 'error', message: '引擎不可用' })
  for (const [event, data] of [
    ['token', { text: 42 }], ['tool_start', { id: '', name: 'tool' }],
    ['tool_end', { id: 'a' }], ['done', { message: false }], ['error', {}],
    ['unsupported', {}], ['message', {}], ['token', []], ['token', null],
  ] as const) assert.throws(() => adapt(event, data), /无法识别|JSON 对象/)
  assert.throws(() => adaptProvisionalEvent({ event: 'token', data: '[DONE]' }), /有效 JSON/)
})

test('POST 保留地址、请求体、请求头及取消信号，UTF-8 在每个字节边界拆包均正确', async (t) => {
  const source = encoder.encode('\uFEFF: ping\r\nevent: token\r\ndata: {\r\ndata: "text":"中文🌊"\r\ndata: }\r\n\r\n'
    + wireEvent('done', {}))
  let chunks: Uint8Array[] = []
  const requestSignal = signal()
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/projects/7/chat')
    assert.equal(init.method, 'POST')
    assert.deepEqual(init.headers, { 'Content-Type': 'application/json', Accept: 'text/event-stream' })
    assert.equal(init.body, JSON.stringify({ message: '你好' }))
    assert.equal(init.signal, requestSignal)
    return responseWithChunks(chunks)
  })
  const expected = [{ type: 'token', text: '中文🌊' }, { type: 'done', message: undefined }]
  for (let split = 0; split <= source.length; split++) {
    chunks = [source.slice(0, split), source.slice(split)]
    assert.deepEqual(await collect(postSSE('/api/projects/7/chat', { message: '你好' }, requestSignal)), expected)
  }
  chunks = Array.from(source, (byte) => Uint8Array.of(byte))
  assert.deepEqual(await collect(postSSE('/api/projects/7/chat', { message: '你好' }, requestSignal)), expected)
  assert.equal(getEventListeners(requestSignal, 'abort').length, 0)
})

test('报告 POST 发送空对象，同批事件各分发一次并在 done 处终止', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    assert.equal(url, '/api/projects/7/report')
    assert.equal(init.body, '{}')
    return responseWithChunks([encoder.encode(
      wireEvent('tool_start', { id: 'x', name: 'score' })
      + wireEvent('token', { text: '甲' }) + wireEvent('token', { text: '乙' })
      + wireEvent('tool_end', { id: 'x', name: 'score', result: 0 })
      + wireEvent('done', {}) + 'event: token\ndata: invalid trailing JSON\n\n',
    )])
  })
  const events = await collect(postSSE('/api/projects/7/report', {}, signal()))
  assert.deepEqual(events.map((event) => event.type), ['tool_start', 'token', 'token', 'tool_end', 'done'])
  assert.equal(events.filter((event) => event.type === 'token').map((event) => event.text).join(''), '甲乙')
})

test('真实 HTTP 或网络失败时不重试，也不回退到 Mock', async (t) => {
  for (const status of [404, 500, 503]) await t.test(`HTTP ${status} 错误`, async (child) => {
    const fetchMock = child.mock.method(globalThis, 'fetch', async () => new Response('unavailable', { status }))
    await assert.rejects(collect(postSSE('/api/projects/7/chat', { message: 'x' }, signal())), new RegExp(`HTTP ${status}`))
    assert.equal(fetchMock.mock.callCount(), 1)
  })
  await t.test('网络请求失败', async (child) => {
    const fetchMock = child.mock.method(globalThis, 'fetch', async () => { throw new TypeError('network down') })
    await assert.rejects(collect(postSSE('/chat', {}, signal())), /network down/)
    assert.equal(fetchMock.mock.callCount(), 1)
  })
})

test('拒绝 HTML 代理响应和空流式响应体', async (t) => {
  let response = new Response('<html>SPA fallback</html>', { headers: { 'Content-Type': 'text/html' } })
  t.mock.method(globalThis, 'fetch', async () => response)
  await assert.rejects(collect(postSSE('/chat', {}, signal())), /text\/event-stream/)
  response = new Response(null, { headers: { 'Content-Type': 'text/event-stream' } })
  await assert.rejects(collect(postSSE('/chat', {}, signal())), /没有响应体/)
})

test('过期推演的 HTTP409 保留状态与中文原因，不开始消费 SSE', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({ detail: '数据已发生变化，请重新预览并确认' }),
    { status: 409, headers: { 'Content-Type': 'application/json' } }))
  await assert.rejects(collect(postSSE('/chat', {}, signal())), (error: unknown) => {
    assert.ok(error instanceof Error && 'status' in error)
    assert.equal(error.status, 409)
    assert.match(error.message, /数据已发生变化/)
    return true
  })
})

test('提前断流时报告错误并保留已经收到的文本', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => responseWithChunks([encoder.encode(
    wireEvent('token', { text: '已收到' }) + 'event: done\ndata: {}\n',
  )]))
  const events: ChatStreamEvent[] = []
  await assert.rejects(async () => {
    for await (const event of postSSE('/chat', {}, signal())) events.push(event)
  }, /尚未收到 done/)
  assert.deepEqual(events, [{ type: 'token', text: '已收到' }])
})

test('无效 JSON 和损坏的 UTF-8 均明确报错', async (t) => {
  let chunks = [encoder.encode('event: token\ndata: not-json\n\n')]
  t.mock.method(globalThis, 'fetch', async () => responseWithChunks(chunks))
  await assert.rejects(collect(postSSE('/chat', {}, signal())), /有效 JSON/)
  chunks = [encoder.encode('data: '), Uint8Array.of(0xe4, 0xb8)]
  await assert.rejects(collect(postSSE('/chat', {}, signal())), TypeError)
})

test('服务端 error 事件立即终止流，不追加虚假的完成事件', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => responseWithChunks([encoder.encode(
    wireEvent('token', { text: 'partial' }) + wireEvent('error', { message: 'engine failed' })
    + wireEvent('done', {}) + wireEvent('token', { text: 'must not appear' }),
  )]))
  assert.deepEqual(await collect(postSSE('/chat', {}, signal())), [
    { type: 'token', text: 'partial' }, { type: 'error', message: 'engine failed' },
  ])
})

test('请求开始前取消时不执行 fetch', async (t) => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('must not fetch') })
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(collect(postSSE('/chat', {}, controller.signal)), { name: 'AbortError' })
  assert.equal(fetchMock.mock.callCount(), 0)
})

test('取消唤醒等待中的读取，并取消响应体、释放锁和移除监听器', { timeout: 2000 }, async (t) => {
  let ready!: () => void
  const reading = new Promise<void>((resolve) => { ready = resolve })
  let cancelled = 0
  const body = new ReadableStream<Uint8Array>({ pull() { ready() }, cancel() { cancelled++ } })
  t.mock.method(globalThis, 'fetch', async () => new Response(body, { headers: { 'Content-Type': 'text/event-stream' } }))
  const controller = new AbortController()
  const pending = collect(postSSE('/chat', {}, controller.signal))
  await reading
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
  assert.equal(cancelled, 1)
  assert.equal(body.locked, false)
  assert.equal(getEventListeners(controller.signal, 'abort').length, 0)
})

test('消费者提前退出时取消传输，已取消流的缓冲文本不能混入后续请求', async (t) => {
  let cancelled = 0
  t.mock.method(globalThis, 'fetch', async () => new Response(new ReadableStream<Uint8Array>({
    start(controller) { controller.enqueue(encoder.encode(wireEvent('token', { text: 'first' }) + wireEvent('token', { text: 'second' }))) },
    cancel() { cancelled++ },
  }), { headers: { 'Content-Type': 'text/event-stream' } }))
  for await (const event of postSSE('/chat', {}, signal())) {
    assert.deepEqual(event, { type: 'token', text: 'first' })
    break
  }
  assert.equal(cancelled, 1)
  const controller = new AbortController()
  const iterator = postSSE('/chat', {}, controller.signal)
  assert.deepEqual((await iterator.next()).value, { type: 'token', text: 'first' })
  controller.abort()
  await assert.rejects(iterator.next(), { name: 'AbortError' })
  assert.equal(cancelled, 2)
})

test('逐字显示的计时器在完成和取消时均清理监听器', async () => {
  const controller = new AbortController()
  await streamDelay(1, controller.signal)
  assert.equal(getEventListeners(controller.signal, 'abort').length, 0)
  const pending = streamDelay(60_000, controller.signal)
  controller.abort()
  await assert.rejects(pending, { name: 'AbortError' })
  assert.equal(getEventListeners(controller.signal, 'abort').length, 0)
  assert.throws(() => streamDelay(1, controller.signal), { name: 'AbortError' })
})

test('本地 Mock 确定性输出传入数值和 Unicode 码点，不请求网络', async (t) => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('mock must be local') })
  const result = { score: 71.25, closeness: 0.6789 }
  const first = await collect(mockSSE('中🌊', result, signal()))
  const second = await collect(mockSSE('中🌊', result, signal()))
  assert.deepEqual(first, second)
  assert.match(first[0].type === 'tool_start' ? first[0].name : '', /演示/)
  assert.equal(first[1].type === 'tool_end' ? first[1].result : undefined, result)
  assert.deepEqual(first.slice(2), [{ type: 'token', text: '中' }, { type: 'token', text: '🌊' }, { type: 'done' }])
  assert.equal(fetchMock.mock.callCount(), 0)
})

test('取消本地 Mock 后不继续产生工具完成或 done 事件', async () => {
  const beforeTool = new AbortController()
  const pendingTool = mockSSE('text', {}, beforeTool.signal)
  await pendingTool.next()
  beforeTool.abort()
  await assert.rejects(pendingTool.next(), { name: 'AbortError' })
  const beforeDone = new AbortController()
  const stream = mockSSE('字', {}, beforeDone.signal)
  await stream.next()
  await stream.next()
  assert.deepEqual((await stream.next()).value, { type: 'token', text: '字' })
  beforeDone.abort()
  await assert.rejects(stream.next(), { name: 'AbortError' })
})
