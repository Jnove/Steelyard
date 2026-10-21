import type { FieldMetadata, FieldSchema } from '../api/types'

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

export function orderedFields(schema: FieldSchema): FieldMetadata[] {
  // custom 是存储容器；运行期 schema 已把其中的字段展开成独立输入项。
  const fields = schema.fields.filter(
    (field) => field.name !== 'custom' && !field.hidden,
  )
  const groups = [
    ...new Set([
      ...(schema.group_order ?? []),
      ...fields.map((field) => field.group || '其他参数'),
    ]),
  ]
  return groups.flatMap((group) =>
    fields.filter((field) => (field.group || '其他参数') === group),
  )
}

/** 显示用的 schema 是平铺字段，方案里的自定义参数仍保存在 custom 内。 */
export function schemaFieldValue(
  params: object,
  field: FieldMetadata,
): unknown {
  const custom: unknown = Reflect.get(params, 'custom')
  return field.custom
    ? isRecord(custom)
      ? custom[field.name]
      : undefined
    : Reflect.get(params, field.name)
}

export function schemaInitialParams(
  schema: FieldSchema,
  params?: object,
): Record<string, unknown> {
  return Object.fromEntries(
    orderedFields(schema).map((field) => {
      const value = params ? schemaFieldValue(params, field) : undefined
      const type = fieldType(field)
      return [
        field.name,
        type.startsWith('object') && value != null
          ? JSON.stringify(value, null, 2)
          : type === 'boolean' && value != null
            ? String(value)
            : (value ?? undefined),
      ]
    }),
  )
}

export function schemaSubmitParams(
  schema: FieldSchema,
  raw: Record<string, unknown> = {},
  original?: object,
): Record<string, unknown> {
  const fields = orderedFields(schema)
  const previous: unknown = original
    ? Reflect.get(original, 'custom')
    : undefined
  const custom = Object.fromEntries([
    ...Object.entries(isRecord(previous) ? previous : {}),
    ...fields
      .filter((field) => field.custom)
      .map((field) => [field.name, parseSchemaValue(field, raw[field.name])]),
  ])
  const hidden = original
    ? schema.fields
        .filter(
          (field) => field.hidden && !field.custom && field.name !== 'custom',
        )
        .flatMap((field) => {
          const value = schemaFieldValue(original, field)
          return value === undefined ? [] : [[field.name, value] as const]
        })
    : []
  const builtin = Object.fromEntries([
    ...hidden,
    ...fields
      .filter((field) => !field.custom)
      .map((field) => [field.name, parseSchemaValue(field, raw[field.name])]),
  ])
  // 编辑时保留已删除定义或暂未返回定义的值；添加普通方案无需凭空添加容器。
  return fields.some((field) => field.custom) || isRecord(previous)
    ? { ...builtin, custom }
    : builtin
}

export function recordedSchemaFields(
  schema: FieldSchema,
  params: object,
): number {
  return orderedFields(schema).filter((field) => {
    const value = schemaFieldValue(params, field)
    return (
      value != null &&
      value !== '' &&
      (typeof value !== 'object' || Object.keys(value).length > 0)
    )
  }).length
}

export function fieldType(field: FieldMetadata): string {
  return field.type.replace(/\s/g, '').replace(/\|null|null\|/g, '')
}

function isEmpty(value: unknown): boolean {
  return value == null || (typeof value === 'string' && value.trim() === '')
}

export function parseSchemaValue(
  field: FieldMetadata,
  value: unknown,
): unknown {
  const type = fieldType(field)
  if (isEmpty(value))
    return type.startsWith('array') &&
      !field.custom &&
      !field.empty_means_unknown &&
      !field.required_options?.length
      ? []
      : null
  if (type.startsWith('object') && typeof value === 'string')
    return JSON.parse(value) as unknown
  if (type === 'boolean' && typeof value === 'string') return value === 'true'
  if (type.startsWith('array') && Array.isArray(value)) {
    // 标准册空清单采用默认册；不影响不规则项明确 [] 的“已核对”语义。
    if (field.required_options?.length && value.length === 0) return null
    return value.map((item: unknown) => {
      if (type.includes('<number>') || type.includes('<integer>')) {
        return typeof item === 'string' && item.trim() ? Number(item) : item
      }
      return typeof item === 'string' ? item.trim() : item
    })
  }
  return value
}

/** 用于选择控件及 Form normalize：必选项始终在界面上显示，不能被移除。 */
export function normalizeRequiredOptions(
  field: FieldMetadata,
  value: unknown,
): unknown {
  if (!field.required_options?.length || !fieldType(field).startsWith('array'))
    return value
  return [
    ...new Set([
      ...field.required_options,
      ...(Array.isArray(value) ? value : []),
    ]),
  ]
}

