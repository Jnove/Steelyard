import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import type { EvalResult, RankResponse } from '../src/api/types'
import { comparisonRows, comparisonSchemes, dimensionScore, orderSchemes, pairSummary, rowScore, rowStatus, scoreDifference, signedScore } from '../src/utils/comparison'
import { comparisonSvg } from '../src/components/comparison/ComparisonExport'

const fixture = JSON.parse(readFileSync(new URL('../src/mocks/fixtures/data.json', import.meta.url), 'utf8'))
const results: EvalResult[] = fixture.evaluation.results
const rank: RankResponse = fixture.ranks.government

test('角色变化及评估输入重排不改变方案身份、颜色或四维分数', () => {
  const original = comparisonSchemes(results, rank)
  for (const role of Object.values(fixture.ranks) as RankResponse[]) {
    const changed = comparisonSchemes([...results].reverse(), role)
    for (const scheme of original) {
      const same = changed.find(item => item.id === scheme.id)!
      assert.equal(same.color, scheme.color)
      assert.deepEqual(same.evaluation.dimension_scores, scheme.evaluation.dimension_scores)
      assert.equal(same.ranked?.rank, role.ranking.find(item => item.scheme_id === scheme.id)?.rank)
      assert.equal(same.ranked?.is_non_dominated, role.ranking.find(item => item.scheme_id === scheme.id)?.is_non_dominated)
    }
    assert.ok(changed.some(item => item.excluded && !item.ranked))
  }
})

test('真实项目的新编号仍按 scheme_id 关联，不使用字母、排名位置或 scheme_order 下标', () => {
  const rename = (id: string) => String(Number(id) + 100)
  const moved = results.map(item => ({ ...item, scheme_id: rename(item.scheme_id) })).reverse()
  const movedRank = { ...rank, ranking: [...rank.ranking].reverse().map(item => ({ ...item, scheme_id: rename(item.scheme_id) })), excluded: rank.excluded.map(item => ({ ...item, scheme_id: rename(item.scheme_id) })) }
  for (const scheme of comparisonSchemes(moved, movedRank)) {
    assert.equal(scheme.ranked?.scheme_id, scheme.excluded ? undefined : scheme.id)
    if (!scheme.excluded) assert.equal(scheme.ranked?.scheme_name, scheme.name)
  }
})

test('基准与双方案差值使用未舍入分数；零、负差和缺值各自保留', () => {
  assert.equal(signedScore(scoreDifference(10.04, 9.96)), '+0.1')
  assert.equal(signedScore(scoreDifference(9.96, 10.04)), '-0.1')
  assert.equal(signedScore(scoreDifference(0, 0)), '0.0')
  assert.equal(signedScore(-0.0001), '0.0')
  for (const absent of [null, undefined, NaN, Infinity]) assert.equal(scoreDifference(0, absent), null)
  assert.equal(signedScore(null), '—')
})

test('覆盖率为零的汇总不绘成零分；真实零分、缺数据与不适用保持区别', () => {
  const template = comparisonSchemes(results, rank)[0]
  const empty = { ...template, evaluation: { ...template.evaluation, dimension_scores: { quality: 0 }, dimension_coverage: { quality: 0 } } }
  const zero = { ...empty, evaluation: { ...empty.evaluation, dimension_coverage: { quality: 1 } } }
  assert.equal(dimensionScore(empty, 'quality'), null)
  assert.equal(dimensionScore(zero, 'quality'), 0)
  const row = { kind: 'metric' as const, key: 'NEW-01', name: '新指标', dimension: 'quality' as const }
  const withMetric = (status: 'scored' | 'not_applicable' | 'insufficient_data') => ({ ...template, evaluation: { ...template.evaluation, metrics: { 'NEW-01': { rule_id: 'NEW-01', name: '新指标', status, score: 0, dimension: 'quality' as const, formula: '原公式', source: 'TODO(专业组)' } } } })
  assert.equal(rowScore(row, withMetric('scored')), 0)
  assert.equal(rowScore(row, withMetric('not_applicable')), null)
  assert.equal(rowStatus(row, withMetric('not_applicable')), '不适用')
  assert.equal(rowStatus(row, withMetric('insufficient_data')), '数据不足')
})

