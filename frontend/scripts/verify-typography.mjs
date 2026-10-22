/** Readability against the isolated local preview. TYPOGRAPHY_PHASE=before records an optional heading baseline. */
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect as baseExpect } from '@playwright/test'

const expect = baseExpect.configure({ timeout: 20_000 })
const base = process.env.WORKBENCH_URL ?? 'http://127.0.0.1:5182'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const phase = process.env.TYPOGRAPHY_PHASE === 'before' ? 'before' : 'after'
const output = new URL(`../../backend/data/homepage-ui/typography/${phase}/`, import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
const page = await context.newPage()
const errors = [], checks = [], samples = []
page.on('pageerror', error => errors.push(error.message))
const audit = async name => {
  const sample = await page.evaluate(() => {
    const text = [...document.querySelectorAll('body *')].flatMap(element => {
      if (element.closest('script,style,defs,title,option,h1,h2,h3,h4,h5,h6,[aria-hidden="true"],.ant-slider-handle')) return []
      const content = [...element.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent.trim()).join(' ').trim()
      const rect = element.getBoundingClientRect(), style = getComputedStyle(element)
      if (!content || rect.width < 1 || rect.height < 1 || style.visibility === 'hidden' || style.display === 'none') return []
      const scale = element instanceof SVGGraphicsElement ? Math.abs(element.getScreenCTM()?.a ?? 1) : 1
      return [{ text: content.slice(0, 65), selector: element.tagName + '.' + [...element.classList].join('.'), size: parseFloat(style.fontSize) * scale }]
    })
    return {
      width: innerWidth, overflow: document.documentElement.scrollWidth > innerWidth,
      headings: [...document.querySelectorAll('h1,h2,h3')].map(element => ({ text: element.textContent, size: getComputedStyle(element).fontSize })),
      small: text.filter(item => item.size < 13.9), total: text.length,
    }
  })
  samples.push({ name, ...sample })
  if (phase === 'after') {
    assert.equal(sample.overflow, false, `${name}: page horizontal overflow`)
    assert.deepEqual(sample.small, [], `${name}: text smaller than 14px`)
  }
  await page.screenshot({ path: fileURLToPath(new URL(`${name}.png`, output)), fullPage: false })
}
try {
  for (const width of [1440, 1224, 768, 390, 320]) {
    await page.setViewportSize({ width, height: width === 1224 ? 613 : width < 768 ? 844 : 900 })
    for (const [route, name] of [['/', 'landing'], ['/projects', 'projects'], ['/projects/1/schemes', 'schemes'], ['/projects/1/dashboard', 'dashboard'], ['/projects/1/chat', 'chat']]) {
      await page.goto(`${base}${route}`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      if (name === 'landing') await expect(page.getByRole('region', { name: '建筑体量展台' })).toHaveAttribute('data-renderer', /webgl|static/)
      if (name === 'projects') await expect(page.locator('.home-project-name').first()).toBeVisible()
      if (name === 'schemes') await expect(page.locator('.styled-spec-table tbody tr.ant-table-row').first()).toBeVisible()
      if (name === 'dashboard') await expect(page.getByLabel('决策建议简报')).toHaveAttribute('aria-busy', 'false')
      if (name === 'chat') {
        await expect(page.getByLabel('输入追问')).toBeVisible()
        await expect(page.locator('.chat-side .ant-progress').first()).toBeVisible()
      }
      await audit(`${name}-${width}`)
    }
    checks.push(`${width}px 首页、项目总览、方案录入、对比看板、对话页`)
  }
  if (phase === 'after') {
    const baseline = await readFile(new URL('../before/report.json', output), 'utf8').then(JSON.parse).catch(error => {
      if (error.code === 'ENOENT') return undefined
      throw error
    })
    if (baseline) {
      for (const sample of samples) {
        const before = baseline.samples.find(item => item.name === sample.name)
        assert.deepEqual(sample.headings.filter(heading => heading.text.trim()), before.headings.filter(heading => heading.text.trim()), `${sample.name}: heading typography must remain unchanged`)
      }
      checks.push('标题与小标题字号保持不变')
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${base}/projects/1/dashboard`)
    await expect(page.getByLabel('决策建议简报')).toHaveAttribute('aria-busy', 'false')
    await page.locator('.decision-role-options label').filter({ hasText: '自定义' }).click()
    await expect(page.getByRole('slider')).toHaveCount(4)
    await expect(page.getByLabel('决策建议简报')).toHaveAttribute('aria-busy', 'false')
    await audit('custom-390')
    await page.goto(`${base}/projects/1/schemes`)
    await page.getByRole('button', { name: '添加方案', exact: true }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.locator('.ant-modal')).not.toHaveClass(/(?:enter|appear)-(?:active|prepare)/)
    await audit('scheme-form-390')
    checks.push('自定义权重、弹窗表单字号及窄屏显示')
  }
  assert.deepEqual(errors, [])
  const report = { phase, checks, samples, errors }
  await writeFile(new URL('report.json', output), JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ phase, checks, smallText: samples.map(({ name, small }) => ({ name, count: small.length })) }, null, 2))
} finally { await browser.close() }
