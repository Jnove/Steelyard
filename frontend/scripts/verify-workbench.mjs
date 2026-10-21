/** Visual and navigation acceptance against the isolated local preview. No production writes. */
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })

const base = process.env.WORKBENCH_URL ?? 'http://127.0.0.1:5182'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const output = new URL('../../backend/data/homepage-ui/browser/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
const errors = [], checks = []
page.on('pageerror', error => errors.push(error.message))
const capture = name => page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, output)), fullPage: !['scheme-form', 'trace-drawer'].includes(name) })
try {
  await page.goto(`${base}/`)
  const stage = page.getByRole('region', { name: '建筑体量展台' })
  const choices = stage.getByRole('group', { name: '切换展示方案' }).getByRole('button')
  await expect(choices.nth(1)).toBeVisible()
  const projectId = await page.getByLabel('选择展台项目').inputValue()
  await expect(stage).toHaveAttribute('data-renderer', /webgl|static/)
  await choices.nth(1).click()
  await expect(choices.nth(1)).toHaveAttribute('aria-pressed', 'true')
  const schemeName = (await choices.nth(1).getAttribute('aria-label')).replace('展示方案 ', '')
  await expect(stage.locator('.stage-float > strong')).toHaveText(schemeName)
  const renderer = await stage.getAttribute('data-renderer')
  if (renderer === 'webgl') {
    await stage.locator('canvas').press('ArrowRight')
    await stage.locator('canvas').press('Home')
    await stage.getByRole('button', { name: '复位视角' }).click()
  }
  checks.push(`首屏建筑展台、方案切换、键盘旋转与复位 (${renderer})`)
  await page.getByRole('link', { name: '进入项目工作台', exact: true }).click()
  await expect(page).toHaveURL(`${base}/projects`)
  await expect(page.getByRole('region', { name: '建筑体量展台' })).toHaveCount(0)
  await page.getByRole('link', { name: '筑衡 · 返回首页' }).click()
  await expect(page).toHaveURL(`${base}/`)
  checks.push('展示首页进入项目工作台，工作台不加载建筑展台，品牌入口可返回首页')

  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(`${base}/`)
    await expect(choices.nth(1)).toBeVisible()
    await expect(stage).toHaveAttribute('data-renderer', /webgl|static/)
    await expect(page.getByRole('link', { name: '进入项目工作台', exact: true })).toBeInViewport()
    await expect(page.locator('.home-sidebar')).toHaveCount(0)
    const lines = await page.locator('h1').evaluate(element => element.getBoundingClientRect().height / parseFloat(getComputedStyle(element).lineHeight))
    assert.ok(lines < 2.1, `landing headline wraps at ${width}`)
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
    await capture(`landing-${width}`)
    await page.screenshot({ path: fileURLToPath(new URL(`landing-${width}-fold.png`, output)) })
    for (const [route, heading] of [['', '项目总览'], ['schemes', '方案录入'], ['dashboard', '方案对比看板'], ['chat', '对话与报告']]) {
      await page.goto(`${base}/projects${route ? `/${projectId}/${route}` : ''}`)
      await expect(page.getByRole('heading', { level: 1 })).toContainText(heading)
      if (route === 'dashboard') await expect(page.getByLabel('方案比较工作台')).toBeVisible()
      if (route === 'schemes') await expect(page.locator('.styled-spec-table tbody tr.ant-table-row').first()).toBeVisible()
      if (route === 'chat') {
        await expect(page.locator('.ant-select[aria-label="选择追问与溯源方案"]')).toBeVisible()
        await expect(page.locator('.chat-side .ant-progress').first()).toBeVisible()
        await expect(page.getByLabel('快捷问题').getByRole('button').first()).toBeEnabled()
      }
      if (!route) await expect(stage).toHaveCount(0)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${route || 'home'} overflows at ${width}`)
      await capture(`${route || 'homepage'}-${width}`)
      await page.screenshot({ path: fileURLToPath(new URL(`${route || 'homepage'}-${width}-fold.png`, output)) })
      if (width < 1100) {
        const trigger = page.getByRole('button', { name: '打开页面导航' })
        await trigger.click()
        await expect(page.getByRole('dialog').getByRole('navigation', { name: '页面导航' })).toBeVisible()
        await page.keyboard.press('Escape')
        await expect(trigger).toBeFocused()
      }
    }
  }
  checks.push('首页、方案、看板、对话在 1440/768/390px 的布局和窄屏导航')

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${base}/projects/${projectId}/schemes`)
  await page.getByRole('button', { name: '添加方案', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(page.locator('.ant-modal')).not.toHaveClass(/(?:enter|appear)-(?:active|prepare)/)
  await expect(dialog).toContainText('添加候选方案')
  await dialog.getByRole('button', { name: /^保\s*存方案$/ }).click()
  await expect(dialog.getByText('请输入方案名称', { exact: true })).toBeVisible()
  await expect(dialog.getByText('请输入方案名称', { exact: true })).toBeInViewport()
  await capture('scheme-form')
  await dialog.getByRole('button', { name: /^取\s*消$/ }).click()
  checks.push('方案表单打开、必填校验与取消')

  await page.goto(`${base}/projects/${projectId}/dashboard`)
  const workbench = page.getByLabel('方案比较工作台')
  await expect(workbench).toHaveAttribute('aria-busy', 'false')
  await workbench.locator('.comp-score-list .score-button').first().click()
  await expect(page.locator('.ant-drawer-content')).toBeVisible()
  await capture('trace-drawer')
  await page.locator('.ant-drawer-close').click()
  for (const [view, tab] of [['map', '看整体'], ['pair', '比两套'], ['matrix', '查全表']]) {
    await workbench.getByRole('tab', { name: new RegExp(tab) }).click()
    if (view === 'pair') {
      const first = await page.getByLabel('差值图方案一').inputValue()
      const second = await page.getByLabel('差值图方案二').inputValue()
      await page.getByRole('button', { name: '交换对比方案' }).click()
      await expect(page.getByLabel('差值图方案一')).toHaveValue(second)
      await expect(page.getByLabel('差值图方案二')).toHaveValue(first)
    }
    if (view === 'matrix') {
      await page.getByLabel('搜索指标或规则', { exact: true }).fill('不存在的指标')
      await expect(workbench.locator('.comp-cell')).toHaveCount(0)
      await page.getByRole('button', { name: '清空指标搜索' }).click()
      await expect(workbench.locator('.comp-cell').first()).toBeVisible()
      await workbench.locator('.comp-cell').first().press('ArrowRight')
      await expect(workbench.locator('.comp-cell').nth(1)).toBeFocused()
    }
    await capture(`comparison-${view}`)
    const download = page.waitForEvent('download')
    await workbench.getByRole('button', { name: /导出当前图/ }).click()
    const file = await download
    assert.match(file.suggestedFilename(), new RegExp(`comparison-${view}.*\\.svg$`))
    const svg = await readFile(await file.path(), 'utf8')
    assert.match(svg, /<svg/)
    assert.match(svg, /#327473/)
  }
  checks.push('依据抽屉、三种比较视图、方案交换、指标搜索、方向键与 SVG 导出')

  await page.goto(`${base}/projects/${projectId}/schemes`)
  await page.evaluate(() => window.scrollTo(0, 500))
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '对话与报告' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('对话与报告')
  assert.equal(await page.evaluate(() => scrollY), 0)
  const selector = page.getByLabel('切换当前项目')
  const otherId = await selector.locator('option').evaluateAll(options => options.find(option => option.value !== options.find(option => option.selected)?.value)?.value)
  await selector.selectOption(otherId)
  await expect(page).toHaveURL(new RegExp(`/projects/${otherId}/chat$`))
  checks.push('跨页面回到顶部，切换项目保留当前工作页')

  const fallback = await context.newPage()
  fallback.on('pageerror', error => errors.push(error.message))
  await fallback.route('**/api/projects', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '验收模拟：展示项目暂不可用' }) }))
  await fallback.goto(`${base}/`)
  await expect(fallback.getByRole('alert')).toContainText('验收模拟：展示项目暂不可用')
  await expect(fallback.getByRole('link', { name: '进入项目工作台', exact: true })).toHaveAttribute('href', `${new URL(base).pathname.replace(/\/$/, '')}/projects`.replace(/^\/\//, '/'))
  await fallback.unroute('**/api/projects')
  await fallback.route('**/api/projects', route => route.fulfill({ status: 200, contentType: 'application/json', body: '[]' }))
  await fallback.reload()
  await expect(fallback.getByText('还没有展示项目，进入工作台录入第一组候选方案。')).toBeVisible()
  await expect(fallback.getByLabel('选择展台项目')).toHaveCount(0)
  await fallback.close()
  checks.push('展示数据失败或为空时保持首页可读，工作台入口仍可用')

  const staticPage = await context.newPage()
  staticPage.on('pageerror', error => errors.push(error.message))
  await staticPage.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      return String(kind).includes('webgl') ? null : original.call(this, kind, ...args)
    }
  })
  await staticPage.goto(`${base}/`)
  const staticStage = staticPage.getByRole('region', { name: '建筑体量展台' })
  await expect(staticStage.locator('.stage-float')).toBeVisible()
  await expect(staticStage).toHaveAttribute('data-renderer', 'static')
  await expect(staticStage.getByText('静态体量示意 · 仍可切换方案')).toBeVisible()
  await staticStage.getByRole('group', { name: '切换展示方案' }).getByRole('button').nth(1).click()
  await expect(staticStage.getByRole('group', { name: '切换展示方案' }).getByRole('button').nth(1)).toHaveAttribute('aria-pressed', 'true')
  await staticPage.close()
  checks.push('WebGL 不可用时显示静态体量，方案切换仍可用')
  assert.deepEqual(errors, [])
  await writeFile(new URL('workbench-acceptance.json', output), JSON.stringify({ checks, pageErrors: errors }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks }, null, 2))
} finally { await browser.close() }
