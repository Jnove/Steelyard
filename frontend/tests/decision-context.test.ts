import assert from 'node:assert/strict'
import test from 'node:test'
import { contextKey, decisionInput, decisionLabel, normalizeContext, readContext, writeContext } from '../src/utils/decision-context.ts'

test('视角、权重与方案按项目保存，刷新读取不会串到其他项目', () => {
  const saved = new Map<string, string>()
  const storage = { getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => { saved.set(key, value) } }
  const custom = { projectId: 1, role: 'custom', weights: [.1, .2, .3, .4], schemeId: '16' }
  writeContext(custom, storage)
  writeContext({ projectId: 2, role: 'contractor', schemeId: '23' }, storage)
  assert.deepEqual(readContext(1, storage), custom)
  assert.deepEqual(decisionInput(readContext(1, storage)), { weights: [.1, .2, .3, .4] })
  assert.deepEqual(decisionInput(readContext(2, storage)), { role: 'contractor' })
  assert.equal(readContext(2, storage).schemeId, '23')
  assert.equal(decisionLabel(readContext(2, storage)), '施工单位视角')
  assert.deepEqual(readContext(3, storage), { projectId: 3, role: 'government' })
  saved.set(contextKey(3), JSON.stringify(custom))
  assert.deepEqual(readContext(3, storage), { projectId: 3, role: 'government' })
})

test('无效、负数、非有限权重不发送到 API，合法比例先归一化', () => {
  for (const weights of [[], [1, 0, 0], [0, 0, 0, 0], [-.1, .2, .3, .6], [NaN, 0, 0, 1], [Infinity, 0, 0, 0], ['.25', .25, .25, .25]]) {
    assert.deepEqual(normalizeContext({ projectId: 1, role: 'custom', weights }, 1), { projectId: 1, role: 'government' })
  }
  assert.deepEqual(normalizeContext({ projectId: 1, role: '__proto__' }, 1), { projectId: 1, role: 'government' })
  assert.deepEqual(decisionInput(normalizeContext({ projectId: 1, role: 'construction', weights: [1, 0, 0, 0] }, 1)), { role: 'contractor' })
  assert.equal(normalizeContext({ projectId: 1, role: 'residents' }, 1).role, 'resident')
  assert.deepEqual(decisionInput(normalizeContext({ projectId: 1, role: 'custom', weights: [1, 2, 3, 4] }, 1)), { weights: [.1, .2, .3, .4] })
})

test('损坏或不可用的浏览器存储不阻断页面', () => {
  assert.deepEqual(readContext(4, { getItem: () => '{oops' }), { projectId: 4, role: 'government' })
  assert.deepEqual(readContext(4, { getItem: () => { throw new Error('blocked') } }), { projectId: 4, role: 'government' })
  assert.doesNotThrow(() => writeContext({ projectId: 4, role: 'government' }, { setItem: () => { throw new Error('quota') } }))
})
