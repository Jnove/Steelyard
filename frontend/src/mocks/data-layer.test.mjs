// 在 frontend 目录运行：node --test src/mocks/data-layer.test.mjs
// 使用 Vite 已有的 esbuild 转译，不增加测试依赖，不写入构建文件。
import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'

const require = createRequire(import.meta.url)
const fixtures = JSON.parse(await readFile(new URL('./fixtures/data.json', import.meta.url), 'utf8'))
const grid = JSON.parse(await readFile(new URL('./fixtures/grid.json', import.meta.url), 'utf8'))
const example = await readFile(new URL('./fixtures/demo-import.xlsx', import.meta.url))
const invalidExample = await readFile(new URL('./fixtures/demo-invalid.xlsx', import.meta.url))
const stored = new Map()
globalThis.localStorage = {
  getItem: key => stored.get(key) ?? null,
  setItem: (key, value) => { stored.set(key, String(value)) },
  removeItem: key => { stored.delete(key) },
}

async function api(mock) {
  const result = await build({
    stdin: { contents: `
      export * from '../api/client';
      export { projects } from '../api/projects';
      export { schemes } from '../api/schemes';
      export { evaluation } from '../api/evaluation';
      export { ranking } from '../api/ranking';
      export { rules } from '../api/rules';
      export { schema } from '../api/schema';
      export { topsis } from './topsis';
    `, resolveDir: fileURLToPath(new URL('.', import.meta.url)), loader: 'ts' },
    bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent',
    define: { 'import.meta.env': JSON.stringify({ VITE_USE_MOCK: String(mock), VITE_API_BASE: '/api/' }),
      'import.meta.url': JSON.stringify(new URL('./index.ts', import.meta.url).href) },
  })
  const module = { exports: {} }
  new Function('require', 'module', 'exports', result.outputFiles[0].text)(require, module, module.exports)
  return module.exports
}
const mock = await api(true)
const real = await api(false)
const close = (a, b, tolerance = 1e-12) => assert.ok(Math.abs(a - b) <= tolerance, `${a} != ${b}`)
const rejects = (promise, status, code) => assert.rejects(promise, error =>
  error.name === 'ApiError' && error.status === status && (!code || error.body.code === code))

beforeEach(() => {
  stored.clear()
  globalThis.fetch = async () => { throw new Error('离线 API 不应发送网络请求') }
})

test('项目 CRUD 持久化、返回值隔离和跨项目错误', async () => {
  assert.equal((await mock.projects.list()).length, 1)
  const p = await mock.projects.create({ name: '测试项目', params: { site_area: 100 } })
  const s = await mock.schemes.create(p.id, { name: '测试方案', params: { floors: 12 } })
  s.name = '修改返回对象不能修改存储'
  assert.equal((await mock.schemes.list(p.id))[0].name, '测试方案')
  await mock.schemes.update(p.id, s.id, { name: '更新方案', params: { floors: 15 } })
  const reloaded = await api(true)
  assert.equal((await reloaded.projects.get(p.id)).name, p.name)
  assert.equal((await reloaded.schemes.list(p.id))[0].params.floors, 15)
  await rejects(mock.schemes.update(1, s.id, { name: '跨项目' }), 404)
  await rejects(mock.projects.get(999), 404)
  await rejects(mock.schemes.create(p.id, { name: '更新方案' }), 409)
  await rejects(mock.projects.create({ name: '' }), 422)
  await rejects(mock.schemes.create(p.id, { name: '非法参数', params: { floors: -1 } }), 422)
  await rejects(mock.schemes.create(p.id, { name: '非法枚举', params: { structure_type: '错误值' } }), 422)
  await mock.schemes.create(p.id, { name: '可空枚举', params: { structure_type: null } })
})

