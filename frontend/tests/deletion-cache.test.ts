import assert from 'node:assert/strict'
import { test } from 'node:test'
import { QueryClient } from '@tanstack/react-query'
import { clearDeletedData } from '../src/utils/deletion-cache'

test('删除项目清除全部本项目缓存，列表回退且保留其他项目', async () => {
  const client = new QueryClient()
  const keys = [['project', 7], ['schemes', 7], ['evaluation', 7], ['rank', 7, 'government'], ['report', 7]]
  for (const key of [...keys, ['project', 8]]) client.setQueryData(key, { marker: true })
  client.setQueryData(['projects'], [{ id: 7 }, { id: 8 }])
  await clearDeletedData(client, 7)
  for (const key of keys) assert.equal(client.getQueryData(key), undefined)
  assert.deepEqual(client.getQueryData(['project', 8]), { marker: true })
  assert.deepEqual(client.getQueryData(['projects']), [{ id: 8 }])
  client.clear()
})

test('删除方案移除该候选和全部角色派生缓存，保留地块与其他方案', async () => {
  const client = new QueryClient()
  const keys = [['evaluation', 7], ['rank', 7, 'government'], ['rank', 7, 'resident'], ['agent', 7]]
  for (const key of [...keys, ['project', 7], ['rank', 8]]) client.setQueryData(key, { marker: true })
  client.setQueryData(['schemes', 7], [{ id: 3 }, { id: 4 }])
  await clearDeletedData(client, 7, 3)
  for (const key of keys) assert.equal(client.getQueryData(key), undefined)
  assert.deepEqual(client.getQueryData(['project', 7]), { marker: true })
  assert.deepEqual(client.getQueryData(['rank', 8]), { marker: true })
  assert.deepEqual(client.getQueryData(['schemes', 7]), [{ id: 4 }])
  client.clear()
})
