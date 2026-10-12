import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { buildingModel } from '../src/components/building-model'

test('体量展示不为缺失、非有限或无效的楼栋和层数补造参数', () => {
  for (const params of [{}, { buildings: 4 }, { buildings: 4, floors: null }, { buildings: Infinity, floors: 18 }, { buildings: -1, floors: 18 }, { buildings: .5, floors: 18 }, { buildings: 4, floors: 2.5 }]) {
    const model = buildingModel(params)
    assert.equal(model.volumes.length, 0)
    assert.ok(model.missing.length > 0)
  }
})

test('切换真实参数改变体量并保留原输入；未填层高仍能显示明确的概念比例', () => {
  const params = { buildings: 4, floors: 16, floor_height: 3.3, footprint: 2400 }
  const original = structuredClone(params)
  const first = buildingModel(params)
  const other = buildingModel({ ...params, buildings: 6, floors: 18, floor_height: 3.0 })
  assert.equal(first.volumes.length, 4)
  assert.equal(other.volumes.length, 6)
  assert.notEqual(first.volumes[0].height, other.volumes[0].height)
  assert.deepEqual(params, original)
  assert.equal(buildingModel({ buildings: 4, floors: 16 }).volumes.length, 4)
})

test('大规模数据限制显示开销，不改写原数值，并说明发生了展示限制', () => {
  const input = { buildings: 100000, floors: 100000, floor_height: 25, footprint: Number.MAX_VALUE }
  const model = buildingModel(input)
  assert.equal(model.capped, true)
  assert.ok(model.volumes.length <= 12)
  assert.ok(model.volumes.every(v => v.floors <= 48 && v.height <= 4.6 && Number.isFinite(v.width)))
  assert.equal(input.buildings, 100000)
  assert.equal(input.floors, 100000)
})

test('A–E 实际参数形成不同立面特征，不依赖名称或固定方案顺序', () => {
  const files = ['A_高品质', 'B_不合规', 'C_MiC高标准化', 'D_均衡', 'E_被支配']
  const models = files.map(name => {
    const scheme = JSON.parse(readFileSync(new URL(`../src/mocks/data/schemes/${name}.json`, import.meta.url), 'utf8'))
    return buildingModel(scheme.params)
  })
  assert.deepEqual(models.map(m => m.facade), ['wall','wall','modular','hybrid','frame'])
  assert.deepEqual(models.map(m => m.cantilever), [true,false,false,false,true])
  assert.equal(new Set(models.map(m => JSON.stringify([m.facade,m.cantilever,m.glazing,m.bays,m.volumes]))).size, 5)
})

test('未录入或非法窗墙比不补造开窗参数；分格数保持上限', () => {
  const model = buildingModel({ buildings: 4, floors: 16, units: 100000, window_wall_ratio: { 南: NaN, 北: 1.2, 东: 0, 西: .3 } })
  assert.deepEqual(model.glazing, { 南: null, 北: null, 东: 0, 西: .3 })
  assert.equal(model.bays, 8)
  assert.equal(model.cantilever, false)
  assert.equal(model.facade, 'neutral')
})
