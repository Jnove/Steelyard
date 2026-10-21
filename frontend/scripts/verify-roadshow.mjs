/** Roadshow flow regression. Run only against an isolated local FakeLLM database. */
import assert from 'node:assert/strict'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })

const base = process.env.ROADSHOW_URL ?? 'http://127.0.0.1:5179'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname), 'Only an isolated local server is allowed')
assert.equal(process.env.ROADSHOW_ALLOW_WRITE, '1', 'Set ROADSHOW_ALLOW_WRITE=1 for the disposable test database')
const output = new URL('../../backend/data/roadshow-check/browser/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
const errors = []
const requests = []
const created = []
const checks = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (request.method() === 'POST' && /\/(plan|chat|report)$/.test(new URL(request.url()).pathname)) {
    requests.push({ path: new URL(request.url()).pathname, body: request.postDataJSON() })
  }
})
const fixture = async name => JSON.parse(await readFile(new URL(`../../data/schemes/mock/${name}`, import.meta.url), 'utf8'))
const api = async (path, data, method = 'POST') => {
  const response = await context.request.fetch(`${base}/api${path}`, { method, ...(data === undefined ? {} : { data }) })
  assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`)
  return response.status() === 204 ? undefined : response.json()
}
const complete = async () => {
  const message = page.locator('.chat-message.assistant').last()
  await expect(message.locator('.section-heading .ant-tag').first()).toHaveText('已完成', { timeout: 60_000 })
  await expect(message.locator('.ant-alert-error')).toHaveCount(0)
}
const lastRequest = kind => requests.filter(item => item.path.endsWith(`/${kind}`)).at(-1)?.body
const capture = async name => {
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.evaluate(() => new Promise(requestAnimationFrame))
  await page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, output)), fullPage: true })
}
try {
  const projectData = await fixture('project.json')
  const project = await api('/projects', { name: `路演链路验收 ${Date.now()}`, params: projectData.params })
  created.push(project.id)
  const files = ['A_高品质.json', 'C_MiC高标准化.json', 'D_均衡.json']
  const candidates = []
  for (const file of files) {
    const data = await fixture(file)
    candidates.push(await api(`/projects/${project.id}/schemes`, { name: data.name, params: data.params }))
  }
  const selected = candidates[1]
  await api(`/projects/${project.id}/evaluate`, {})
  const allSchemes = () => api(`/projects/${project.id}/schemes?include_whatif=true`, undefined, 'GET')
  const dashboard = `${base}/projects/${project.id}/dashboard`
  await page.goto(dashboard)
  await expect(page.locator('.ranking-row')).toHaveCount(3)
  await page.getByText('施工单位', { exact: true }).click()
  await expect(page.getByLabel('决策建议简报')).toContainText('结果视角：施工单位')
  await page.locator('.ant-select[aria-label="选择讨论方案"]').click()
  await page.getByTitle(selected.name, { exact: true }).last().click()
  await page.getByRole('link', { name: /讨论与报告/ }).click()
  await expect(page.getByLabel('当前决策视角')).toContainText('施工单位')
  await expect(page.locator('.chat-side').getByTitle(selected.name, { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('当前决策视角')).toContainText('施工单位')
  checks.push('角色、所选方案跨页面及刷新恢复')

  await page.getByLabel('输入追问').fill('解释当前方案的施工友好依据')
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await complete()
  assert.equal(lastRequest('plan').scheme_id, selected.id)
  assert.equal(lastRequest('chat').intent, 'explain')
  assert.equal(lastRequest('chat').role, 'contractor')
  checks.push('自然语言解释与角色、方案上下文一致')

  await page.getByRole('link', { name: '查看完整比选看板', exact: true }).click()
  await page.locator('.decision-role-options label').filter({ hasText: '自定义' }).click()
  await page.getByRole('slider', { name: '居住品质权重' }).focus()
  await page.keyboard.press('End')
  await expect(page.getByLabel('决策建议简报')).toContainText('自定义权重')
  await page.getByRole('link', { name: /讨论与报告/ }).click()
  await expect(page.getByLabel('当前决策视角')).toContainText('100.0% / 0.0% / 0.0% / 0.0%')
  const before = await allSchemes()
  const question = `假设方案 ${selected.id} 的 std_floor_repeat 改为 0.6`
  await page.getByLabel('输入追问').fill(question)
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await expect(page.getByLabel('推演确认')).toBeVisible()
  await expect(page.getByLabel('调整参数预览')).toContainText('0.6')
  assert.deepEqual(lastRequest('plan').weights, [1, 0, 0, 0])
  assert.equal((await allSchemes()).length, before.length)
  await capture('whatif-preview')
  await page.getByRole('button', { name: '返回修改', exact: true }).click()
  assert.equal((await allSchemes()).length, before.length)
  await expect(page.getByLabel('输入追问')).toHaveValue(question)
  checks.push('自然语言参数预览及取消均不写入副本')
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await expect(page.getByLabel('推演确认')).toBeVisible()
  await page.getByRole('button', { name: '确认创建副本并推演', exact: true }).click()
  await complete()
  const after = await allSchemes()
  assert.equal(after.length, before.length + 1)
  const copy = after.find(item => !before.some(old => old.id === item.id))
  assert.equal(copy.parent_id, selected.id)
  assert.equal(copy.is_whatif, true)
  assert.equal(copy.params.std_floor_repeat, 0.6)
  assert.deepEqual(after.find(item => item.id === selected.id).params, selected.params)
  assert.deepEqual(lastRequest('chat').weights, [1, 0, 0, 0])
  assert.equal(lastRequest('chat').intent, 'whatif')
  assert.equal(lastRequest('chat').change.scheme_id, selected.id)
  checks.push('确认后仅创建一个副本，原方案不变，自定义权重沿用')

  await page.getByLabel('输入追问').fill(`假设方案 ${selected.id} 的 std_floor_repeat 改为 0.7`)
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await expect(page.getByLabel('推演确认')).toBeVisible()
  await api(`/projects/${project.id}/schemes/${selected.id}`, {
    name: selected.name, params: { ...selected.params, std_floor_repeat: 0.55 },
  }, 'PUT')
  await page.getByRole('button', { name: '确认创建副本并推演', exact: true }).click()
  await expect(page.getByRole('button', { name: '重新预览调整', exact: true })).toBeVisible()
  assert.equal((await allSchemes()).length, after.length)
  await page.getByRole('button', { name: '重新预览调整', exact: true }).click()
  await expect(page.getByLabel('调整参数预览')).toContainText('0.55')
  await expect(page.getByLabel('调整参数预览')).toContainText('0.7')
  assert.equal((await allSchemes()).length, after.length)
  await page.getByRole('button', { name: '确认创建副本并推演', exact: true }).click()
  await complete()
  assert.equal((await allSchemes()).length, after.length + 1)
  checks.push('预览过期拒绝写入，重新预览新原值后再次确认才执行')

  const beforeStreamConflict = await allSchemes()
  await page.getByLabel('输入追问').fill(`假设方案 ${selected.id} 的 std_floor_repeat 改为 0.8`)
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await expect(page.getByLabel('推演确认')).toBeVisible()
  await page.route('**/api/projects/*/chat', route => route.fulfill({
    status: 200, contentType: 'text/event-stream',
    body: `event: error\ndata: ${JSON.stringify({ message: '方案或规则已变更，请重新预览并确认调整', status: 409 })}\n\n`,
  }), { times: 1 })
  await page.getByRole('button', { name: '确认创建副本并推演', exact: true }).click()
  await expect(page.getByRole('button', { name: '重新预览调整', exact: true }).last()).toBeVisible()
  await page.getByRole('button', { name: '重新预览调整', exact: true }).last().click()
  await expect(page.getByLabel('调整参数预览')).toContainText('0.8')
  assert.equal((await allSchemes()).length, beforeStreamConflict.length)
  await page.getByRole('button', { name: '返回修改', exact: true }).click()
  checks.push('流式阶段版本冲突可重新预览，恢复过程不自动创建副本（模拟响应）')

  await page.getByRole('button', { name: '生成 Markdown 报告', exact: true }).click()
  await complete()
  assert.deepEqual(lastRequest('report').weights, [1, 0, 0, 0])
  await expect(page.getByRole('button', { name: '下载 Markdown（.md）', exact: true })).toBeVisible()
  checks.push('报告沿用自定义权重且可下载')
  await capture('chat-report')

  const second = await api('/projects', { name: `上下文隔离验收 ${Date.now()}`, params: projectData.params })
  created.push(second.id)
  await page.goto(`${base}/projects/${second.id}/chat`)
  await expect(page.getByLabel('当前决策视角')).toContainText('政府')
  await page.goto(`${base}/projects/${project.id}/chat`)
  await expect(page.getByLabel('当前决策视角')).toContainText('自定义权重')
  checks.push('项目之间的上下文隔离')

  const chatCount = requests.filter(item => item.path.endsWith('/chat')).length
  await page.route('**/api/projects/*/plan', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '验收模拟：计划服务暂不可用' }) }), { times: 1 })
  await page.getByLabel('输入追问').fill('解释当前方案')
  await page.getByRole('button', { name: /^发\s*送$/ }).click()
  await expect(page.getByText('验收模拟：计划服务暂不可用', { exact: false })).toBeVisible()
  assert.equal(requests.filter(item => item.path.endsWith('/chat')).length, chatCount)
  await expect(page.getByLabel('输入追问')).toHaveValue('解释当前方案')
  await expect(page.getByRole('button', { name: /^发\s*送$/ })).toBeEnabled()
  checks.push('计划失败保留输入、不执行聊天或写入')
  await page.setViewportSize({ width: 390, height: 844 })
  await capture('chat-mobile')
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'Mobile page must not overflow')
  checks.push('390px 窄屏无页面横向溢出')
  assert.deepEqual(errors, [])
  await writeFile(new URL('verification.json', output), JSON.stringify({ passed: true, checks, consoleErrors: errors, mode: 'isolated-local-FakeLLM' }, null, 2))
  console.log(JSON.stringify({ passed: true, checks }, null, 2))
} catch (error) {
  await capture('failure').catch(() => {})
  throw error
} finally {
  for (const id of created.reverse()) await api(`/projects/${id}`, undefined, 'DELETE').catch(error => console.error(`Test project ${id} cleanup failed: ${error.message}`))
  await context.close()
  await browser.close()
}
