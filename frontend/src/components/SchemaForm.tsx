import { useState } from 'react'
import { Alert, Button, Checkbox, Collapse, Form, Input, InputNumber, Select, Space, Tooltip } from 'antd'
import type { FieldMetadata, FieldSchema } from '../api/types'

export interface SchemaFormValues {
  name: string
  params: Record<string, unknown>
}

interface SchemaFormProps {
  schema: FieldSchema
  nameLabel: string
  initialValues?: { name: string; params: object }
  pending?: boolean
  error?: unknown
  onSubmit: (values: SchemaFormValues) => void
  onCancel: () => void
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 保留服务端返回的全部校验或导入错误，以及对应的方案和字段。 */
export function errorMessages(error: unknown): string[] {
  if (error == null) return []
  if (typeof error === 'string') return [error]
  if (Array.isArray(error)) return error.flatMap(errorMessages)
  if (isRecord(error)) {
    for (const key of ['body', 'detail', 'errors', 'data']) {
      if (error[key] != null) {
        const messages = errorMessages(error[key])
        if (messages.length) return messages
      }
    }
    const message = error.message ?? error.msg
    if (typeof message === 'string') {
      const location = Array.isArray(error.loc)
        ? error.loc.filter((part) => part !== 'body').join(' · ')
        : undefined
      const context = [error.scheme, error.label ?? error.field, location]
        .filter((part) => typeof part === 'string' && part.length > 0)
        .join(' · ')
      return [context ? `${context}：${message}` : message]
    }
  }
  return ['操作未完成，请稍后重试。']
}

export function RequestErrors({ error, title = '操作未完成' }: { error: unknown; title?: string }) {
  const messages = errorMessages(error)
  if (!messages.length) return null
  return <Alert type="error" showIcon message={title} description={<ul>{messages.map((message, index) => <li key={index}>{message}</li>)}</ul>} />
}

export function orderedFields(schema: FieldSchema): FieldMetadata[] {
  const groups = [...new Set([
    ...(schema.group_order ?? []),
    ...schema.fields.map((field) => field.group || '其他参数'),
  ])]
  return groups.flatMap((group) => schema.fields.filter((field) => (field.group || '其他参数') === group))
}

function fieldType(field: FieldMetadata): string {
  return field.type.replace(/\s/g, '').replace(/\|null|null\|/g, '')
}

function isEmpty(value: unknown): boolean {
  return value == null || (typeof value === 'string' && value.trim() === '')
}

export function parseSchemaValue(field: FieldMetadata, value: unknown): unknown {
  const type = fieldType(field)
  if (isEmpty(value)) return type.startsWith('array') && !field.empty_means_unknown ? [] : null
  if (type.startsWith('object') && typeof value === 'string') return JSON.parse(value) as unknown
  if (type === 'boolean' && typeof value === 'string') return value === 'true'
  if (type.startsWith('array') && Array.isArray(value)) {
    return value.map((item: unknown) => {
      if (type.includes('<number>') || type.includes('<integer>')) {
        return typeof item === 'string' && item.trim() ? Number(item) : item
      }
      return typeof item === 'string' ? item.trim() : item
    })
  }
  return value
}

function numericErrors(value: number, constraints: Record<string, unknown>): string[] {
  const errors: string[] = []
  const { minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf } = constraints
  if (typeof minimum === 'number' && value < minimum) errors.push(`不能小于 ${minimum}`)
  if (typeof maximum === 'number' && value > maximum) errors.push(`不能大于 ${maximum}`)
  if (typeof exclusiveMinimum === 'number' && value <= exclusiveMinimum) errors.push(`必须大于 ${exclusiveMinimum}`)
  if (typeof exclusiveMaximum === 'number' && value >= exclusiveMaximum) errors.push(`必须小于 ${exclusiveMaximum}`)
  if (typeof multipleOf === 'number' && multipleOf > 0) {
    const quotient = value / multipleOf
    if (Math.abs(quotient - Math.round(quotient)) > 1e-9) errors.push(`必须是 ${multipleOf} 的倍数`)
  }
  return errors
}

function matchesType(value: unknown, type: string): boolean {
  if (type === 'integer') return typeof value === 'number' && Number.isSafeInteger(value)
  if (type === 'number') return typeof value === 'number' && Number.isFinite(value)
  if (type === 'string') return typeof value === 'string'
  if (type === 'boolean') return typeof value === 'boolean'
  return true
}

export function validateSchemaField(field: FieldMetadata, raw: unknown): string[] {
  let value: unknown
  try {
    value = parseSchemaValue(field, raw)
  } catch {
    return ['请输入有效的 JSON 对象，例如 {"南": 0.4}；键名须使用双引号。']
  }
  const type = fieldType(field)
  if (value == null || (!type.startsWith('object') && isEmpty(value)) || (type.startsWith('array') && Array.isArray(value) && value.length === 0)) {
    return field.required ? [`请填写${field.label}`] : []
  }
  const constraints: Record<string, unknown> = field.constraints ?? {}
  const errors: string[] = []
  if (type === 'number' || type === 'integer') {
    if (!matchesType(value, type)) return [type === 'integer' ? '请输入有效的整数' : '请输入有效的数字']
    errors.push(...numericErrors(value as number, constraints))
  } else if (type.startsWith('object')) {
    if (!isRecord(value)) return ['请输入 JSON 对象，不能使用数组、字符串或单个数字。']
    const itemType = type.match(/<(.+)>/)?.[1]
    if (itemType) {
      for (const [key, item] of Object.entries(value)) {
        if (!matchesType(item, itemType)) errors.push(`“${key}”的值必须为${itemType === 'integer' ? '整数' : itemType === 'number' ? '有效数字' : itemType === 'boolean' ? '布尔值' : '字符串'}`)
      }
    }
  } else if (type.startsWith('array')) {
    if (!Array.isArray(value)) return ['请选择或输入列表项']
    const itemType = type.match(/<(.+)>/)?.[1] ?? 'string'
    if (value.some((item: unknown) => !matchesType(item, itemType) || isEmpty(item))) errors.push('列表包含空白项或类型不正确的值')
    if (typeof constraints.minItems === 'number' && value.length < constraints.minItems) errors.push(`至少选择 ${constraints.minItems} 项`)
    if (typeof constraints.maxItems === 'number' && value.length > constraints.maxItems) errors.push(`最多选择 ${constraints.maxItems} 项`)
    if (field.enum && value.some((item: unknown) => !field.enum?.some((option) => option === item))) errors.push('请选择列表中的有效选项')
    const allowedOptions = field.options
    if (field.allow_custom_options === false && Array.isArray(allowedOptions)
      && value.some((item: unknown) => !allowedOptions.some(option => (typeof option === 'string' ? option : option.value) === item))) errors.push('请选择已核定的列表选项')
  } else if (!matchesType(value, type)) errors.push('输入值的类型不正确')
  if (!type.startsWith('array') && field.enum && !field.enum.some((option) => option === value)) errors.push('请选择列表中的有效选项')
  if (typeof value === 'string') {
    if (typeof constraints.minLength === 'number' && value.length < constraints.minLength) errors.push(`至少输入 ${constraints.minLength} 个字符`)
    if (typeof constraints.maxLength === 'number' && value.length > constraints.maxLength) errors.push(`最多输入 ${constraints.maxLength} 个字符`)
  }
  return errors
}

function DeclaredListInput({ value, onChange, options }: {
  value?: string[] | null; onChange?: (value: string[] | null) => void;
  options: { label: string; value: string }[];
}) {
  return <Space direction="vertical" style={{ width: '100%' }}>
    <Select mode="multiple" allowClear style={{ width: '100%' }} options={options}
      value={value ?? undefined} placeholder="未核对；核对后选择不规则项"
      onChange={(items: string[]) => onChange?.(items.length ? items : null)} />
    <Checkbox checked={Array.isArray(value) && value.length === 0}
      onChange={(event) => onChange?.(event.target.checked ? [] : null)}>已核对，无不规则项</Checkbox>
  </Space>
}

function renderInput(field: FieldMetadata) {
  const type = fieldType(field)
  const unit = field.unit && field.unit !== '—' ? field.unit : undefined
  const source = field.enum ?? (Array.isArray(field.options) ? field.options : Object.entries(field.options ?? {}).map(([value, label]) => ({ value, label })))
  const options = source.flatMap((option) => {
    if (option === null) return []
    if (typeof option === 'object') return [option]
    return [{ label: String(option), value: typeof option === 'boolean' ? String(option) : option }]
  })
  if (type === 'boolean') return <Select allowClear options={[{ label: '是', value: 'true' }, { label: '否', value: 'false' }]} placeholder="请选择" />
  if (type.startsWith('array') && field.empty_means_unknown) return <DeclaredListInput options={options.map(option => ({ label: String(option.label), value: String(option.value) }))} />
  if (type.startsWith('array')) return <Select mode={field.enum || field.allow_custom_options === false ? 'multiple' : 'tags'} allowClear options={options} placeholder={field.allow_custom_options === false ? '请选择已核定的预设项' : '选择预设项，或输入后按回车添加'} />
  if (field.enum || field.options) return <Select allowClear showSearch optionFilterProp="label" options={options} placeholder="请选择" />
  if (type === 'number' || type === 'integer') return <InputNumber style={{ width: '100%' }} addonAfter={unit} step={type === 'integer' ? 1 : 0.01} placeholder="未填写" />
  if (type.startsWith('object')) return <Input.TextArea autoSize={{ minRows: 3, maxRows: 8 }} placeholder={type.includes('integer') ? '{"两居室": 80, "三居室": 40}' : '{"南": 0.4, "北": 0.3}'} />
  return <Input allowClear addonAfter={unit} placeholder="未填写" />
}

export default function SchemaForm({ schema, nameLabel, initialValues, pending = false, error, onSubmit, onCancel }: SchemaFormProps) {
  const [form] = Form.useForm<SchemaFormValues>()
  const fields = orderedFields(schema)
  const groups = [...new Set(fields.map((field) => field.group || '其他参数'))]
  const [activeGroups, setActiveGroups] = useState<string[]>(groups)
  const initialParams = Object.fromEntries(fields.map((field) => {
    const value: unknown = initialValues ? Reflect.get(initialValues.params, field.name) : undefined
    const type = fieldType(field)
    return [field.name, type.startsWith('object') && value != null ? JSON.stringify(value, null, 2) : type === 'boolean' && value != null ? String(value) : value ?? undefined]
  }))

  return (
    <Form<SchemaFormValues>
      form={form}
      layout="vertical"
      disabled={pending}
      initialValues={{ name: initialValues?.name ?? '', params: initialParams }}
      onFinish={(values) => onSubmit({ name: values.name.trim(), params: Object.fromEntries(fields.map((field) => [field.name, parseSchemaValue(field, values.params?.[field.name])])) })}
      onFinishFailed={() => setActiveGroups(groups)}
    >
      <RequestErrors error={error} title="保存失败，请检查以下问题" />
      <Form.Item name="name" label={nameLabel} rules={[{ required: true, whitespace: true, message: `请输入${nameLabel}` }, { max: 200, message: '名称不能超过 200 个字符' }]}>
        <Input autoFocus allowClear placeholder={`为${nameLabel.replace('名称', '')}起一个便于识别的名字`} />
      </Form.Item>
      <p className="muted">参数可按已知信息填写，留空表示暂无数据。比例请填 0–1 的小数，例如 0.82。</p>
      <Collapse
        activeKey={activeGroups}
        onChange={(keys) => setActiveGroups(typeof keys === 'string' ? [keys] : keys)}
        items={groups.map((group) => ({
          key: group,
          label: group,
          forceRender: true,
          children: <div className="schema-grid">{fields.filter((field) => (field.group || '其他参数') === group).map((field) => (
            <Form.Item
              key={field.name}
              name={['params', field.name]}
              label={<Space size={4}>{field.label}{field.description && <Tooltip title={field.description}><span tabIndex={0} aria-label={`${field.label}说明`}>ⓘ</span></Tooltip>}</Space>}
              required={field.required}
              extra={fieldType(field).startsWith('object') ? `填写 JSON 对象${field.unit && field.unit !== '—' ? `，数值单位：${field.unit}` : ''}${field.required ? '。' : '；可留空。'}` : undefined}
              rules={[{ validator: async (_, raw: unknown) => {
                const errors = validateSchemaField(field, raw)
                if (errors.length) throw new Error(errors.join('；'))
              } }]}
            >
              {renderInput(field)}
            </Form.Item>
          ))}</div>,
        }))}
      />
      <div className="action-row">
        <Button onClick={onCancel} disabled={pending}>取消</Button>
        <Button type="primary" htmlType="submit" loading={pending}>保存{nameLabel.replace('名称', '')}</Button>
      </div>
    </Form>
  )
}