test('新项目逐条新增预设方案 → 评估 → 排序，编号和索引正确映射', async () => {
  const p = await mock.projects.create({ name: '独立流程', params: fixtures.projects[0].params })
  const seed = fixtures.schemes.filter(s => !s.is_whatif)
  const created = []
  // 倒序创建，确保数组下标不能被误当成方案编号或当前列表顺序。
  for (const s of [...seed].reverse()) created.push(await mock.schemes.create(p.id, { name: `副本 ${s.name}`, params: s.params }))
  assert.equal((await mock.evaluation.get(p.id)).results.length, 0)
  await rejects(mock.ranking.run(p.id), 409, 'MOCK_EVALUATION_REQUIRED')
  const evaluated = await mock.evaluation.run(p.id)
  assert.equal(evaluated.results.length, 5)
  assert.equal(evaluated.demo.mode, 'engine-fixture')
  assert.equal((await mock.evaluation.get(1)).results.length, 0)
  const ranked = await mock.ranking.run(p.id, { role: 'government' })
  assert.equal(ranked.project_id, p.id)
  const ids = new Set(created.map(s => String(s.id)))
  assert.ok(ranked.participant_ids.every(id => ids.has(id)))
  for (const [i, id] of ranked.participant_ids.entries()) {
    const row = ranked.ranking.find(r => r.scheme_id === id)
    close(row.closeness, ranked.topsis.schemes[i].closeness)
    assert.deepEqual(row.dimension_scores, fixtures.ranks.government.ranking.find(r => r.scheme_name === row.scheme_name.replace('副本 ', '')).dimension_scores)
    assert.ok(row.dominated_by.every(id => ids.has(id)))
  }
  assert.ok(ranked.excluded.every(r => ids.has(r.scheme_id)))
  const editable = created[0]
  await mock.schemes.update(p.id, editable.id, { name: '仅修改名称' })
  assert.equal((await mock.evaluation.get(p.id)).results.length, 0)
  await mock.evaluation.run(p.id)
  assert.ok((await mock.ranking.run(p.id)).ranking.some(r => r.scheme_name === '仅修改名称'))
})

test('新项目导入真实 Excel 解析快照 → 评估 → 排序', async () => {
  const p = await mock.projects.create({ name: 'Excel 独立项目' })
  const imported = await mock.schemes.importExcel(p.id, new File([example], '任意名称.xlsx'))
  assert.equal(imported.created.length, 5)
  assert.equal(imported.project_params_updated, true)
  assert.equal(imported.demo.mode, 'offline-crud')
  await mock.evaluation.run(p.id)
  assert.equal((await mock.ranking.run(p.id)).ranking.length, 4)
  assert.equal((await mock.evaluation.get(1)).results.length, 0)
  const second = await mock.schemes.importExcel(p.id, new File([example], '重复.xlsx'))
  assert.ok(second.created.every(s => s.name.endsWith(' (2)')))
  assert.equal((await mock.evaluation.get(p.id)).results.length, 0)
  await rejects(mock.evaluation.run(p.id), 409, 'MOCK_EVALUATION_UNSUPPORTED')
})

test('修改参数或新增方案后不复用旧评估，其他项目保持不变', async () => {
  await mock.evaluation.run(1)
  const p = await mock.projects.create({ name: '另一项目' })
  await mock.schemes.create(p.id, { name: '新增方案' })
  assert.equal((await mock.evaluation.get(1)).results.length, 5)
  await rejects(mock.evaluation.run(p.id), 409, 'MOCK_EVALUATION_UNSUPPORTED')
  await mock.schemes.update(1, 1, { params: { floors: 5 } })
  const empty = await mock.evaluation.get(1)
  assert.equal(empty.results.length, 0)
  assert.ok(empty.demo.unavailable.includes('evaluation'))
  await rejects(mock.ranking.run(1), 409)
  await rejects(mock.evaluation.run(1), 409, 'MOCK_EVALUATION_UNSUPPORTED')
})

test('全部角色快照、精确权重网格与真实名次翻转', async () => {
  await mock.evaluation.run(1)
  const roles = await mock.ranking.roles(1)
  assert.equal(roles.roles.length, 4)
  const values = []
  for (const role of roles.roles) {
    const ranked = await mock.ranking.run(1, { role: role.role })
    ranked.sensitivity.baseline_weights.forEach((w, i) => close(w, ranked.weights_used.weights[i]))
    assert.deepEqual(ranked.rank_acceptability, fixtures.ranks[role.role].rank_acceptability)
    values.push(ranked.ranking[0].closeness)
  }
  assert.equal(new Set(values).size, 4)
  const exact = await mock.ranking.run(1, { weights: [40, 30, 20, 10] })
  assert.equal(exact.demo.mode, 'engine-fixture')
  exact.sensitivity.baseline_weights.forEach((w, i) => close(w, exact.weights_used.weights[i]))
  const roleWeights = roles.roles[0].weights.map(v => v * 100)
  assert.equal((await mock.ranking.run(1, { weights: roleWeights })).demo.mode, 'engine-fixture')
  const flip = await mock.ranking.run(1, { weights: [1, 0, 0, 0] })
  assert.equal(flip.ranking[0].scheme_id, '5')
  assert.ok(flip.rank_acceptability && flip.sensitivity)
})

