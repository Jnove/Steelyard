/** Check scroll locking against an isolated local mock app. */
import assert from 'node:assert/strict'
import { chromium, expect } from '@playwright/test'

const base = process.env.TRACE_URL ?? 'http://127.0.0.1:5186'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const position = page => page.evaluate(() => ({
  y: window.scrollY,
  bodyY: document.body.scrollTop,
  height: document.documentElement.scrollHeight,
  overflow: [document.documentElement, document.body].map(el => {
    const style = getComputedStyle(el)
    return [style.overflowX, style.overflowY]
  }),
  buttonTop: document.querySelector('.score-button').getBoundingClientRect().top,
}))
try {
  for (const viewport of [{ width: 1280, height: 720 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, reducedMotion: 'reduce' })
    const page = await context.newPage()
    await page.goto(`${base}/projects/1/schemes`)
    await page.getByRole('button', { name: '开始评估', exact: true }).click()
    await expect(page.locator('.ranking-row').first()).toBeVisible()
    await page.locator('.dashboard-scheme-details > summary').click()
    const trigger = page.locator('.score-button').first()
    await trigger.scrollIntoViewIfNeeded()
    await page.evaluate(() => window.scrollBy(0, document.querySelector('.score-button').getBoundingClientRect().top - 180))
    const before = await position(page)
    assert.ok(before.y > 500, 'Start well below the top of the page')
    for (let opening = 0; opening < 2; opening++) {
      await trigger.click()
      await expect(page.locator('.ant-drawer-body .trace-item').first()).toBeVisible()
      const during = await position(page)
      console.log(JSON.stringify({ viewport, opening, before, during }))
      assert.ok(Math.abs(during.y - before.y) <= 1, 'Opening drawer preserves page scroll')
      assert.ok(Math.abs(during.buttonTop - before.buttonTop) <= 1, 'Background content stays in place')
      await page.locator('.ant-drawer-body').evaluate(el => { el.scrollTop = 300 })
      assert.equal((await position(page)).y, during.y, 'Drawer scroll is independent')
      await page.keyboard.press('Escape')
      await expect(page.locator('.ant-drawer-content-wrapper')).not.toBeVisible()
      await expect(trigger).toBeFocused()
      assert.ok(Math.abs((await position(page)).y - before.y) <= 1, 'Closing drawer preserves page scroll')
    }
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No horizontal overflow')
    await context.close()
  }
} finally { await browser.close() }
