import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import SchemaForm, { errorMessages, normalizeRequiredOptions, orderedFields, parseSchemaValue, recordedSchemaFields, schemaFieldValue, schemaInitialParams, schemaSubmitParams, validateSchemaField } from '../src/components/SchemaForm'
import type { FieldMetadata, FieldSchema } from '../src/api/types'

const field = (type: string, overrides: Partial<FieldMetadata> = {}): FieldMetadata => ({
  name: 'value', label: '测试参数', description: '', unit: '', group: '基本信息',
  type, required: false, constraints: {}, ...overrides,
})

const standards = field('array<string> | null', {
  name: 'standard_packs', label: '适用标准册', empty_means_unknown: true,
  allow_custom_options: false, required_options: ['GB'],
  options: [{ value: 'GB', label: '国家标准' }, { value: 'ZJ', label: '浙江省地方标准' }],
})

test('默认标准册空值提交 null，已有国标或地方组合保持原样', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [standards] }
  for (const value of [undefined, null, '', []]) {
    assert.deepEqual(schemaSubmitParams(schema, { standard_packs: value }), { standard_packs: null })
    assert.deepEqual(validateSchemaField(standards, value), [])
  }
  for (const value of [['GB'], ['GB', 'ZJ']]) {
    const original = { standard_packs: value }
    assert.deepEqual(schemaSubmitParams(schema, schemaInitialParams(schema, original), original), original)
    assert.deepEqual(validateSchemaField(standards, value), [])
  }
  assert.deepEqual(parseSchemaValue(standards, ['ZJ']), ['ZJ'])
  assert.ok(validateSchemaField(standards, ['ZJ']).some(message => message.includes('GB')))
  assert.ok(validateSchemaField(standards, ['GB', 'ZZ']).length > 0)
})

test('标准册控件规范化显示锁定国标，移除地方册不会移除国标，其他清单不受影响', () => {
  assert.deepEqual(normalizeRequiredOptions(standards, null), ['GB'])
  assert.deepEqual(normalizeRequiredOptions(standards, ['ZJ']), ['GB', 'ZJ'])
  assert.deepEqual(normalizeRequiredOptions(standards, ['GB', 'ZJ']), ['GB', 'ZJ'])
  assert.deepEqual(normalizeRequiredOptions(standards, []), ['GB'])
  assert.deepEqual(normalizeRequiredOptions(standards, ['ZJ', 'GB', 'ZJ']), ['GB', 'ZJ'])
  const irregularity = field('array<string>', { empty_means_unknown: true })
  assert.deepEqual(normalizeRequiredOptions(irregularity, []), [])
  assert.equal(normalizeRequiredOptions(irregularity, null), null)
  assert.deepEqual(parseSchemaValue(irregularity, []), [])
})

test('标准册表单初始界面显示国标且没有删除按钮，已有地方册可以删除', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [standards] }
  const render = (params?: object) => renderToStaticMarkup(createElement(SchemaForm, {
    schema, nameLabel: '项目名称', initialValues: params ? { name: '测试项目', params } : undefined,
    onSubmit: () => {}, onCancel: () => {},
  }))
  const empty = render()
  assert.ok(empty.includes('国家标准') && empty.includes('始终生效'))
  assert.equal(empty.includes('ant-tag-close-icon'), false)
  const regional = render({ standard_packs: ['GB', 'ZJ'] })
  assert.ok(regional.includes('浙江省地方标准'))
  assert.equal((regional.match(/ant-tag-close-icon/g) ?? []).length, 1)
})

test('隐藏字段不显示，编辑保存保留已有值，不从可见表单输入覆盖', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [
    field('number', { name: 'floors' }), field('string', { name: 'source_id', hidden: true }),
  ] }
  const original = { floors: 16, source_id: 'verified-case' }
  assert.deepEqual(orderedFields(schema).map(item => item.name), ['floors'])
  assert.deepEqual(schemaInitialParams(schema, original), { floors: 16 })
  assert.deepEqual(schemaSubmitParams(schema, { floors: 18, source_id: 'changed' }, original), { floors: 18, source_id: 'verified-case' })
  assert.deepEqual(schemaSubmitParams(schema, { floors: 18 }), { floors: 18 })
})

