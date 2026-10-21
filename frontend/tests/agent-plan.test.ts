import assert from 'node:assert/strict'
import test from 'node:test'
import { planRequest, type PlanResponse } from '../src/api/agents.ts'
import { plannedRequest, previewValue } from '../src/utils/agent-plan.ts'

const proposal: PlanResponse = {
  fingerprint: 'a'.repeat(64),
  plan: { intent: 'whatif', change: { scheme_id: 9, field: 'std_floor_repeat', value: .85 }, role: 'construction', weights: null, rule_id: null },
  proposal: { scheme_name: '方案甲', field_label: '标准层重复率', before: .7, after: .85 },
}

test('计划请求仅调用只读 plan，携带当前方案/权重/历史；执行内容明确保留已确认计划', async () => {
  const fetchBefore = globalThis.fetch
  const signal = new AbortController().signal
  const body = { message: '把当前方案的标准层重复率改为 0.85', role: 'construction', scheme_id: 9,
    history: [{ role: 'user' as const, content: '当前方案的施工风险如何？' }] }
  const calls: string[] = []
  globalThis.fetch = async (url, options) => {
    calls.push(String(url))
    assert.equal(options?.method, 'POST')
    assert.equal(options?.signal, signal)
    assert.deepEqual(JSON.parse(String(options?.body)), body)
    return new Response(JSON.stringify(proposal), { headers: { 'content-type': 'application/json' } })
  }
  try {
    const response = await planRequest(2, body, signal)
    assert.deepEqual(calls, ['/api/projects/2/plan'])
    const confirmed = plannedRequest(body, response)
    assert.equal(confirmed.intent, 'whatif')
    assert.deepEqual(confirmed.change, proposal.plan.change)
    assert.equal(confirmed.message, body.message)
    assert.deepEqual(confirmed.history, body.history)
    assert.equal(confirmed.role, 'construction')
    assert.equal(confirmed.expected_fingerprint, 'a'.repeat(64))
  } finally { globalThis.fetch = fetchBefore }
})

test('不完整推演预览拒绝执行，明确的解释计划保持上下文', () => {
  assert.throws(() => plannedRequest({}, { ...proposal, proposal: null }), /参数预览/)
  assert.throws(() => plannedRequest({}, { ...proposal, plan: { ...proposal.plan, change: null } }), /参数预览/)
  assert.throws(() => plannedRequest({}, { ...proposal, fingerprint: '' }), /数据版本/)
  const explanation: PlanResponse = { fingerprint: 'b'.repeat(64), plan: { intent: 'explain', change: null, role: null, weights: [.1, .2, .3, .4], rule_id: null }, proposal: null }
  assert.deepEqual(plannedRequest({ message: '为什么', scheme_id: 9 }, explanation), { message: '为什么', scheme_id: 9, ...explanation.plan })
})

test('计划接口真实错误保留中文原因，零值/未填写/布尔值预览不混淆', async () => {
  const fetchBefore = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: '调整参数不合法，原方案未修改' }), { status: 422 })
  try { await assert.rejects(planRequest(2, {}, new AbortController().signal), /调整参数不合法/) }
  finally { globalThis.fetch = fetchBefore }
  assert.equal(previewValue(0), '0')
  assert.equal(previewValue(false), '否')
  assert.equal(previewValue(null), '未填写')
})
