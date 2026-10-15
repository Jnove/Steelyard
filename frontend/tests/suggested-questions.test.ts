import assert from 'node:assert/strict'
import { test } from 'node:test'
import { offlineQuestions } from '../src/utils/suggested-questions'
import type { EvalResult } from '../src/api/types'

test('离线建议随所选方案及真实失败项变化，不固定装配率假设', () => {
  const results = [
    { scheme_id: '1', scheme_name: '剪力墙候选', compliance: [{ rule_id: 'C-01', status: 'failed' }] },
    { scheme_id: '2', scheme_name: '模块化候选', compliance: [] },
  ] as EvalResult[]
  const first = offlineQuestions(results, '1'), second = offlineQuestions(results, '2')
  assert.match(first[0], /剪力墙候选.*C-01/)
  assert.match(second[0], /模块化候选/)
  assert.notDeepEqual(first, second)
  assert.ok(first.length <= 3 && second.length <= 3)
  assert.ok(!first.join('').includes('提高装配率'))
  assert.ok(offlineQuestions([]).every(question => !question.includes('排名第一')))
})
