/** Decision controls and clickable project paths against the isolated local preview. */
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })
const base = process.env.WORKBENCH_URL ?? 'http://127.0.0.1:5182'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const output = new URL('../../backend/data/homepage-ui/browser/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1224, height: 613 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = [], checks = [], requests = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (request.method() === 'POST' && /\/projects\/\d+\/rank$/.test(new URL(request.url()).pathname)) requests.push(request.postDataJSON())
})
const editor = page.getByRole('region', { name: '自定义评价权重' })
const summary = page.getByRole('region', { name: '决策建议简报' })
const settled = () => expect(summary).toHaveAttribute('aria-busy', 'false')
const savedContext = () => page.evaluate(() => JSON.parse(sessionStorage.getItem('zhuheng:decision-context:v1:1')))
const sameWeights = (actual, expected) => actual.forEach((value, index) => assert.ok(Math.abs(value - expected[index]) < 1e-10))
try {
  await page.goto(`${base}/projects/1/dashboard`)
  await settled()
  const response = await context.request.get(`${base}/api/projects/1/rank/roles`)
  assert.equal(response.status(), 200)
  const { roles } = await response.json()
  for (const template of roles) {
    await page.locator('.decision-role-options label').filter({ hasText: template.role_name }).click()
    await expect(page.getByRole('radio', { name: template.role_name, exact: true })).toBeChecked()
    await expect(page.locator('.role-state')).toHaveText('模板权重 · 只读')
    await settled()
    await expect(page.getByRole('slider')).toHaveCount(0)
    await expect(summary).toContainText(`结果视角：${template.role_name}`)
    const labels = await page.locator('.role-weight-summary dd').allTextContents()
    assert.deepEqual(labels, template.weights.map(value => `${(value * 100).toFixed(1)}%`))
    assert.deepEqual(requests.at(-1), { role: template.role })
  }
  checks.push('五个预设视角只读，显示真实模板权重，排名请求仅携带所选角色')
  await page.screenshot({ path: fileURLToPath(new URL('dashboard-preset-1224.png', output)) })

  const template = roles.at(-1)
  await page.locator('.decision-role-options label').filter({ hasText: '自定义' }).click()
  await expect(editor).toBeVisible()
  await settled()
  sameWeights((await savedContext()).weights, template.weights)
  const placement = await page.evaluate(() => {
    const editor = document.querySelector('.custom-weights-panel')
    const recommendation = document.querySelector('.executive-summary-card')
    return editor.getBoundingClientRect().bottom <= recommendation.getBoundingClientRect().top
  })
  assert.ok(placement, 'custom editor must precede recommendation')
  const slider = editor.getByRole('slider', { name: '居住品质权重' })
  await slider.focus()
  await page.keyboard.press('End')
  await settled()
  assert.deepEqual((await savedContext()).weights, [1, 0, 0, 0])
  await expect(summary).toContainText('结果视角：自定义权重')
  await page.keyboard.press('ArrowLeft')
  await settled()
  const adjusted = (await savedContext()).weights
  assert.ok(Math.abs(adjusted.reduce((sum, value) => sum + value, 0) - 1) < 1e-10)
  assert.ok(Math.abs(adjusted[0] - .99) < 1e-10)
  assert.equal(requests.at(-1).role, undefined)
  sameWeights(requests.at(-1).weights, adjusted)
  await page.reload()
  await settled()
  await expect(editor).toBeVisible()
  sameWeights((await savedContext()).weights, adjusted)
  await expect(slider).toHaveAttribute('aria-valuenow', '99')
  checks.push('自定义编辑位于推荐之前，继承当前模板；键盘调权、归一化、排名和刷新恢复一致')

  for (const [width, height] of [[1440, 900], [1224, 613], [768, 1024], [390, 844], [320, 568]]) {
    await page.setViewportSize({ width, height })
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(page.getByRole('navigation', { name: '页面路径' }).getByRole('link', { name: '工作空间', exact: true })).toBeVisible()
    await expect(editor.getByRole('slider')).toHaveCount(4)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `horizontal overflow at ${width}`)
    const overlap = await editor.locator('.weight-control').evaluateAll(elements => elements.some((element, i) => elements.slice(i + 1).some(other => {
      const a = element.getBoundingClientRect(), b = other.getBoundingClientRect()
      return Math.min(a.right, b.right) > Math.max(a.left, b.left) + 1 && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top) + 1
    })))
    assert.equal(overlap, false, `weight controls overlap at ${width}`)
    await page.screenshot({ path: fileURLToPath(new URL(`dashboard-custom-${width}.png`, output)), fullPage: false })
  }
  checks.push('1440/1224/768/390/320px 无横向溢出或滑块重叠，路径入口可见')
  await page.setViewportSize({ width: 1224, height: 613 })
  await page.locator('.decision-role-options label').filter({ hasText: '政府' }).click()
  await expect(editor).toHaveCount(0)
  await settled()
  await page.locator('.decision-role-options label').filter({ hasText: '自定义' }).click()
  await settled()
  sameWeights((await savedContext()).weights, roles.find(role => role.role === 'government').weights)
  checks.push('切回模板收起编辑器，再选自定义从当前模板开始')

  for (const id of [1, 4]) {
    await page.goto(`${base}/projects/${id}/dashboard`)
    await settled()
    const path = page.getByRole('navigation', { name: '页面路径' })
    const project = path.locator('a.workbench-breadcrumb-project')
    await expect(project).toHaveAttribute('href', `/projects/${id}/schemes`)
    await project.click()
    await expect(page).toHaveURL(`${base}/projects/${id}/schemes`)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('方案录入')
    await path.getByRole('link', { name: '工作空间', exact: true }).click()
    await expect(page).toHaveURL(`${base}/projects`)
  }
  checks.push('项目1和4的面包屑分别进入对应方案录入，工作空间返回项目总览')
  assert.deepEqual(errors, [])
  await writeFile(new URL('dashboard-controls-report.json', output), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks }, null, 2))
} finally { await browser.close() }
