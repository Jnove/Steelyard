/** Homepage acceptance uses only a local preview API; creates/deletes its own project. */
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const base = process.env.HOMEPAGE_URL ?? 'http://127.0.0.1:5182'
if (!['localhost', '127.0.0.1'].includes(new URL(base).hostname))
  throw new Error('Homepage acceptance only runs against a local preview')
const output = fileURLToPath(
  new URL('../../backend/data/homepage-ui/browser/', import.meta.url),
)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: 'reduce',
})
const page = await context.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
page.setDefaultTimeout(15_000)
let createdId
const name = `首页验收 ${Date.now()}`
const checks = []
try {
  await page.goto(`${base}/projects`)
  await expect(
    page.getByRole('table', { name: '项目列表' }).locator('tbody tr').first(),
  ).toBeVisible()
  await expect(
    page.getByRole('complementary', { name: '当前项目详情' }),
  ).toContainText('候选方案')
  const stage = page.getByRole('region', { name: '建筑体量展台' })
  await expect(stage.locator('.stage-float')).toBeVisible()
  await expect(stage).toHaveAttribute('data-renderer', /webgl|static/)
  assert.ok((await stage.boundingBox()).y < 400, 'building showcase remains visible above the project list')
  await page.screenshot({
    path: path.join(output, 'homepage-desktop.png'),
    fullPage: true,
  })
  checks.push('desktop project table and selected details')

  await page.getByRole('button', { name: /教学案例/ }).click()
  const teaching = await page.locator('.home-project-name').allTextContents()
  assert.ok(
    teaching.length > 0 &&
      teaching.every((name) => name.includes('教学') && !name.includes('虚构')),
  )
  await page.getByRole('button', { name: /虚构示例/ }).click()
  const fictional = await page.locator('.home-project-name').allTextContents()
  assert.ok(
    fictional.length > 0 && fictional.every((name) => name.includes('虚构')),
  )
  await page.getByRole('button', { name: /全部项目/ }).click()
  await page.getByRole('textbox', { name: '搜索项目' }).fill('不存在的项目检索')
  await expect(
    page.getByText('没有找到匹配项目', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '清除筛选' }).click()
  const selectedName = await page
    .locator('.home-project-name')
    .first()
    .textContent()
  await page.locator('.home-project-name').first().click()
  await expect(
    page
      .getByRole('complementary', { name: '当前项目详情' })
      .getByRole('heading', { level: 2 }),
  ).toHaveText(selectedName)
  await page.getByRole('button', { name: '按更新时间排序' }).click()
  await expect(page.locator('th[aria-sort="ascending"]')).toBeVisible()
  checks.push('case filters, search, empty results, selection and sorting')

  for (const width of [320, 375, 414, 768]) {
    await page.setViewportSize({ width, height: 950 })
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `page overflow at ${width}`,
    )
    await page.getByRole('button', { name: '新建项目', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    const bounds = await page.getByRole('dialog').boundingBox()
    assert.ok(
      bounds.x >= 0 && bounds.x + bounds.width <= width + 1,
      `dialog overflow at ${width}`,
    )
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    if (width === 375 || width === 768)
      await page.screenshot({
        path: path.join(output, `homepage-${width}.png`),
        fullPage: true,
      })
  }
  checks.push('320/375/414/768 viewport and dialog fit')

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: '新建项目', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: '保存项目', exact: true }).click()
  await expect(
    dialog.getByText('请输入项目名称', { exact: true }),
  ).toBeVisible()
  await dialog.getByRole('textbox', { name: '项目名称' }).fill(name)
  await dialog.getByRole('spinbutton', { name: /用地面积/ }).fill('12345')
  await dialog.getByRole('spinbutton', { name: /容积率/ }).fill('2.5')
  await dialog.getByRole('spinbutton', { name: /建筑密度/ }).fill('0')
  await dialog
    .getByRole('combobox', { name: /气候/ })
    .selectOption({ label: '夏热冬冷' })
  await page.screenshot({
    path: path.join(output, 'homepage-create.png'),
    fullPage: true,
  })
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/projects') &&
      response.request().method() === 'POST',
  )
  await dialog.getByRole('button', { name: '保存项目', exact: true }).click()
  const createResult = await createdResponse
  const created = await createResult.json()
  assert.equal(createResult.status(), 201, JSON.stringify(created))
  createdId = created.id
  assert.equal(created.params.site_area, 12345)
  assert.equal(created.params.density_max, 0)
  assert.equal(created.params.climate_zone, '夏热冬冷')
  await expect(page).toHaveURL(new RegExp(`/projects/${createdId}/schemes$`))
  assert.equal(
    await page
      .locator('body')
      .evaluate((body) => body.classList.contains('home-active')),
    true,
  )
  checks.push(
    'required field, numeric zero, enum, create and shared workbench shell',
  )

  await page.goto(`${base}/projects`)
  await page
    .getByRole('button', { name: `编辑地块${name}`, exact: true })
    .click()
  await expect(
    page.getByRole('dialog').getByRole('spinbutton', { name: /用地面积/ }),
  ).toHaveValue('12345')
  await page
    .getByRole('dialog')
    .getByRole('spinbutton', { name: /用地面积/ })
    .fill('23456')
  const updatedResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/projects/${createdId}`) &&
      response.request().method() === 'PUT',
  )
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '保存项目', exact: true })
    .click()
  const updated = await (await updatedResponse).json()
  assert.equal(updated.params.site_area, 23456)
  assert.equal(updated.params.density_max, 0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('status')).toContainText('地块已更新')
  await page
    .getByRole('button', { name: `删除项目${name}`, exact: true })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '取消', exact: true })
    .click()
  await expect(page.getByRole('button', { name, exact: true })).toBeVisible()
  await page
    .getByRole('button', { name: `删除项目${name}`, exact: true })
    .click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: '确认删除', exact: true })
    .click()
  await expect(page.getByRole('status')).toContainText('项目及其方案已删除')
  await expect(page.getByRole('button', { name, exact: true })).toHaveCount(0)
  createdId = undefined
  checks.push('edit retains unchanged values, delete cancel and confirm')

  await page.getByRole('button', { name: '使用指南', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('开始一次方案比选')
  await page.keyboard.press('Escape')
  await expect(
    page.getByRole('button', { name: '使用指南', exact: true }),
  ).toBeFocused()
  await page.getByRole('button', { name: '收起侧栏' }).click()
  await expect(page.getByRole('button', { name: '展开侧栏' })).toBeVisible()
  await page.getByRole('button', { name: '展开侧栏' }).click()
  checks.push('guide focus restore and sidebar collapse')

  await page.route('**/api/projects', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '验收模拟：项目服务暂不可用' }),
    }),
  )
  await page.getByRole('button', { name: '刷新项目列表' }).click()
  await expect(page.getByRole('alert')).toContainText(
    '验收模拟：项目服务暂不可用',
  )
  await page.unroute('**/api/projects')
  await page.getByRole('button', { name: '重新加载', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.locator('.home-project-name').first()).toBeVisible()
  checks.push('request failure and recovery')

  assert.deepEqual(errors, [])
  await writeFile(
    path.join(output, 'acceptance.json'),
    JSON.stringify({ checks, pageErrors: errors }, null, 2),
  )
  console.log(
    JSON.stringify({ passed: checks.length, checks, output }, null, 2),
  )
} finally {
  if (createdId)
    await context.request.delete(`${base}/api/projects/${createdId}`)
  await browser.close()
}
