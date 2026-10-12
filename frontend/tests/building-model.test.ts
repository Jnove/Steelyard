import assert from 'node:assert/strict'
import { test } from 'node:test'
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
