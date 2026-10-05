import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { adaptProvisionalEvent, createSSEParser, type SSEFrame } from '../src/api/sse.ts'
import { applyAgentEvent, numberSegments, type StreamContent } from '../src/api/agent-state.ts'

const initial = (): StreamContent => ({ content: '', tools: [], unverifiedNumbers: [] })

for (const [name, cached] of [['t8-report.sse.txt', false], ['t8-report-cache.sse.txt', true]] as const) {
  test(`页面消费真实 T8 验收事件流：${name}`, async () => {
    const wire = await readFile(new URL(`../../docs/evidence/${name}`, import.meta.url), 'utf8')
    const frames: SSEFrame[] = []
    const parser = createSSEParser(frame => frames.push(frame))
    // 保留真实协议数据，只改变传输边界。
    for (const character of wire) parser.push(character)
    const final = JSON.parse(frames.find(frame => frame.event === 'done')!.data)
    let state = initial()
    for (const frame of frames) state = applyAgentEvent(state, adaptProvisionalEvent(frame))
    assert.equal(state.content, final.report)
    assert.equal(state.cached, cached)
    assert.deepEqual(state.unverifiedNumbers, [])
    assert.ok(state.tools.every(tool => tool.status === 'done'))
    if (!cached) assert.ok(state.tools.length >= 2)
  })
}

test('重写丢弃旧草稿，最终数字偏移只应用到 done 正文，emoji 不错位', () => {
  let state = applyAgentEvent(initial(), { type: 'token', text: '错误草稿 999' })
  state = applyAgentEvent(state, { type: 'citation_warning', exhausted: false,
    unverified_numbers: [{ text: '999', start: 5, end: 8 }] })
  state = applyAgentEvent(state, { type: 'token', text: '第二稿', replace: true })
  assert.equal(state.content, '第二稿')
  assert.deepEqual(state.unverifiedNumbers, [])
  state = applyAgentEvent(state, { type: 'done', report: '😀 得分998.23',
    unverified_numbers: [{ text: '998.23', start: 4, end: 10 }], cached: false })
  const spans = numberSegments(state.content, state.unverifiedNumbers)
  assert.equal(spans.filter(span => span.unverified).map(span => span.text).join(''), '998.23')
  assert.equal(spans.map(span => span.text).join(''), '😀 得分998.23')
  assert.equal(state.citationWarning, true)
})
