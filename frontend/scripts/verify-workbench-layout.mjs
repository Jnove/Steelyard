/** Layout regressions for the presentation workbench; use a local API with the demo cases. */
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const base = process.env.WORKBENCH_URL ?? 'http://127.0.0.1:5182'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = new URL('../../backend/data/homepage-ui/workbench-polish/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1224, height: 613 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const expect = baseExpect.configure({ timeout: 20_000 })
const errors = [], checks = [], measurements = []
let importProjectId
page.on('pageerror', error => errors.push(error.message))
const capture = name => page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, output)), fullPage: false })

async function noPageOverflow(label) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, label)
}

async function plotFits() {
  const plot = page.locator('.comp-plot').first()
  await expect.poll(() => plot.evaluate(element => Math.abs(element.querySelector('svg').viewBox.baseVal.width - element.querySelector('svg').clientWidth))).toBeLessThan(2)
  const bounds = await plot.evaluate(element => {
    const svg = element.querySelector('svg'), width = svg.viewBox.baseVal.width
    const boxes = [...svg.querySelectorAll('.comp-point-label-box')].map(rect => ({ x: rect.x.baseVal.value, y: rect.y.baseVal.value, width: rect.width.baseVal.value, height: rect.height.baseVal.value }))
    return { client: element.clientWidth, scroll: element.scrollWidth, width, boxes,
      text: [...svg.querySelectorAll('.comp-point-label')].map(label => ({ text: label.textContent, size: label.getBoundingClientRect().height })) }
  })
  assert.ok(bounds.scroll <= bounds.client + 2, JSON.stringify(bounds))
  for (const [index, box] of bounds.boxes.entries()) {
    assert.ok(box.x >= 0 && box.x + box.width <= bounds.width, JSON.stringify(box))
    for (const other of bounds.boxes.slice(index + 1)) assert.ok(
      box.x + box.width <= other.x || other.x + other.width <= box.x || box.y + box.height <= other.y || other.y + other.height <= box.y,
      `plot labels overlap: ${JSON.stringify(bounds)}`)
  }
  assert.ok(bounds.text.every(label => label.size >= 14), JSON.stringify(bounds.text))
  return bounds
}

