import assert from 'node:assert/strict'
import { test } from 'node:test'
import { errorMessages, orderedFields, parseSchemaValue, validateSchemaField } from '../src/components/SchemaForm'
import type { FieldMetadata } from '../src/api/types'

const field = (type: string, overrides: Partial<FieldMetadata> = {}): FieldMetadata => ({
  name: 'value', label: '测试参数', description: '', unit: '', group: '基本信息',
  type, required: false, constraints: {}, ...overrides,
})

test('可选对象允许留空或 null，但拒绝数组、字符串与单个数字', () => {
  const metadata = field('object<number>')
  for (const value of [undefined, null, '', '  ', 'null', '{}']) {
    assert.deepEqual(validateSchemaField(metadata, value), [], String(value))
  }
  for (const value of ['[]', '[1]', '""', '"  "', '"文本"', '42', 'true', '{错误']) {
    assert.ok(validateSchemaField(metadata, value).length > 0, value)
  }
  assert.equal(parseSchemaValue(metadata, ''), null)
  assert.deepEqual(parseSchemaValue(metadata, '{"南":0.4,"北":0}'), { 南: 0.4, 北: 0 })
})

test('对象逐项验证数字类型，保留全部错误，不把数字字符串或布尔值当数字', () => {
  assert.equal(validateSchemaField(field('object<integer>'), '{"甲":1.5,"乙":"2","丙":true}').length, 3)
  assert.deepEqual(validateSchemaField(field('object<integer>'), '{"甲":0,"乙":120}'), [])
  assert.ok(validateSchemaField(field('object<number>'), '{"甲":1e400}').length > 0)
})

test('必填字段拒绝空值，但允许合法的零和 false', () => {
  for (const type of ['number', 'integer', 'string', 'object<number>', 'array<string>', 'boolean']) {
    for (const value of [null, undefined, '']) assert.ok(validateSchemaField(field(type, { required: true }), value).length > 0)
  }
  assert.deepEqual(validateSchemaField(field('integer', { required: true }), 0), [])
  assert.deepEqual(validateSchemaField(field('boolean', { required: true }), 'false'), [])
  assert.equal(parseSchemaValue(field('boolean'), 'false'), false)
})

test('数值约束保留边界语义，整数拒绝小数及非有限数字', () => {
  const closed = field('number', { constraints: { minimum: 0, maximum: 1 } })
  for (const value of [0, 0.82, 1]) assert.deepEqual(validateSchemaField(closed, value), [])
  for (const value of [-0.01, 1.01, NaN, Infinity, 'abc']) assert.ok(validateSchemaField(closed, value).length > 0)
  const open = field('number', { constraints: { exclusiveMinimum: 0, exclusiveMaximum: 1 } })
  for (const value of [0, 1]) assert.ok(validateSchemaField(open, value).length > 0)
  assert.deepEqual(validateSchemaField(open, 0.5), [])
  for (const value of [1.5, Infinity, Number.MAX_SAFE_INTEGER + 1]) assert.ok(validateSchemaField(field('integer'), value).length > 0)
})

test('枚举限制取值，自由标签保留自定义项，数字数组转换并验证元素', () => {
  const enumeration = field('string', { enum: ['剪力墙', '框架'] })
  assert.deepEqual(validateSchemaField(enumeration, '框架'), [])
  assert.ok(validateSchemaField(enumeration, '其他').length > 0)
  const tags = field('array<string>', { options: ['大悬挑'] })
  assert.deepEqual(validateSchemaField(tags, ['大悬挑', '自定义风险']), [])
  assert.deepEqual(parseSchemaValue(tags, [' 自定义风险 ']), ['自定义风险'])
  assert.deepEqual(parseSchemaValue(tags, undefined), [])
  assert.ok(validateSchemaField(tags, ['  ']).length > 0)
  assert.deepEqual(parseSchemaValue(field('array<integer>'), ['2', '3']), [2, 3])
  assert.ok(validateSchemaField(field('array<integer>'), ['2.5']).length > 0)
  assert.ok(validateSchemaField(field('array<string>', { enum: ['甲'] }), ['乙']).length > 0)
})

test('字符串长度和 nullable 类型仍执行约束', () => {
  const metadata = field('string', { constraints: { minLength: 2, maxLength: 4 } })
  assert.ok(validateSchemaField(metadata, '甲').length > 0)
  assert.deepEqual(validateSchemaField(metadata, '甲乙丙'), [])
  assert.ok(validateSchemaField(metadata, '甲乙丙丁戊').length > 0)
  const nullable = field('number | null', { constraints: { minimum: 0 } })
  assert.deepEqual(validateSchemaField(nullable, null), [])
  assert.ok(validateSchemaField(nullable, -1).length > 0)
})

test('字段按 schema 分组排序，未知分组和无分组字段不丢失', () => {
  const fields = [field('string', { name: '甲', group: '新分组' }), field('number', { name: '乙', group: '基本信息' }), field('string', { name: '丙', group: '' })]
  assert.deepEqual(orderedFields({ title: '', description: '', group_order: ['基本信息', '空分组'], fields }).map(item => item.name), ['乙', '甲', '丙'])
})

test('导入错误逐条保留方案和字段，兼容嵌套422及普通网络错误', () => {
  const error = Object.assign(new Error('HTTP 422'), { body: { detail: { errors: [
    { scheme: '甲', label: '总户数', message: '必须为整数' },
    { scheme: '乙', field: 'gfa', message: '必须大于零' },
    { label: '用地面积', message: '缺少数据' },
  ] } } })
  assert.deepEqual(errorMessages(error), ['甲 · 总户数：必须为整数', '乙 · gfa：必须大于零', '用地面积：缺少数据'])
  assert.deepEqual(errorMessages({ detail: [{ loc: ['body', 'params', 'units'], msg: '数值错误' }] }), ['params · units：数值错误'])
  assert.deepEqual(errorMessages(new Error('连接中断')), ['连接中断'])
  for (const value of [null, undefined, []]) assert.deepEqual(errorMessages(value), [])
})
