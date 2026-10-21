import { useId } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { LoaderCircle } from 'lucide-react'
import type { FieldMetadata, FieldSchema } from '../../api/types'
import type { SchemaFormValues } from '../SchemaForm'
import {
  errorMessages,
  fieldType,
  normalizeRequiredOptions,
  orderedFields,
  schemaInitialParams,
  schemaSubmitParams,
  validateSchemaField,
} from '../../utils/schema-form'
import { Button } from '../ui/button'
import { Input } from '../ui/input'

export function HomeErrors({
  error,
  title = '操作未完成',
}: {
  error: unknown
  title?: string
}) {
  const errors = errorMessages(error)
  return errors.length ? (
    <div className="home-error" role="alert">
      <strong>{title}</strong>
      <ul>
        {errors.map((message, i) => (
          <li key={i}>{message}</li>
        ))}
      </ul>
    </div>
  ) : null
}

function fieldOptions(field: FieldMetadata) {
  const labels =
    field.options && !Array.isArray(field.options) ? field.options : undefined
  const source =
    field.enum ??
    (Array.isArray(field.options)
      ? field.options
      : Object.entries(field.options ?? {}).map(([value, label]) => ({
          value,
          label,
        })))
  return source.flatMap((option) =>
    option === null
      ? []
      : typeof option === 'object'
        ? [option]
        : [
            {
              value: String(option),
              label: labels?.[String(option)] ?? String(option),
            },
          ],
  )
}

