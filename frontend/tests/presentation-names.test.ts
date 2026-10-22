import assert from 'node:assert/strict'
import { test } from 'node:test'
import { projectNameParts, schemeNameParts, shortSchemeLabel } from '../src/utils/presentation-names'

test('项目名称将地块简称与来源说明分开，不修改原始数据', () => {
  const name = '下沙公租房一期 · 真实地块参考／教学推演（公开字段版）'
  assert.deepEqual(projectNameParts(name), { title: '下沙公租房一期', detail: '真实地块参考／教学推演（公开字段版）' })
  assert.deepEqual(projectNameParts('虚构钱塘案例 · 品质与工业化取舍'), { title: '虚构钱塘案例', detail: '品质与工业化取舍' })
  assert.equal(name, '下沙公租房一期 · 真实地块参考／教学推演（公开字段版）')
})

test('方案只分离已知演示后缀，保留方案差异及自定义括号', () => {
  assert.deepEqual(schemeNameParts('A 现浇剪力墙（演示自拟） · 教学推演'), { title: 'A 现浇剪力墙', detail: '演示自拟 · 教学推演' })
  assert.equal(schemeNameParts('A 品质优先 · 现浇剪力墙（第二版）').title, 'A 品质优先 · 现浇剪力墙（第二版）')
  assert.equal(shortSchemeLabel('B MiC模块化（演示自拟） · 教学推演'), 'B · MiC')
  assert.equal(shortSchemeLabel('C 现浇基准（演示自拟） · 教学推演'), 'C · 现浇基准')
  assert.equal(shortSchemeLabel('D 常规做法 · 现浇框架-剪力墙'), 'D · 框架-剪力墙')
})
