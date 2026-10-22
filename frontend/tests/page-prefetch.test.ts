import assert from 'node:assert/strict'
import { test } from 'node:test'
import { QueryClient } from '@tanstack/react-query'
import { prefetchProjectData } from '../src/utils/page-prefetch'
import { evaluationOptions, schemaOptions, schemeOptions } from '../src/utils/project-queries'
import { invalidateSchemeResults } from '../src/utils/invalidate-scheme-results'

test('入口预加载只读请求去重，页面复用缓存；字段配置在30秒后仍有效', async t => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } })
  const calls: { path: string; method?: string }[] = []
  t.mock.method(globalThis, 'fetch', async (url: string, init: RequestInit) => {
    const path = String(url)
    calls.push({ path, method: init.method })
    return Response.json({ path })
  })
  try {
    await Promise.all([prefetchProjectData(client, 5, 'schemes'), prefetchProjectData(client, 5, 'schemes')])
    assert.equal(calls.length, 3)
    assert.ok(calls.every(call => call.method === 'GET'))
    await client.fetchQuery(schemeOptions(5))
    await client.fetchQuery(schemaOptions())
    assert.equal(calls.length, 3, 'page reuses the prefetched keys')
    client.setQueryData(['schema'], { path: '/api/schema' }, { updatedAt: Date.now() - 31_000 })
    await prefetchProjectData(client, 6, 'schemes')
    assert.equal(calls.filter(call => call.path.endsWith('/schema')).length, 1)
    await prefetchProjectData(client, 5, 'dashboard')
    assert.ok(calls.some(call => call.path.endsWith('/5/evaluate')))
    assert.ok(calls.some(call => call.path.endsWith('/5/rank/roles')))
    assert.ok(calls.every(call => call.method === 'GET'), 'no ranking, re-evaluation or model invocation on hover')
    const count = calls.length
    for (const id of [0, -1, 1.5, NaN, Infinity]) await prefetchProjectData(client, id, 'dashboard')
    assert.equal(calls.length, count)
  } finally { client.clear() }
})

test('保存后的失效操作丢弃尚未返回的预加载，旧响应不能覆盖新评估', async t => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } })
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let started!: () => void
  const received = new Promise<void>(resolve => { started = resolve })
  let revision = 1
  t.mock.method(globalThis, 'fetch', async (url: string) => {
    const captured = revision
    if (String(url).endsWith('/5/evaluate') && captured === 1) { started(); await gate }
    return Response.json({ revision: captured })
  })
  try {
    await prefetchProjectData(client, 6, 'dashboard')
    const pending = prefetchProjectData(client, 5, 'dashboard')
    await received
    await invalidateSchemeResults(client, 5)
    revision = 2
    release()
    await pending
    assert.equal(client.getQueryData(['evaluation', 5]), undefined)
    assert.deepEqual(await client.fetchQuery(evaluationOptions(5)), { revision: 2 })
    assert.deepEqual(client.getQueryData(['evaluation', 6]), { revision: 1 })
  } finally { release(); client.clear() }
})

test('预加载失败不会锁住错误；方案变更后失效的缓存可以重新读取', async t => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } })
  let missing = true
  let revision = 1
  t.mock.method(globalThis, 'fetch', async (url: string) => {
    const path = String(url)
    return path.endsWith('/5/evaluate') && missing
      ? Response.json({ detail: '还没有评估结果' }, { status: 404 })
      : Response.json({ revision })
  })
  try {
    await prefetchProjectData(client, 5, 'dashboard')
    assert.equal(client.getQueryData(['evaluation', 5]), undefined)
    missing = false
    await prefetchProjectData(client, 5, 'dashboard')
    assert.deepEqual(await client.fetchQuery(evaluationOptions(5)), { revision: 1 })
    await prefetchProjectData(client, 6, 'dashboard')
    revision = 2
    await client.invalidateQueries({ queryKey: ['evaluation', 5] })
    await prefetchProjectData(client, 5, 'dashboard')
    assert.deepEqual(await client.fetchQuery(evaluationOptions(5)), { revision: 2 })
    assert.deepEqual(client.getQueryData(['evaluation', 6]), { revision: 1 })
  } finally { client.clear() }
})
