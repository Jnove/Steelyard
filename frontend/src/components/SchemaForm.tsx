import { useState } from 'react'
import { errorMessages, orderedFields, fieldType, normalizeRequiredOptions, schemaInitialParams, schemaSubmitParams, validateSchemaField } from '../utils/schema-form'
export * from '../utils/schema-form'

import { Alert, Button, Checkbox, Collapse, Form, Input, InputNumber, Select, Space, Tag, Tooltip } from 'antd'
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

export function RequestErrors({ error, title = '操作未完成' }: { error: unknown; title?: string }) {
  const messages = errorMessages(error)
  if (!messages.length) return null
  return <Alert type="error" showIcon message={title} description={<ul>{messages.map((message, index) => <li key={index}>{message}</li>)}</ul>} />
}

function RequiredOptionsListInput({ field, options, value, onChange }: {
  field: FieldMetadata; options: { label: string; value: string }[];
  value?: string[] | null; onChange?: (value: string[]) => void;
}) {
  const required = field.required_options ?? []
  return <Select mode="multiple" style={{ width: '100%' }}
    value={normalizeRequiredOptions(field, value) as string[]}
    options={options.map(option => ({ ...option, disabled: required.includes(option.value) }))}
    placeholder="选择适用的地方标准册"
    onChange={onChange}
    tagRender={({ label, value: option, closable, onClose }) => <Tag
      closable={closable && !required.includes(String(option))}
      onClose={onClose} style={{ marginInlineEnd: 4 }}
      onMouseDown={event => { event.preventDefault(); event.stopPropagation() }}>
      {label}{required.includes(String(option)) ? '（始终生效）' : ''}
    </Tag>} />
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
  const labels = !Array.isArray(field.options) ? field.options : undefined
  const options = source.flatMap((option) => {
    if (option === null) return []
    if (typeof option === 'object') return [option]
    return [{ label: labels?.[String(option)] ?? String(option), value: typeof option === 'boolean' ? String(option) : option }]
  })
  if (type === 'boolean') return <Select allowClear options={[{ label: '是', value: 'true' }, { label: '否', value: 'false' }]} placeholder="请选择" />
  if (type.startsWith('array') && field.required_options?.length) return <RequiredOptionsListInput field={field}
    options={options.map(option => ({ label: String(option.label), value: String(option.value) }))} />
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
  const initialParams = schemaInitialParams(schema, initialValues?.params)

  return (
    <Form<SchemaFormValues>
      form={form}
      layout="vertical"
      scrollToFirstError
      disabled={pending}
      initialValues={{ name: initialValues?.name ?? '', params: initialParams }}
      onFinish={(values) => onSubmit({ name: values.name.trim(), params: schemaSubmitParams(schema, values.params, initialValues?.params) })}
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
              normalize={field.required_options?.length ? value => normalizeRequiredOptions(field, value) : undefined}
              extra={field.required_options?.length ? '标记“始终生效”的标准册不可关闭；地方标准仅在选择后参与评估。' : fieldType(field).startsWith('object') ? `填写 JSON 对象${field.unit && field.unit !== '—' ? `，数值单位：${field.unit}` : ''}${field.required ? '。' : '；可留空。'}` : undefined}
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