try {
  const response = await context.request.get(`${base}/api/projects`)
  assert.ok(response.ok())
  const projects = await response.json()
  const xiasha = projects.find(project => project.name.includes('下沙'))
  assert.ok(xiasha, 'load the Xiasha case into the local preview first')
  const fiveScheme = projects.find(project => project.name.includes('虚构钱塘案例'))
  const compactName = xiasha.name.split(/\s+·\s+/u)[0]

  for (const width of [1440, 1224, 1101, 966, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 800 })
    for (const route of ['', 'schemes', 'dashboard', 'chat']) {
      await page.goto(`${base}/projects${route ? `/${xiasha.id}/${route}` : ''}`)
      await expect(page.locator('h1')).toBeVisible()
      if (!route) {
        await expect(page.locator('.home-project-name').last()).toBeVisible()
        if (width >= 768) assert.equal(await page.locator('.home-table-scroll').evaluate(el => el.scrollWidth > el.clientWidth + 2), false, `project scrollbar at ${width}`)
        await expect(page.locator('.home-project-name').filter({ hasText: compactName })).toHaveAttribute('title', xiasha.name)
      } else {
        await expect(page.locator('.workbench-breadcrumb-project')).toHaveText(compactName)
        await expect(page.locator('.workbench-breadcrumb-project')).toHaveAttribute('title', xiasha.name)
      }
      if (route === 'schemes') {
        const row = page.locator('.styled-spec-table tr[data-row-key="unit_mix"]')
        await expect(row).toBeVisible()
        const cells = await row.locator('.spec-value').evaluateAll(values => values.map(element => ({ height: element.clientHeight, scroll: element.scrollHeight })))
        assert.ok(cells.length && cells.every(cell => cell.scroll <= cell.height + 1), JSON.stringify(cells))
        assert.ok((await page.locator('.scheme-col-header > strong').allTextContents()).every(name => !name.includes('教学推演') && !name.includes('演示自拟')))
      }
      if (route === 'dashboard') {
        await expect(page.getByLabel('方案比较工作台')).toHaveAttribute('aria-busy', 'false')
        measurements.push({ case: 'xiasha', width, ...await plotFits() })
        await page.getByRole('tab', { name: /比两套/ }).click()
        await plotFits()
        if (width === 390) { await page.locator('.comp-plot').scrollIntoViewIfNeeded(); await capture('pair-390') }
      }
      if (route === 'chat') {
        await expect(page.locator('.chat-starters button')).toHaveCount(4)
        await expect(page.locator('.chat-starters button').first()).toBeEnabled()
        await expect(page.locator('.chat-main > p[role="status"]')).toContainText(/项目情境建议|含 AI 建议/)
        await expect(page.getByLabel('假设的标准层重复率')).toHaveAttribute('placeholder', '如 0.85')
        const scores = await page.locator('.chat-rank-line strong').evaluateAll(elements => elements.map(el => el.getBoundingClientRect().right))
        assert.ok(scores.length && scores.every(right => Math.abs(right - scores[0]) < 1))
      }
      await noPageOverflow(`${route || 'projects'} at ${width}`)
      if ([1224, 390].includes(width)) { await page.evaluate(() => window.scrollTo(0, 0)); await capture(`fixed-${route || 'projects'}-${width}`) }
    }
  }
  checks.push('下沙四页在 1440/1224/1101/966/768/390/320px 无页面横溢；桌面项目表和各尺寸散点/差值图无多余滚动条')
  checks.push('项目简称保留完整标题，方案表头无演示后缀挤压，户型配比单元格自然增高')
  checks.push('取舍图标签无相互覆盖、无越界，缩放后文字仍至少14px；对话四个入口、排名得分对齐和参数提示可见')

  if (fiveScheme) {
    for (const width of [1224, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 800 })
      await page.goto(`${base}/projects/${fiveScheme.id}/dashboard`)
      await expect(page.getByLabel('方案比较工作台')).toHaveAttribute('aria-busy', 'false')
      measurements.push({ case: 'five-scheme', width, ...await plotFits() })
      await page.locator('.radar-panel').scrollIntoViewIfNeeded()
      await expect(page.locator('.radar-panel canvas')).toBeVisible()
      await page.waitForTimeout(450) // ECharts debounces its canvas resize; capture the final geometry.
      await page.locator('.radar-panel').screenshot({ path: fileURLToPath(new URL(`five-radar-${width}.png`, output)) })
      await noPageOverflow(`five scheme at ${width}`)
    }
    checks.push('五方案案例在 1224/768/390/320px 的散点标签和雷达图')
  }

  await page.setViewportSize({ width: 1224, height: 800 })
  await page.goto(`${base}/projects/${xiasha.id}/schemes`)
  await page.getByRole('button', { name: /导入与导出/ }).click()
  await expect(page.getByRole('menuitem', { name: '下载录入模板' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '导出方案' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '导入 Excel' })).toBeEnabled()
  await expect(page.getByRole('menuitem', { name: '导入 Excel' })).toBeInViewport()
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.getByRole('menuitem', { name: '导入 Excel' }).click()])
  await chooser.setFiles({ name: 'empty.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.alloc(0) })
  await expect(page.getByText('所选文件为空，请选择包含方案参数的 Excel 文件。', { exact: true })).toBeVisible()
  checks.push('导入导出菜单保留下载链接、文件选择及空文件校验，不写入案例')

  await page.getByRole('button', { name: /导入与导出/ }).click()
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('menuitem', { name: '导出方案' }).click()])
  const workbook = await readFile(await download.path())
  assert.ok(workbook.length > 1000)
  const created = await context.request.post(`${base}/api/projects`, { data: { name: '界面验收 · Excel 往返', params: xiasha.params } })
  assert.ok(created.ok())
  importProjectId = (await created.json()).id
  await page.goto(`${base}/projects/${importProjectId}/schemes`)
  await page.getByRole('button', { name: /导入与导出/ }).click()
  await expect(page.getByRole('menuitem', { name: '导入 Excel' })).toBeEnabled()
  await expect(page.getByRole('menuitem', { name: '导入 Excel' })).toBeInViewport()
  const [importChooser] = await Promise.all([page.waitForEvent('filechooser'), page.getByRole('menuitem', { name: '导入 Excel' }).click()])
  await importChooser.setFiles({ name: 'xiasha-roundtrip.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: workbook })
  await expect(page.getByText('已导入 3 个方案', { exact: true })).toBeVisible()
  const originalSchemes = await (await context.request.get(`${base}/api/projects/${xiasha.id}/schemes`)).json()
  const importedSchemes = await (await context.request.get(`${base}/api/projects/${importProjectId}/schemes`)).json()
  assert.deepEqual(importedSchemes.map(row => row.name), originalSchemes.map(row => row.name))
  await page.getByRole('button', { name: '开始评估', exact: true }).click()
  await expect(page.getByLabel('方案比较工作台')).toHaveAttribute('aria-busy', 'false')
  await context.request.delete(`${base}/api/projects/${importProjectId}`)
  importProjectId = undefined
  checks.push('通过新菜单导出下沙 Excel、在临时项目导入并评估；三套原始方案名完整保留，临时项目已清理')

  await page.goto(`${base}/projects/${xiasha.id}/chat`)
  const starter = page.locator('.chat-starters button').first()
  await expect(starter).toBeEnabled()
  await expect(page.locator('.chat-main > p[role="status"]')).toContainText(/项目情境建议|含 AI 建议/)
  const originalQuestion = await starter.getAttribute('title')
  const [request] = await Promise.all([page.waitForRequest(request => new URL(request.url()).pathname.endsWith('/plan')), starter.click()])
  assert.equal(request.postDataJSON().message, originalQuestion)
  const reply = page.locator('.chat-message.assistant').last()
  await expect(reply.locator('.section-heading .ant-tag').first()).toHaveText('已完成', { timeout: 60_000 })
  await expect(page.getByLabel('快捷问题')).toHaveCount(1)
  checks.push('快捷问题显示精简文案但发送完整原问题，真实本地 API 完成回答，建议区不重复')

  assert.deepEqual(errors, [])
  await writeFile(new URL('layout-acceptance.json', output), JSON.stringify({ checks, measurements, errors }, null, 2))
  console.log(JSON.stringify({ checks, pageErrors: errors }, null, 2))
} finally {
  if (importProjectId) await context.request.delete(`${base}/api/projects/${importProjectId}`)
  await browser.close()
}