test('声明式清单区分未核对和已核对无不规则项', () => {
  const metadata = field('array<string>', { empty_means_unknown: true, allow_custom_options: false })
  assert.equal(parseSchemaValue(metadata, undefined), null)
  assert.equal(parseSchemaValue(metadata, ''), null)
  assert.deepEqual(parseSchemaValue(metadata, []), [])
  assert.deepEqual(parseSchemaValue(metadata, ['扭转不规则']), ['扭转不规则'])
  assert.deepEqual(parseSchemaValue(field('array<string>'), ''), [])
})

test('已核定清单拒绝拼写错误，自由风险标签仍允许扩展', () => {
  const metadata = field('array<string>', { allow_custom_options: false, options: ['扭转不规则'] })
  assert.deepEqual(validateSchemaField(metadata, ['扭转不规则']), [])
  assert.ok(validateSchemaField(metadata, ['扭转不规侧']).length > 0)
  assert.deepEqual(validateSchemaField(field('array<string>', { options: ['大悬挑'] }), ['其他风险']), [])
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

test('自定义字段从嵌套容器初始化，提交保留未知键并避免写到方案顶层', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [
    field('number', { name: 'floors' }),
    field('object', { name: 'custom' }),
    field('number | null', { name: 'regional_ratio', custom: true }),
    field('array<string> | null', { name: 'regional_notes', custom: true }),
  ] }
  const original = { floors: 16, custom: { regional_ratio: 0, regional_notes: null, removed_field: 12, unknown_list: ['甲'], unknown_null: null } }
  assert.deepEqual(orderedFields(schema).map(item => item.name), ['floors', 'regional_ratio', 'regional_notes'])
  const initial = schemaInitialParams(schema, original)
  assert.deepEqual(initial, { floors: 16, regional_ratio: 0, regional_notes: undefined })
  const payload = schemaSubmitParams(schema, { ...initial, floors: 18 }, original)
  assert.deepEqual(payload, { floors: 18, custom: { ...original.custom } })
  assert.equal(Object.hasOwn(payload, 'regional_ratio'), false)
  assert.equal(schemaFieldValue(payload, schema.fields[2]), 0)
  assert.equal(recordedSchemaFields(schema, payload), 2)
  assert.deepEqual(original.custom, { regional_ratio: 0, regional_notes: null, removed_field: 12, unknown_list: ['甲'], unknown_null: null })
})

test('自定义清单保留未填写与明确空清单的区别，清空数值不会恢复旧值', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [
    field('number | null', { name: 'regional_ratio', custom: true }),
    field('array<string> | null', { name: 'regional_notes', custom: true }),
  ] }
  for (const value of [null, [], ['甲']]) {
    const original = { custom: { regional_ratio: 0, regional_notes: value } }
    assert.deepEqual(schemaSubmitParams(schema, schemaInitialParams(schema, original), original), original)
  }
  assert.deepEqual(schemaSubmitParams(schema, { regional_ratio: undefined, regional_notes: undefined }, { custom: { regional_ratio: 0, regional_notes: ['甲'] } }), {
    custom: { regional_ratio: null, regional_notes: null },
  })
  assert.deepEqual(schemaSubmitParams(schema, { regional_ratio: 0, regional_notes: [' 乙 '] }), { custom: { regional_ratio: 0, regional_notes: ['乙'] } })
})

test('普通字段保持平铺载荷，编辑时没有定义的自定义数据仍被保留', () => {
  const schema: FieldSchema = { title: '', description: '', group_order: [], fields: [
    field('number', { name: 'floors' }), field('object', { name: 'custom' }),
  ] }
  assert.deepEqual(schemaSubmitParams(schema, { floors: 12 }), { floors: 12 })
  assert.deepEqual(schemaSubmitParams(schema, { floors: 12 }, { floors: 10, custom: { deleted_field: 0 } }), { floors: 12, custom: { deleted_field: 0 } })
  const numeric = field('number', { name: 'shared', custom: true })
  assert.equal(schemaFieldValue({ shared: 99, custom: { shared: 0 } }, numeric), 0)
  assert.equal(schemaFieldValue({ shared: 99 }, numeric), undefined)
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
