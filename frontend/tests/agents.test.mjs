/** 使用现有 TypeScript 与 Node 内置测试验证网络分块；不增加依赖。 */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/api/agents.ts', import.meta.url), 'utf8')
const javascript = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const { streamAgent } = await import(`data:text/javascript;base64,${Buffer.from('import.meta.env = {};\n' + javascript).toString('base64')}`)

test('UTF-8 多字节与 CRLF 任意分块仍能读取替换、警告与最终正文', async () => {
  const originalFetch = globalThis.fetch
  const events = []
  const final = { report: '😀 得分998.23', intent: 'new_eval', cached: false, unverified_numbers: [{ text: '998.23', start: 4, end: 10 }] }
  const frames = [
    ': ping\r\n\r\n',
    'event: token\r\ndata: {"text":"旧草稿","replace":true}\r\n\r\n',
    'event: citation_warning\r\ndata: {"exhausted":true}\r\n\r\n',
    `event: done\r\ndata: ${JSON.stringify(final)}\r\n\r\n`,
  ]
  const bytes = new TextEncoder().encode(frames.join(''))
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/projects/1/report')
    assert.equal(options.method, 'POST')
    assert.deepEqual(JSON.parse(options.body), {})
    return new Response(new ReadableStream({
      start(controller) {
        // 单字节分块强制把中文、emoji 与 CRLF 边界拆开。
        for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
        controller.close()
      },
    }), { headers: { 'content-type': 'text/event-stream' } })
  }
  try {
    await streamAgent('1', 'report', {}, (event) => events.push(event), new AbortController().signal)
    assert.deepEqual(events.map((event) => event.name), ['token', 'citation_warning', 'done'])
    assert.deepEqual(events.at(-1).data, final)
    const issue = final.unverified_numbers[0]
    assert.equal(Array.from(final.report).slice(issue.start, issue.end).join(''), issue.text)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('没有最终事件的断流报错，保留已经收到的事件', async () => {
  const originalFetch = globalThis.fetch
  const events = []
  globalThis.fetch = async () => new Response('event: token\ndata: {"text":"未完成"}\n\n')
  try {
    await assert.rejects(streamAgent('1', 'chat', { message: '解释' }, (event) => events.push(event), new AbortController().signal), /事件流提前结束/)
    assert.equal(events.length, 1)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('error 为终止事件，非成功 HTTP 返回清晰错误', async () => {
  const originalFetch = globalThis.fetch
  const events = []
  try {
    globalThis.fetch = async () => new Response('event: error\ndata: {"message":"需要先评估"}\n\n')
    await streamAgent('1', 'chat', {}, (event) => events.push(event), new AbortController().signal)
    assert.equal(events[0].data.message, '需要先评估')
    globalThis.fetch = async () => new Response('项目不存在', { status: 404 })
    await assert.rejects(streamAgent('1', 'report', {}, () => {}, new AbortController().signal), /HTTP 404/)
  } finally {
    globalThis.fetch = originalFetch
  }
})
