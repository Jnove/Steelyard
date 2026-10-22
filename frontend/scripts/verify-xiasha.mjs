/** Validate the roadshow case against an isolated local database and FakeLLM. */
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const base = process.env.ROADSHOW_URL ?? 'http://127.0.0.1:5179'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
assert.equal(process.env.ROADSHOW_ALLOW_WRITE, '1', 'Use an isolated local database')
const output = new URL('../../backend/data/xiasha-roadshow/browser/', import.meta.url)
await mkdir(output, { recursive: true })
const fixture = async filename => JSON.parse(await readFile(new URL(`../../data/schemes/xiasha-real/${filename}`, import.meta.url), 'utf8'))
const browser = await chromium.launch({ channel: process.env.ROADSHOW_BROWSER ?? 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 1000 }, acceptDownloads: true })
const page = await context.newPage()
const expect = baseExpect.configure({ timeout: 30_000 })
const errors = []
const checks = []
page.on('pageerror', error => errors.push(error.message))
const api = async (path, body, method = 'POST') => {
  const response = await context.request.fetch(`${base}/api${path}`, { method, ...(body === undefined ? {} : { data: body }) })
  assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`)
  return response.status() === 204 ? undefined : response.json()
}
let projectId
try {
  const data = await fixture('project.json')
  const project = await api('/projects', { name: `下沙口径验收 ${Date.now()}`, params: data.params })
  projectId = project.id
  for (const file of ['A_现浇剪力墙.json', 'B_MiC模块化.json', 'C_现浇基准.json']) {
    const scheme = await fixture(file)
    await api(`/projects/${projectId}/schemes`, { name: scheme.name, params: scheme.params })
  }
  const evaluation = await api(`/projects/${projectId}/evaluate`, {})
  assert.equal(evaluation.rule_count, 58)
  assert.equal(evaluation.results.length, 3)
  for (const row of evaluation.results) {
    assert.equal(row.compliance.filter(item => item.status === 'insufficient_data').length, 5)
    for (const key of ['G-05', 'Q-05', 'Q-06']) assert.equal(row.metrics[key].status, 'not_applicable')
    assert.equal(row.metrics['G-02'], undefined)
    assert.equal(row.metrics['G-03'], undefined)
  }
  checks.push('实际API：三套各5条数据不足，三代理指标不计分，施工无重复计权')
  await page.goto(`${base}/projects/${projectId}/dashboard`)
  await expect(page.getByText('已知条件下的评分与取舍', { exact: true })).toBeVisible()
  await expect(page.getByText('暂不纳入评分：G-05、Q-05、Q-06', { exact: true })).toBeVisible()
  await expect(page.getByLabel('决策建议简报')).toBeVisible()
  await page.getByText('案例来源与评分边界', { exact: true }).click()
  await expect(page.getByText(/路演主案例：真实地块参考/)).toBeVisible()
  await page.screenshot({ path: fileURLToPath(new URL('dashboard-desktop.png', output)), fullPage: true })
  checks.push('看板：缺失条件、排除指标和资料版本可见')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.waitForTimeout(400) // ECharts completes its debounced resize after the viewport changes.
  await page.screenshot({ path: fileURLToPath(new URL('dashboard-mobile.png', output)), fullPage: true })
  checks.push('390px窄屏无页面横向溢出')
  await page.setViewportSize({ width: 1366, height: 1000 })
  await page.goto(`${base}/projects/${projectId}/chat`)
  await page.getByRole('button', { name: '生成 Markdown 报告', exact: true }).click()
  const message = page.locator('.chat-message.assistant').last()
  await expect(message.locator('.section-heading .ant-tag').first()).toHaveText('已完成', { timeout: 60_000 })
  await expect(message).toContainText('已知条件下的评分与取舍')
  await expect(message).toContainText('暂不计分')
  await expect(message).toContainText('教学假设')
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: '下载 Markdown（.md）', exact: true }).click(),
  ])
  const reportPath = fileURLToPath(new URL('report.md', output))
  await download.saveAs(reportPath)
  const report = await readFile(reportPath, 'utf8')
  assert.ok(report.includes('已知条件下的评分与取舍'))
  assert.ok(report.includes('暂不计分'))
  await page.screenshot({ path: fileURLToPath(new URL('report.png', output)), fullPage: true })
  checks.push('报告生成与下载：包含已知条件、暂不计分和教学假设说明')
  assert.deepEqual(errors, [])
  await writeFile(new URL('result.json', output), JSON.stringify({ mode: 'isolated local FakeLLM', checks, errors, evaluation }, null, 2))
  console.log(JSON.stringify({ checks, errors }, null, 2))
} finally {
  if (projectId) await api(`/projects/${projectId}`, undefined, 'DELETE')
  await browser.close()
}
