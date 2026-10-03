import { cp, mkdir } from 'node:fs/promises'
const out = new URL('../src/mocks/data/', import.meta.url)
await mkdir(out, { recursive: true })
await cp(new URL('../../data/schemes/mock/', import.meta.url), new URL('schemes/', out), { recursive: true })
await cp(new URL('../../data/schema/', import.meta.url), new URL('schema/', out), { recursive: true })
console.log('示例数据与字段清单同步完成')
