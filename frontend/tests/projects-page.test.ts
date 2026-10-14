import assert from 'node:assert/strict'
import { test } from 'node:test'
import { QueryClient } from '@tanstack/react-query'
import type { Project } from '../src/api/types'
import { clearProjectDerivedQueries, featuredProject } from '../src/pages/ProjectsPage'

const project = (id: number, name: string): Project => ({ id, name, params: {} as Project['params'], created_at: '', updated_at: '' })

test('首页优先真实地块教学案例，用户选择优先且旧虚构案例仍可回退', () => {
  const ordinary = project(1, '日常项目'), fictional = project(3, '虚构示例'), real = project(4, '下沙公租房一期 · 建成项目'), teaching = project(8, '下沙公租房一期 · 教学方案')
  const items = [ordinary, fictional, real, teaching]
  assert.equal(featuredProject(items)?.id, teaching.id)
  assert.equal(featuredProject(items, fictional.id)?.id, fictional.id)
  assert.equal(featuredProject(items, 999)?.id, teaching.id)
  assert.equal(featuredProject(items.slice(0, 3))?.id, fictional.id)
  assert.equal(featuredProject([ordinary, real])?.id, ordinary.id)
  assert.equal(featuredProject([]), undefined)
})

test('地块保存清除本项目旧评估、全部权重排名和 Agent 缓存，保留其他项目', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const localKeys = [
    ['evaluation', 7], ['rank', 7, { role: 'government' }], ['rank', 7, { weights: [1, 0, 0, 0] }],
    ['agent', 7], ['agent-results', 7], ['report', 7], ['chat', 7],
  ]
  const otherKeys = [['evaluation', 8], ['rank', 8, { role: 'government' }], ['agent', 8], ['project', 8], ['schemes', 7]]
  for (const key of [...localKeys, ...otherKeys, ['projects'], ['project', 7]]) client.setQueryData(key, { marker: 'before-edit' })
  await clearProjectDerivedQueries(client, 7)
  for (const key of localKeys) assert.equal(client.getQueryData(key), undefined, JSON.stringify(key))
  for (const key of otherKeys) {
    assert.deepEqual(client.getQueryData(key), { marker: 'before-edit' })
    assert.equal(client.getQueryState(key)?.isInvalidated, false)
  }
  assert.equal(client.getQueryState(['projects'])?.isInvalidated, true)
  assert.equal(client.getQueryState(['project', 7])?.isInvalidated, true)
  client.clear()
})
