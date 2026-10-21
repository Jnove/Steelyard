/** 用隔离的 FakeLLM 数据库验收完整前后端链路，禁止对已有项目运行。 */
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium, expect } from '@playwright/test'

const base = process.env.INTEGRATION_URL ?? 'http://127.0.0.1:5178'
const output = new URL('../../backend/data/integration-ui/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } })
const page = await context.newPage()
page.setDefaultTimeout(30_000)
const errors = []
const chatRequests = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (request.method() === 'POST' && request.url().endsWith('/chat')) chatRequests.push(request.postDataJSON())
})
const lastAssistant = () => page.locator('.chat-message.assistant').last()
const complete = () => expect(lastAssistant().locator('.section-heading .ant-tag').first())
  .toHaveText('已完成', { timeout: 60_000 })
try {
  await page.goto(base + '/projects')
  await page.getByRole('link', { name: '管理方案', exact: true }).first().click()
  await page.getByRole('button', { name: '开始评估', exact: true }).click()
  await expect(page.locator('.ranking-row')).toHaveCount(4)
  await expect(page.locator('.excluded-row')).toContainText('B 不合规')
  await page.getByText('设计单位', { exact: true }).click()
  await expect(page.locator('.weight-label').first()).toContainText('28.6')
  await expect(page.getByText('直接赋权，无两两比较矩阵', { exact: true })).toBeVisible()
  await page.getByText('政府', { exact: true }).click()
  const response = await page.request.post(base + '/api/projects/1/rank', { data: { role: 'government' } })
  assert.equal(response.status(), 200)
  const rank = await response.json()
  const leader = rank.sensitivity.cells[0].top_index
  const leaderName = rank.ranking.find(row => row.scheme_id === rank.scheme_order[leader]).scheme_name
  await expect(page.locator('.sensitivity-table tbody tr').first().locator('td').first()).toContainText(leaderName)
  await page.getByRole('slider', { name: '居住品质权重' }).focus()
  await page.keyboard.press('End')
  await expect(page.locator('.ranking-row').first()).toContainText('A 高品质')
  await page.getByText('政府', { exact: true }).click()
  await expect(page.locator('.ranking-row').first()).toContainText('C MiC 高标准化')
  await page.locator('.score-button').first().click()
  await expect(page.getByRole('dialog')).toContainText('原始输入')
  await page.keyboard.press('Escape')
  await page.screenshot({ path: fileURLToPath(new URL('dashboard.png', output)), fullPage: true })
  await page.locator('nav a[href$="/chat"]').click()
  await page.getByRole('button', { name: '生成 Markdown 报告', exact: true }).click()
  await complete()
  await expect(lastAssistant().locator('.ant-alert-error')).toHaveCount(0)
  const downloadWait = page.waitForEvent('download')
  await lastAssistant().getByRole('button', { name: '下载 Markdown（.md）', exact: true }).click()
  const download = await downloadWait
  await download.saveAs(fileURLToPath(new URL('report.md', output)))
  await page.getByRole('button', { name: '生成 Markdown 报告', exact: true }).click()
  await complete()
  await expect(lastAssistant()).toContainText('已读取报告缓存')
  const chatStarted = Date.now()
  await page.getByLabel('快捷问题').getByRole('button').first().click()
  await complete()
  const chatElapsedMs = Date.now() - chatStarted
  assert.ok(chatRequests.at(-1).history.length >= 2)
  assert.ok(chatRequests.at(-1).history.every(item => ['user', 'assistant'].includes(item.role)))
  const original = await (await page.request.get(base + '/api/projects/1/schemes/3')).json()
  const beforeCopies = await (await page.request.get(base + '/api/projects/1/schemes?include_whatif=true')).json()
  await page.getByRole('spinbutton', { name: '假设的标准层重复率' }).fill('0.6')
  await page.getByRole('button', { name: '预览参数调整', exact: true }).click()
  await expect(page.getByLabel('推演确认')).toBeVisible()
  await page.getByRole('button', { name: '确认创建副本并推演', exact: true }).click()
  await complete()
  assert.equal(chatRequests.at(-1).change.field, 'std_floor_repeat')
  const after = await (await page.request.get(base + '/api/projects/1/schemes/3')).json()
  assert.deepEqual(after.params, original.params)
  const schemes = await (await page.request.get(base + '/api/projects/1/schemes?include_whatif=true')).json()
  const newSchemes = schemes.filter(scheme => !beforeCopies.some(previous => previous.id === scheme.id))
  assert.equal(newSchemes.length, 1)
  assert.ok(newSchemes[0].parent_id === 3 && newSchemes[0].is_whatif && newSchemes[0].params.std_floor_repeat === 0.6)
  // 假设推演的候选集合不能污染政府正式方案的查询缓存。
  await expect(page.locator('.chat-side .panel').first().locator('.ant-progress')).toHaveCount(4)
  await page.screenshot({ path: fileURLToPath(new URL('whatif.png', output)), fullPage: true })
  // FakeLLM 完成很快，用延迟响应确保取消发生在请求尚未完成时。
  await page.route('**/api/projects/1/report', async route => {
    await new Promise(resolve => setTimeout(resolve, 1000))
    await route.fulfill({ contentType: 'text/event-stream', body: 'event: token\ndata: {"text":"部分内容"}\n\n' }).catch(() => {})
  })
  await page.getByRole('button', { name: '生成 Markdown 报告', exact: true }).click()
  await page.getByRole('button', { name: '停止生成', exact: true }).click()
  await expect(lastAssistant()).toContainText('已停止 · 内容未完成')
  await page.unroute('**/api/projects/1/report')
  // 单独注入校验耗尽的协议响应，验证最终正文、emoji 偏移和 HTML 转义。
  const report = '😀 得分998.23 <img src=x onerror=alert(1)>'
  const final = { report, cached: false, intent: 'explain', traces: [],
    unverified_numbers: [{ text: '998.23', start: 4, end: 10 }] }
  await page.route('**/api/projects/1/chat', route => route.fulfill({ contentType: 'text/event-stream',
    body: 'event: token\ndata: {"text":"旧草稿","replace":true}\n\n'
      + 'event: citation_warning\ndata: {"attempt":2,"exhausted":true,"unverified_numbers":[]}\n\n'
      + `event: done\ndata: ${JSON.stringify(final)}\n\n` }))
  await page.getByRole('textbox', { name: '输入追问' }).fill('验证最终正文显示')
  await page.locator('.chat-compose button[type="submit"]').click()
  await complete()
  await expect(lastAssistant().locator('mark')).toHaveText('998.23')
  await expect(lastAssistant()).not.toContainText('旧草稿')
  await expect(lastAssistant().locator('img')).toHaveCount(0)
  // 页面消费 done 后会取消 reader，CDP 未必还能读取整份响应体；独立读取 HTTP 证据。
  const finalReports = []
  for (let request = 0; request < 2; request++) {
    const response = await page.request.post(base + '/api/projects/1/report', { data: { role: 'government' } })
    assert.equal(response.status(), 200)
    const wire = await response.text()
    const match = wire.match(/event: done\r?\ndata: (.+)/)
    assert.ok(match)
    finalReports.push(JSON.parse(match[1]))
    if (request === 0) await writeFile(new URL('integration-report.sse.txt', output), wire)
  }
  assert.ok(finalReports.some(item => item.cached))
  assert.ok(finalReports.every(item => item.unverified_numbers.length === 0))
  assert.deepEqual(errors, [])
  await writeFile(new URL('integration-ui.json', output), JSON.stringify({
    mode: '真实 REST / SSE + FakeLLM，独立虚构数据库',
    flows: ['录入后评估', '不合规排除', 'scheme_order 敏感性映射', '滑杆排序', '评分溯源',
      '报告与下载', '缓存命中', '带历史的追问', 'What-if 新副本与原方案不变', '正式排序缓存隔离', '取消', '校验耗尽标红与 HTML 转义'],
    backendReports: finalReports.length, cachedReports: finalReports.filter(item => item.cached).length, chatElapsedMs,
    consoleErrors: errors,
  }, null, 2))
  console.log('真实前后端集成流程通过；原方案未修改、报告缓存命中、最终数字标红正确。')
} finally {
  await context.close()
  await browser.close()
}
