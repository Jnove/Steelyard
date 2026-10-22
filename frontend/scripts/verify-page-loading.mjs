/** Production-build checks against isolated local previews; no business data is changed. */
import assert from 'node:assert/strict'
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { gzipSync } from 'node:zlib'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })
const before = process.env.LOADING_BEFORE_URL?.replace(/\/$/, '')
const after = (process.env.LOADING_AFTER_URL ?? 'http://127.0.0.1:5185').replace(/\/$/, '')
for (const url of [before, after].filter(Boolean)) assert.ok(['localhost', '127.0.0.1'].includes(new URL(url).hostname))
const output = new URL('../../backend/data/homepage-ui/performance/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const checks = [], observations = [], screenshots = []
const bundleFiles = {}
const contextOptions = { viewport: { width: 1224, height: 613 }, reducedMotion: 'reduce' }
const ready = page => expect(page.getByRole('region', { name: '决策建议简报' })).toHaveAttribute('aria-busy', 'false')
const radar = page => page.getByRole('img', { name: '各方案四维得分雷达图' })
const capture = async (page, name) => {
  const path = fileURLToPath(new URL(`${name}.png`, output))
  await page.screenshot({ path, fullPage: false })
  screenshots.push(path)
}
try {
  const targets = [...(before ? [['before', before, /\/assets\/TraceDrawer-[^/]+\.js$/]] : []), ['after', after, /\/assets\/ChartRenderer-[^/]+\.js$/]]
  for (const [name, base, asset] of targets) {
    const context = await browser.newContext(contextOptions)
    const page = await context.newPage()
    const errors = [], requests = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('request', request => requests.push(request.url()))
    let release, intercepted = false
    const gate = new Promise(resolve => { release = resolve })
    await page.route(asset, async route => {
      bundleFiles[name] = new URL(route.request().url()).pathname.split('/').at(-1)
      intercepted = true; await gate; await route.continue()
    })
    try {
      await page.goto(`${base}/projects/5/dashboard`, { waitUntil: 'domcontentloaded' })
      await expect.poll(() => intercepted).toBe(true)
      if (name === 'before') {
        await expect(page.getByRole('heading', { name: '方案对比看板', exact: true })).toHaveCount(0)
        observations.push('优化前：图表依赖未下载时，看板页面不能挂载')
      } else {
        await ready(page)
        await expect(page.getByRole('heading', { name: '方案对比看板', exact: true })).toBeVisible()
        await expect(page.locator('.ranking-row')).toHaveCount(5)
        await expect(radar(page).getByRole('status', { name: '图表加载中' })).toBeVisible()
        assert.equal(requests.some(url => /TraceContent-/.test(url)), false)
        observations.push('优化后：图表依赖未下载时，五套方案排名、建议及导航均已可用')
        await capture(page, 'after-chart-pending')
      }
      release()
      await ready(page)
      await expect(radar(page).locator('canvas')).toBeVisible()
      assert.deepEqual(errors, [])
    } finally { release(); await context.close() }
  }
  checks.push('延迟图表下载：看板与排名不再被图表依赖阻塞，图表随后正常渲染')

  const context = await browser.newContext(contextOptions)
  const page = await context.newPage()
  const errors = [], requests = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => requests.push({ url: request.url(), method: request.method(), body: request.postData() }))
  await context.addInitScript(() => sessionStorage.setItem('zhuheng:decision-context:v1:5', JSON.stringify({
    projectId: 5, role: 'custom', weights: [.1, .2, .3, .4],
  })))
  await page.goto(`${after}/projects`)
  await expect(page.locator('.home-project-name').first()).toBeVisible()
  assert.equal(requests.some(request => /SchemaForm-|TraceContent-|ChartRenderer-/.test(request.url)), false)
  let release, intercepted = false
  const gate = new Promise(resolve => { release = resolve })
  await page.route(/\/assets\/SchemesPage-[^/]+\.js$/, async route => { intercepted = true; await gate; await route.continue() })
  try {
    const link = page.locator(`a[href="${new URL(`${after}/projects/5/schemes`).pathname}"]`).first()
    const schemesResponse = page.waitForResponse(response => /\/api\/projects\/5\/schemes$/.test(response.url()) && response.status() === 200)
    await link.hover()
    await schemesResponse
    await expect.poll(() => intercepted).toBe(true)
    assert.equal(requests.some(request => request.method !== 'GET'), false)
    await link.click()
    await expect(page.getByRole('navigation', { name: '主导航' })).toBeVisible()
    await expect(page.getByRole('navigation', { name: '页面路径' })).toBeVisible()
  } finally { release() }
  await expect(page.getByRole('heading', { level: 1 })).toContainText('方案录入')
  await expect(page.locator('.styled-spec-table tbody tr.ant-table-row').first()).toBeVisible()
  assert.equal(requests.filter(request => /\/api\/projects\/5\/schemes$/.test(request.url)).length, 1)
  assert.equal(requests.some(request => /SchemaForm-/.test(request.url)), false)
  checks.push('鼠标悬停提前载入页面与数据；切换时保留导航，进入后复用预加载结果')

  await page.getByRole('button', { name: '添加方案', exact: true }).click()
  await expect(page.locator('.ant-modal-body #name')).toBeVisible()
  assert.equal(requests.some(request => /SchemaForm-/.test(request.url)), true)
  await page.getByRole('button', { name: /^取\s*消$/ }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  checks.push('编辑表单仅打开时下载，取消后返回方案列表')

  const dashboard = page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: '对比看板', exact: true })
  await dashboard.focus()
  await expect.poll(() => requests.some(request => /\/api\/projects\/5\/evaluate$/.test(request.url))).toBe(true)
  assert.equal(requests.some(request => request.method !== 'GET'), false)
  await dashboard.press('Enter')
  await ready(page)
  const rank = requests.filter(request => request.method === 'POST' && /\/rank$/.test(request.url)).at(-1)
  assert.deepEqual(JSON.parse(rank.body), { weights: [.1, .2, .3, .4] })
  await expect(page.getByRole('region', { name: '自定义评价权重' })).toBeVisible()
  checks.push('键盘聚焦同样预加载；自定义权重跨页保留，实际进入看板才请求排序')

  assert.equal(requests.some(request => /TraceContent-/.test(request.url)), false)
  await page.locator('.dashboard-scheme-details > summary').click()
  const trigger = page.locator('.score-button').first()
  await trigger.click()
  await expect(page.locator('.ant-drawer-body .trace-item').first()).toBeVisible()
  await expect(page.locator('.ant-drawer-body canvas').first()).toBeVisible()
  assert.equal(requests.some(request => /TraceContent-/.test(request.url)), true)
  await capture(page, 'after-trace-drawer')
  await page.keyboard.press('Escape')
  await expect(page.locator('.ant-drawer-content-wrapper')).not.toBeVisible()
  await expect(trigger).toBeFocused()
  checks.push('评分溯源仅打开时下载，评分曲线正常渲染；关闭后焦点回到原按钮')
  assert.deepEqual(errors, [])
  await context.close()

  const failedContext = await browser.newContext(contextOptions)
  const failedPage = await failedContext.newPage()
  await failedPage.route(/\/assets\/ChartRenderer-[^/]+\.js$/, route => route.abort('failed'))
  await failedPage.goto(`${after}/projects/5/dashboard`)
  await ready(failedPage)
  await expect(failedPage.getByText('图表暂时无法加载', { exact: true })).toBeVisible()
  await expect(failedPage.locator('.ranking-row')).toHaveCount(5)
  await failedContext.close()
  checks.push('图表下载失败显示局部提示，排名与页面仍可使用')

  const bundles = {}
  const afterAssets = process.env.LOADING_AFTER_DIST
    ? new URL('assets/', pathToFileURL(resolve(process.env.LOADING_AFTER_DIST) + sep))
    : new URL('../dist/assets/', import.meta.url)
  for (const [name, assets] of [...(before ? [['before', new URL('before-dist/assets/', output)]] : []), ['after', afterAssets]]) {
    const file = bundleFiles[name]
    assert.ok(file, `${name} production bundle missing`)
    const content = await readFile(new URL(file, assets))
    bundles[name] = { file, bytes: (await stat(new URL(file, assets))).size, gzipBytes: gzipSync(content).length }
  }
  if (bundles.before) assert.ok(bundles.after.gzipBytes < bundles.before.gzipBytes * .6)
  const report = { checks, observations, bundles, screenshots }
  await writeFile(new URL('page-loading-report.json', output), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} finally { await browser.close() }
