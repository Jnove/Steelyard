import assert from 'node:assert/strict'
import test from 'node:test'
import { redistributeWeights } from '../src/utils/weights.ts'

test('滑杆到任一端点后，权重仍非负且总和为 1', () => {
  for (const original of [[.25,.25,.25,.25], [1,0,0,0], [0,.2,.3,.5]]) {
    for (let index = 0; index < 4; index++) {
      for (const value of [0,.01,.37,.99,1]) {
        const next = redistributeWeights(original,index,value)
        assert.equal(next[index],value)
        assert.ok(next.every(n => Number.isFinite(n) && n >= 0 && n <= 1))
        assert.ok(Math.abs(next.reduce((a,b)=>a+b,0)-1)<1e-12)
      }
    }
  }
})

test('未拖动的维度保持比例，且不修改原数组', () => {
  const original = [.1,.2,.3,.4]
  const next = redistributeWeights(original,0,.7)
  assert.ok(Math.abs(next[1]/next[2] - 2/3)<1e-12)
  assert.ok(Math.abs(next[3]/next[2] - 4/3)<1e-12)
  assert.deepEqual(original,[.1,.2,.3,.4])
})