export default function ProjectForm({
  schema,
  initialValues,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  schema: FieldSchema
  initialValues?: { name: string; params: object }
  pending: boolean
  error: unknown
  onSubmit: (values: SchemaFormValues) => void
  onCancel: () => void
}) {
  const id = useId()
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<SchemaFormValues>({
    defaultValues: {
      name: initialValues?.name ?? '',
      params: schemaInitialParams(schema, initialValues?.params),
    },
  })
  const fields = orderedFields(schema)
  const groups = [...new Set(fields.map((field) => field.group || '其他参数'))]
  return (
    <form
      className="home-project-form"
      onSubmit={handleSubmit((values) =>
        onSubmit({
          name: values.name.trim(),
          params: schemaSubmitParams(
            schema,
            values.params,
            initialValues?.params,
          ),
        }),
      )}
    >
      <HomeErrors error={error} title="保存失败，请检查以下问题" />
      <fieldset disabled={pending}>
        <div className="home-field">
          <label htmlFor={`${id}-name`}>
            项目名称 <span aria-hidden="true">*</span>
          </label>
          <Input
            id={`${id}-name`}
            autoFocus
            placeholder="输入便于识别的项目名称"
            maxLength={200}
            aria-required="true"
            aria-invalid={!!errors.name}
            aria-describedby={errors.name ? `${id}-name-error` : undefined}
            {...register('name', {
              validate: (value) => value.trim().length > 0 || '请输入项目名称',
              maxLength: { value: 200, message: '名称不能超过 200 个字符' },
            })}
          />
          {errors.name && (
            <span className="home-field-error" id={`${id}-name-error`}>
              {errors.name.message}
            </span>
          )}
        </div>
        <p className="home-form-note">
          按已知信息填写，留空表示暂无数据。比例填写 0–1 的小数，例如 0.82。
        </p>
        {groups.map((group) => (
          <section className="home-form-group" key={group}>
            <h3>{group}</h3>
            <div className="home-form-grid">
              {fields
                .filter((field) => (field.group || '其他参数') === group)
                .map((field) => {
                  const type = fieldType(field),
                    options = fieldOptions(field),
                    fieldId = `${id}-${field.name}`
                  return (
                    <Controller
                      key={field.name}
                      control={control}
                      name={`params.${field.name}`}
                      rules={{
                        validate: (value) =>
                          validateSchemaField(field, value).join('；') || true,
                      }}
                      render={({ field: input, fieldState }) => {
                        const describedBy =
                          [
                            field.description ? `${fieldId}-help` : '',
                            fieldState.error ? `${fieldId}-error` : '',
                          ]
                            .filter(Boolean)
                            .join(' ') || undefined
                        const props = {
                          id: fieldId,
                          'aria-required': field.required,
                          'aria-invalid': !!fieldState.error,
                          'aria-describedby': describedBy,
                        }
                        return (
                          <div
                            className={`home-field${type.startsWith('array') || field.name === 'project_notes' ? ' home-field-wide' : ''}`}
                          >
                            <label htmlFor={fieldId}>
                              {field.label}
                              {field.unit && field.unit !== '—' && (
                                <small>{field.unit}</small>
                              )}
                              {field.required && (
                                <span aria-hidden="true"> *</span>
                              )}
                            </label>
                            {type.startsWith('array') ? (
                              <details className="home-options">
                                <summary>
                                  已选择{' '}
                                  {(
                                    normalizeRequiredOptions(
                                      field,
                                      input.value,
                                    ) as unknown[] | null
                                  )?.length ?? 0}{' '}
                                  项 · 展开选项
                                </summary>
                                <div
                                  id={fieldId}
                                  className="home-checkbox-list"
                                  role="group"
                                  aria-label={field.label}
                                  aria-describedby={describedBy}
                                >
                                  {options.map((option) => {
                                    const value = String(option.value),
                                      required =
                                        field.required_options?.includes(value),
                                      selected = normalizeRequiredOptions(
                                        field,
                                        input.value,
                                      ) as string[] | null
                                    return (
                                      <label key={value}>
                                        <input
                                          type="checkbox"
                                          checked={
                                            selected?.includes(value) ?? false
                                          }
                                          disabled={required || pending}
                                          onBlur={input.onBlur}
                                          onChange={(event) =>
                                            input.onChange(
                                              normalizeRequiredOptions(
                                                field,
                                                event.target.checked
                                                  ? [...(selected ?? []), value]
                                                  : selected?.filter(
                                                      (item) => item !== value,
                                                    ),
                                              ),
                                            )
                                          }
                                        />
                                        <span>
                                          {option.label}
                                          {required && <small>始终生效</small>}
                                        </span>
                                      </label>
                                    )
                                  })}
                                </div>
                              </details>
                            ) : options.length || type === 'boolean' ? (
                              <select
                                {...props}
                                {...input}
                                value={
                                  input.value == null ? '' : String(input.value)
                                }
                                className="home-input"
                              >
                                <option value="">未填写</option>
                                {(type === 'boolean'
                                  ? [
                                      { value: 'true', label: '是' },
                                      { value: 'false', label: '否' },
                                    ]
                                  : options
                                ).map((option) => (
                                  <option
                                    key={String(option.value)}
                                    value={String(option.value)}
                                  >
                                    {option.label}
                                  </option>
                                ))}
                              </select>
                            ) : field.name === 'project_notes' ||
                              type.startsWith('object') ? (
                              <textarea
                                {...props}
                                {...input}
                                value={
                                  input.value == null ? '' : String(input.value)
                                }
                                className="home-input home-textarea"
                                rows={3}
                                placeholder="未填写"
                              />
                            ) : (
                              <Input
                                {...props}
                                {...input}
                                value={
                                  input.value == null ? '' : String(input.value)
                                }
                                type={
                                  type === 'number' || type === 'integer'
                                    ? 'number'
                                    : 'text'
                                }
                                step={type === 'integer' ? 1 : 'any'}
                                placeholder="未填写"
                                onChange={(event) =>
                                  input.onChange(
                                    (type === 'number' || type === 'integer') &&
                                      event.target.value !== ''
                                      ? event.target.valueAsNumber
                                      : event.target.value,
                                  )
                                }
                              />
                            )}
                            {field.description && (
                              <span
                                className="home-field-help"
                                id={`${fieldId}-help`}
                              >
                                {field.description}
                              </span>
                            )}
                            {fieldState.error && (
                              <span
                                className="home-field-error"
                                id={`${fieldId}-error`}
                              >
                                {fieldState.error.message}
                              </span>
                            )}
                          </div>
                        )
                      }}
                    />
                  )
                })}
            </div>
          </section>
        ))}
      </fieldset>
      <div className="home-dialog-actions">
        <Button variant="outline" disabled={pending} onClick={onCancel}>
          取消
        </Button>
        <Button type="submit" disabled={pending}>
          {pending && <LoaderCircle size={15} className="home-spin" />}
          {pending ? '保存中…' : '保存项目'}
        </Button>
      </div>
    </form>
  )
}