test('非网格自定义权重返回当前 TOPSIS；敏感性、概率为空且明确告知', async () => {
  await mock.evaluation.run(1)
  const custom = await mock.ranking.run(1, { weights: [37, 29, 21, 13] })
  assert.equal(custom.demo.mode, 'custom-topsis')
  assert.deepEqual(custom.weights_used.weights, [.37, .29, .21, .13])
  assert.equal(custom.sensitivity, null)
  assert.equal(custom.rank_acceptability, null)
  assert.ok(custom.ranking.every(r => r.first_place_probability === null))
  assert.ok(custom.demo.unavailable.includes('sensitivity'))
  assert.ok(custom.demo.unavailable.includes('first_place_probability'))
  assert.deepEqual(custom.pareto, fixtures.ranks.resident.pareto)
  for (const row of custom.ranking) assert.deepEqual(row.dimension_scores, fixtures.ranks.resident.ranking.find(r => r.scheme_id === row.scheme_id).dimension_scores)
  await rejects(mock.ranking.run(1, { weights: [0, 0, 0, 0] }), 400)
  await rejects(mock.ranking.run(1, { weights: [NaN, 1, 1, 1] }), 400)
  await rejects(mock.ranking.run(1, { weights: [-1, 1, 1, 1] }), 400)
  await rejects(mock.ranking.run(1, { weights: [1, 1] }), 400)
  await rejects(mock.ranking.run(1, { role: 'resident', weights: [1, 1, 1, 1] }), 422)
  await rejects(mock.ranking.run(1, { role: '__proto__' }), 400)
})

test('浏览器 TOPSIS 与全部 286 个真实引擎网格输出一致', () => {
  const reference = fixtures.ranks.resident
  const scores = reference.participant_ids.map(id => reference.ranking.find(r => r.scheme_id === id).dimension_scores)
  assert.equal(grid.length, 286)
  for (const snapshot of grid) {
    const actual = mock.topsis(scores, snapshot.weights_used.weights)
    for (const [i, row] of actual.schemes.entries()) {
      const expected = snapshot.topsis.schemes[i]
      close(row.closeness, expected.closeness)
      close(row.distance_to_best, expected.distance_to_best)
      close(row.distance_to_worst, expected.distance_to_worst)
      assert.equal(row.rank, expected.rank)
    }
  }
  const equal = mock.topsis([[0, 0, 0, 0], [0, 0, 0, 0]], [.25, .25, .25, .25])
  assert.ok(equal.schemes.every(s => s.rank === 1 && s.closeness === .5))
})

test('TOPSIS 的列缩放、行置换、并列名次和完全支配性质', () => {
  const weights = [.4, .3, .2, .1]
  const scores = [[90, 80, 70, 60], [50, 60, 40, 45], [65, 40, 50, 70]]
  const baseline = mock.topsis(scores, weights)
  const scaled = mock.topsis(scores.map(row => row.map((v, i) => v * [2, 100, .01, 5][i])), weights)
  scaled.schemes.forEach((row, i) => close(row.closeness, baseline.schemes[i].closeness))
  const permutation = [2, 0, 1]
  const permuted = mock.topsis(permutation.map(i => scores[i]), weights)
  permuted.schemes.forEach((row, i) => {
    close(row.closeness, baseline.schemes[permutation[i]].closeness)
    assert.equal(row.rank, baseline.schemes[permutation[i]].rank)
    assert.ok(row.closeness >= 0 && row.closeness <= 1)
  })
  const tied = mock.topsis([0, 50, 50, 100].map(v => [v, v, v, v]), weights)
  assert.deepEqual(tied.schemes.map(row => row.rank), [4, 2, 2, 1])
  assert.equal(tied.schemes[3].closeness, 1)
  assert.equal(tied.schemes[0].closeness, 0)
  assert.equal(mock.topsis([[7, 8, 9, 10]], weights).schemes[0].closeness, .5)
  assert.deepEqual(mock.topsis([], weights).schemes, [])
})

