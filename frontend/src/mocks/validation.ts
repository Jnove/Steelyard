import { ApiError } from '../api/client'

export interface JsonSchema {
  type?: string; properties?: Record<string, JsonSchema>; required?: string[]
  enum?: unknown[]; anyOf?: JsonSchema[]; items?: JsonSchema
  allow_custom_options?: boolean; options?: string[]
  additionalProperties?: JsonSchema | boolean
  minimum?: number; maximum?: number; exclusiveMinimum?: number; exclusiveMaximum?: number
  minLength?: number; maxLength?: number
}

/** 校验导出参数模型实际使用的 JSON Schema 子集。 */
export function validate(value: unknown, schema: JsonSchema, path = 'params'): void {
  const fail = (message: string): never => { throw new ApiError(422, { detail: `${path}: ${message}` }) }
  if (Array.isArray(value) && schema.allow_custom_options === false && schema.options
    && value.some(item => !schema.options!.includes(String(item)))) fail('请选择已核定的列表选项')
  if (schema.anyOf) {
    for (const variant of schema.anyOf) {
      try {
        validate(value, variant, path)
        // Pydantic 字段元信息可能把枚举放在可空联合之外；null 仍是合法默认值。
        if (value !== null && schema.enum && !schema.enum.includes(value)) fail('值不在允许的选项中')
        return
      } catch (error) { if (!(error instanceof ApiError)) throw error }
    }
    fail('值不符合允许的类型或范围')
  }
  if (schema.enum && !schema.enum.includes(value)) fail('值不在允许的选项中')
  if (schema.type === 'null' && value !== null) fail('应为 null')
  if (schema.type === 'number' || schema.type === 'integer') {
    if (typeof value !== 'number' || !Number.isFinite(value)) fail('必须是有限数字')
    const n = value as number
    if (schema.type === 'integer' && !Number.isInteger(n)) fail('必须是整数')
    if (schema.minimum !== undefined && n < schema.minimum) fail(`不得小于 ${schema.minimum}`)
    if (schema.maximum !== undefined && n > schema.maximum) fail(`不得大于 ${schema.maximum}`)
    if (schema.exclusiveMinimum !== undefined && n <= schema.exclusiveMinimum) fail(`必须大于 ${schema.exclusiveMinimum}`)
    if (schema.exclusiveMaximum !== undefined && n >= schema.exclusiveMaximum) fail(`必须小于 ${schema.exclusiveMaximum}`)
  }
  if (schema.type === 'string') {
    if (typeof value !== 'string') fail('必须是文本')
    const length = [...value as string].length
    if (schema.minLength !== undefined && length < schema.minLength) fail('文本过短')
    if (schema.maxLength !== undefined && length > schema.maxLength) fail('文本过长')
  }
  if (schema.type === 'boolean' && typeof value !== 'boolean') fail('必须是布尔值')
  if (schema.type === 'array') {
    if (!Array.isArray(value)) fail('必须是数组')
    if (schema.items) (value as unknown[]).forEach((item, i) => validate(item, schema.items!, `${path}[${i}]`))
  }
  if (schema.type === 'object') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) fail('必须是对象')
    const object = value as Record<string, unknown>
    for (const key of schema.required ?? []) if (!(key in object)) fail(`缺少 ${key}`)
    for (const [key, item] of Object.entries(object)) {
      if (schema.properties?.[key]) validate(item, schema.properties[key], `${path}.${key}`)
      else if (typeof schema.additionalProperties === 'object') validate(item, schema.additionalProperties, `${path}.${key}`)
      else if (schema.additionalProperties === false) fail(`未知字段 ${key}`)
    }
  }
}