function numericErrors(
  value: number,
  constraints: Record<string, unknown>,
): string[] {
  const errors: string[] = []
  const { minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf } =
    constraints
  if (typeof minimum === 'number' && value < minimum)
    errors.push(`不能小于 ${minimum}`)
  if (typeof maximum === 'number' && value > maximum)
    errors.push(`不能大于 ${maximum}`)
  if (typeof exclusiveMinimum === 'number' && value <= exclusiveMinimum)
    errors.push(`必须大于 ${exclusiveMinimum}`)
  if (typeof exclusiveMaximum === 'number' && value >= exclusiveMaximum)
    errors.push(`必须小于 ${exclusiveMaximum}`)
  if (typeof multipleOf === 'number' && multipleOf > 0) {
    const quotient = value / multipleOf
    if (Math.abs(quotient - Math.round(quotient)) > 1e-9)
      errors.push(`必须是 ${multipleOf} 的倍数`)
  }
  return errors
}

function matchesType(value: unknown, type: string): boolean {
  if (type === 'integer')
    return typeof value === 'number' && Number.isSafeInteger(value)
  if (type === 'number')
    return typeof value === 'number' && Number.isFinite(value)
  if (type === 'string') return typeof value === 'string'
  if (type === 'boolean') return typeof value === 'boolean'
  return true
}

export function validateSchemaField(
  field: FieldMetadata,
  raw: unknown,
): string[] {
  let value: unknown
  try {
    value = parseSchemaValue(field, raw)
  } catch {
    return ['请输入有效的 JSON 对象，例如 {"南": 0.4}；键名须使用双引号。']
  }
  const type = fieldType(field)
  if (
    value == null ||
    (!type.startsWith('object') && isEmpty(value)) ||
    (type.startsWith('array') && Array.isArray(value) && value.length === 0)
  ) {
    return field.required ? [`请填写${field.label}`] : []
  }
  const constraints: Record<string, unknown> = field.constraints ?? {}
  const errors: string[] = []
  if (type === 'number' || type === 'integer') {
    if (!matchesType(value, type))
      return [type === 'integer' ? '请输入有效的整数' : '请输入有效的数字']
    errors.push(...numericErrors(value as number, constraints))
  } else if (type.startsWith('object')) {
    if (!isRecord(value))
      return ['请输入 JSON 对象，不能使用数组、字符串或单个数字。']
    const itemType = type.match(/<(.+)>/)?.[1]
    if (itemType) {
      for (const [key, item] of Object.entries(value)) {
        if (!matchesType(item, itemType))
          errors.push(
            `“${key}”的值必须为${itemType === 'integer' ? '整数' : itemType === 'number' ? '有效数字' : itemType === 'boolean' ? '布尔值' : '字符串'}`,
          )
      }
    }
  } else if (type.startsWith('array')) {
    if (!Array.isArray(value)) return ['请选择或输入列表项']
    const itemType = type.match(/<(.+)>/)?.[1] ?? 'string'
    if (
      value.some(
        (item: unknown) => !matchesType(item, itemType) || isEmpty(item),
      )
    )
      errors.push('列表包含空白项或类型不正确的值')
    if (
      typeof constraints.minItems === 'number' &&
      value.length < constraints.minItems
    )
      errors.push(`至少选择 ${constraints.minItems} 项`)
    if (
      typeof constraints.maxItems === 'number' &&
      value.length > constraints.maxItems
    )
      errors.push(`最多选择 ${constraints.maxItems} 项`)
    if (
      field.enum &&
      value.some(
        (item: unknown) => !field.enum?.some((option) => option === item),
      )
    )
      errors.push('请选择列表中的有效选项')
    for (const required of field.required_options ?? []) {
      if (!value.includes(required))
        errors.push(`必须保留 ${required}，该选项始终生效`)
    }
    const allowedOptions = field.options
    if (
      field.allow_custom_options === false &&
      Array.isArray(allowedOptions) &&
      value.some(
        (item: unknown) =>
          !allowedOptions.some(
            (option) =>
              (typeof option === 'string' ? option : option.value) === item,
          ),
      )
    )
      errors.push('请选择已核定的列表选项')
  } else if (!matchesType(value, type)) errors.push('输入值的类型不正确')
  if (
    !type.startsWith('array') &&
    field.enum &&
    !field.enum.some((option) => option === value)
  )
    errors.push('请选择列表中的有效选项')
  if (typeof value === 'string') {
    if (
      typeof constraints.minLength === 'number' &&
      value.length < constraints.minLength
    )
      errors.push(`至少输入 ${constraints.minLength} 个字符`)
    if (
      typeof constraints.maxLength === 'number' &&
      value.length > constraints.maxLength
    )
      errors.push(`最多输入 ${constraints.maxLength} 个字符`)
  }
  return errors
}