test('Excel 错误可重复且不产生部分写入', async () => {
  const before = await mock.schemes.list(1)
  await rejects(mock.schemes.importExcel(1, new File([], 'empty.xlsx')), 400)
  await rejects(mock.schemes.importExcel(1, new File(['x'], 'wrong.csv')), 400)
  await rejects(mock.schemes.importExcel(1, new File(['x'], 'unknown.xlsx')), 422, 'MOCK_IMPORT_UNSUPPORTED')
  await assert.rejects(mock.schemes.importExcel(1, new File([invalidExample], 'bad.xlsx')), error => {
    assert.equal(error.status, 422)
    const expected = fixtures.imports.find(item => item.filename === 'demo-invalid.xlsx').errors
    assert.ok(expected.length >= 2)
    assert.deepEqual(error.body.detail.errors, expected)
    return true
  })
  assert.deepEqual(await mock.schemes.list(1), before)
})

test('损坏存储明确报错，存储失败不会宣称写入成功', async () => {
  await mock.projects.list()
  const key = [...stored.keys()][0]
  stored.set(key, '{')
  await rejects(mock.projects.list(), 409, 'MOCK_STORAGE_CORRUPT')
  stored.clear()
  const original = localStorage.setItem
  localStorage.setItem = () => { throw new Error('空间不足') }
  try { await rejects(mock.projects.create({ name: '不能保存' }), 503, 'MOCK_STORAGE_UNAVAILABLE') }
  finally { localStorage.setItem = original }
})

test('真实路由 JSON、multipart、ApiError、空响应和取消', async () => {
  const calls = []
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return new Response('{}', { status: 200 }) }
  await real.projects.list(); await real.projects.get(2); await real.projects.create({ name: '项目' })
  await real.schemes.list(2); await real.schemes.create(2, { name: '方案' })
  await real.schemes.update(2, 8, { name: '改名' })
  await real.evaluation.get(2); await real.evaluation.run(2)
  await real.ranking.roles(2); await real.ranking.run(2, { role: 'resident' })
  await real.rules.get(); await real.schema.get()
  await real.schemes.importExcel(2, new File([example], 'file.xlsx'))
  assert.deepEqual(calls.map(c => c.url), ['/api/projects', '/api/projects/2', '/api/projects', '/api/projects/2/schemes',
    '/api/projects/2/schemes', '/api/projects/2/schemes/8', '/api/projects/2/evaluate', '/api/projects/2/evaluate',
    '/api/projects/2/rank/roles', '/api/projects/2/rank', '/api/rules', '/api/schema', '/api/projects/2/schemes/import'])
  assert.equal(calls[5].init.method, 'PUT')
  assert.equal(calls[7].init.method, 'POST')
  assert.deepEqual(JSON.parse(calls[9].init.body), { role: 'resident' })
  const upload = calls.at(-1).init
  assert.equal(upload.headers, undefined)
  assert.ok(upload.body instanceof FormData)
  assert.equal(upload.body.get('file').name, 'file.xlsx')
  globalThis.fetch = async () => new Response('{"detail":{"errors":[{"message":"失败"}]}}', { status: 422 })
  await assert.rejects(real.projects.list(), e => e instanceof real.ApiError && e.status === 422 && e.body.detail.errors[0].message === '失败')
  globalThis.fetch = async () => new Response('服务不可用', { status: 503 })
  await assert.rejects(real.projects.list(), e => e.body === '服务不可用')
  globalThis.fetch = async () => new Response(null, { status: 204 })
  assert.equal(await real.request('/empty'), undefined)
  globalThis.fetch = async () => new Response('<html>错误代理</html>')
  await rejects(real.projects.list(), 200)
  globalThis.fetch = async () => { throw new TypeError('网络断开') }
  await rejects(real.projects.list(), 0)
  const abort = new DOMException('取消', 'AbortError')
  globalThis.fetch = async () => { throw abort }
  await assert.rejects(real.request('/cancel', { signal: new AbortController().signal }), e => e === abort)
})
