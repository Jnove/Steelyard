/** Read-only acceptance of the local dashboard's probability display and scheme identities. */
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })
const base = process.env.WORKBENCH_URL ?? 'http://127.0.0.1:5182'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const output = new URL('../../backend/data/homepage-ui/rank-distribution/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1224, height: 613 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = [], checks = []
page.on('pageerror', error => errors.push(error.message))
const distribution = page.getByLabel('方案获得各名次的概率')
const settled = () => expect(page.getByLabel('决策建议简报')).toHaveAttribute('aria-busy', 'false')
const percent = value => (value * 100).toFixed(1).replace(/\.0$/, '') + '%'
try {
  const ranked = page.waitForResponse(response => /\/api\/projects\/5\/rank$/.test(response.url()) && response.request().method() === 'POST')
  await page.goto(`${base}/projects/5/dashboard`)
  const data = await (await ranked).json()
  await settled()
  await expect(distribution).toBeVisible()
  const colours = new Map()
  for (const [index, id] of data.scheme_order.entries()) {
    const row = distribution.locator(`li[data-scheme="${id}"]`)
    const scheme = data.ranking.find(scheme => scheme.scheme_id === id)
    await expect(row.locator('.probability-scheme strong')).toHaveText(scheme.scheme_name)
    assert.deepEqual(await row.locator('[data-probability]').evaluateAll(cells => cells.map(cell => Number(cell.dataset.probability))), data.rank_acceptability.probabilities[index])
    assert.deepEqual(await row.locator('dd > .numeric').allTextContents(), data.rank_acceptability.probabilities[index].map(percent))
    const colour = await row.locator('.probability-scheme > i').evaluate(element => getComputedStyle(element).backgroundColor)
    colours.set(id, colour)
    await expect(page.locator(`.ranking-row[data-scheme="${id}"] .rank-track > div`)).toHaveCSS('background-color', colour)
    const plot = page.locator('.comp-point').filter({ has: page.locator('title').filter({ hasText: scheme.scheme_name }) })
    await expect(plot.locator('.comp-bead')).toHaveCSS('stroke', colour)
  }
  assert.equal(new Set(colours.values()).size, data.scheme_order.length)
  checks.push('项目5的全部概率按 scheme_order 正确映射，零与100%直接显示；五种方案颜色一致且各不相同')
  const before = new Map(colours)
  await page.locator('.decision-role-options label').filter({ hasText: '住户' }).click()
  await settled()
  for (const [id, colour] of before) await expect(distribution.locator(`li[data-scheme="${id}"] .probability-scheme > i`)).toHaveCSS('background-color', colour)
  checks.push('切换视角重新排名后，同一方案仍保留原颜色')
  await page.locator('.decision-role-options label').filter({ hasText: '政府' }).click()
  await settled()

  for (const [width, height] of [[1440, 900], [1224, 613], [768, 1024], [390, 844], [320, 568]]) {
    await page.setViewportSize({ width, height })
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(page.locator('.home-skip')).not.toBeInViewport()
    await page.screenshot({ path: fileURLToPath(new URL(`decision-bar-${width}.png`, output)) })
    await distribution.screenshot({ path: fileURLToPath(new URL(`probability-${width}.png`, output)) })
    await expect(page.locator('.home-skip')).not.toBeInViewport()
    await page.screenshot({ path: fileURLToPath(new URL(`probability-viewport-${width}.png`, output)) })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `page overflow at ${width}`)
    const clipped = await distribution.evaluate(element => [...element.querySelectorAll('.probability-scheme strong, .probability-ranks dt, .probability-ranks .numeric')].filter(text => {
      const range = document.createRange(); range.selectNodeContents(text)
      const rect = range.getBoundingClientRect(), container = text.closest('.probability-schemes > li').getBoundingClientRect()
      return rect.left < container.left - 1 || rect.right > container.right + 1 || text.scrollWidth > text.clientWidth + 1
    }).map(element => element.textContent))
    assert.deepEqual(clipped, [], `clipped distribution labels at ${width}`)
    await expect(page.locator('.role-bar')).toHaveCSS('border-left-width', '0px')
    await expect(page.locator('.role-bar')).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  }
  checks.push('1440/1224/768/390/320px 的完整名称和百分比无遮挡；视角栏无大底色与粗侧边')
  await page.locator('.decision-role-options label').filter({ hasText: '自定义' }).click()
  await settled()
  await expect(page.getByLabel('自定义评价权重')).toBeVisible()
  assert.ok(await page.evaluate(() => document.querySelector('.custom-weights-panel').getBoundingClientRect().bottom < document.querySelector('.executive-summary-card').getBoundingClientRect().top))
  checks.push('自定义权重仍在推荐方案前展开')
  assert.deepEqual(errors, [])
  await writeFile(new URL('report.json', output), JSON.stringify({ checks, errors, data }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks }, null, 2))
} finally { await browser.close() }