test('矩阵动态汇集每套方案的规则，搜索自动展开相关维度且不受原型旧指标数限制', () => {
  const extra: EvalResult = { scheme_id: 'new', metrics: { 'NEW-99': { rule_id: 'NEW-99', name: '新增日照指标', dimension: 'quality', score: null, value: null, status: 'insufficient_data', formula: '未填', source: 'TODO(专业组)' } }, compliance: [{ rule_id: 'CHECK-99', name: '新增合规规则', status: 'not_applicable', message: '不适用' }] }
  const found = comparisonRows([...results, extra], 'scores', new Set(), 'all', 'NEW-99')
  assert.deepEqual(found.map(row => row.key), ['dim-quality', 'NEW-99'])
  const checks = comparisonRows([...results, extra], 'compliance', new Set(), 'all', 'CHECK-99')
  assert.deepEqual(checks.map(row => row.key), ['CHECK-99'])
  assert.equal(comparisonRows(results, 'scores', new Set(), 'green', '完全不存在').length, 0)
  assert.ok(comparisonRows(results, 'scores', new Set(['quality','structure','construction','green']), 'all', '').length > 12)
})

test('矩阵排名来自当前后端名次，参考方案排在参与方案后，输入不被改写', () => {
  const source = comparisonSchemes(results, rank), before = source.map(item => item.id)
  const sorted = orderSchemes(source, 'rank')
  assert.equal(sorted[0].id, rank.ranking[0].scheme_id)
  assert.ok(sorted.at(-1)?.excluded)
  assert.deepEqual(source.map(item => item.id), before)
})

test('SVG 导出保留实际角色、筛选范围、基准差值与四种合规状态，并转义名称', () => {
  const schemes = comparisonSchemes(results, rank).slice(0, 2)
  const rows = comparisonRows(results, 'scores', new Set(), 'all', '')
  const svg = comparisonSvg({ view: 'matrix', projectName: '<script>alert(1)</script> & 项目', roleName: '设计单位', schemes, rows, mode: 'difference', baseline: schemes[0], xAxis: 'quality', yAxis: 'construction', selectedId: schemes[0].id })
  assert.ok(svg.includes('&lt;script&gt;alert(1)&lt;/script&gt; &amp; 项目'))
  assert.ok(svg.includes('设计单位'))
  assert.ok(svg.includes('分差基准：'))
  assert.ok(svg.includes('0.0'))
  assert.ok(!svg.includes('<script>') && !svg.includes('<foreignObject') && !svg.includes('<image') && !svg.includes('href='))
  const rule = { key: 'STATUS-1', name: '状态验证', kind: 'compliance' as const }
  const statuses = ['passed','failed','not_applicable','insufficient_data'] as const
  const checked = statuses.map((status, index) => ({ ...schemes[0], id: String(index), name: String(index), evaluation: { scheme_id: String(index), compliance: [{ rule_id: 'STATUS-1', name: '状态验证', status, message: '验证' }] } }))
  const complianceSvg = comparisonSvg({ view: 'matrix', projectName: '项目', roleName: '自定义权重', schemes: checked, rows: [rule], mode: 'score', xAxis: 'quality', yAxis: 'construction', selectedId: '0' })
  for (const label of ['通过', '未通过', '不适用', '数据不足']) assert.ok(complianceSvg.includes(label))
})

test('双方案小结仅描述有效得分差异，不把缺项解释为得分相同', () => {
  const scheme = comparisonSchemes(results, rank)[0]
  const missing = { ...scheme, evaluation: { scheme_id: scheme.id, dimension_scores: {} } }
  const summary = pairSummary(scheme, missing)
  assert.ok(summary.includes('缺少可比较的分数'))
  assert.ok(!summary.includes('得分相同') && !summary.includes('得分更高'))
})
