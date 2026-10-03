import { compile } from 'json-schema-to-typescript'
import { readdir, readFile, mkdir, writeFile } from 'node:fs/promises'
const root = new URL('../../data/schema/jsonschema/', import.meta.url)
const output = new URL('../src/api/generated/', import.meta.url)
await mkdir(output, { recursive: true })
// Pydantic 使用 2020-12 的 prefixItems；当前生成器按 draft-07 读取元组。
// 仅转换表示方式，保留每个位置的数值类型、长度与额外项约束。
function draft07(value) {
  if (Array.isArray(value)) return value.map(draft07)
  if (!value || typeof value !== 'object') return value
  const converted = Object.fromEntries(Object.entries(value).map(([k,v]) => [k,draft07(v)]))
  if (converted.prefixItems) {
    converted.additionalItems = converted.items ?? false
    converted.items = converted.prefixItems
    delete converted.prefixItems
  }
  return converted
}
for (const file of (await readdir(root)).filter(f => f.endsWith('.json'))) {
  const schema = draft07(JSON.parse(await readFile(new URL(file, root), 'utf8')))
  const name = file.replace('.schema.json', '').replace('.json', '')
  schema.title = name
  // 定义以模型名命名，避免中文 title 被库压成空标识符。
  for (const [key, value] of Object.entries(schema.$defs ?? {})) value.title = key
  await writeFile(new URL(name + '.ts', output), await compile(schema, name, {
    bannerComment: '/* 自动生成，请运行 npm run gen:types 更新。 */', additionalProperties: false,
  }))
}
console.log('类型生成完成')
