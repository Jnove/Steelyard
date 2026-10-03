/** 使用独立浏览器上下文验证离线完整流程，并保存截图与交互录屏。 */
import { chromium, expect } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../', import.meta.url))
const output = path.join(root, 'docs/screenshots/t7')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ channel: process.env.T7_BROWSER ?? 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width:1366,height:768 },
  recordVideo: { dir:path.join(root,'backend/data/t7-videos'),size:{width:1366,height:768} } })
const page = await context.newPage()
page.setDefaultTimeout(20_000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
const base = process.env.T7_URL ?? 'http://127.0.0.1:5177'
const capture = async name => {
  await page.waitForTimeout(700)
  await page.screenshot({ path:path.join(output,name+'.png'),fullPage:true })
}
try {
  await page.goto(base+'/projects')
  await expect(page.getByRole('link',{name:'杭州钱塘 · 保障性租赁住房 · 虚构示例项目',exact:true})).toBeVisible()
  await capture('projects-1366')
  await page.getByRole('link',{name:'管理方案',exact:true}).click()
  await expect(page.getByRole('button',{name:'开始评估',exact:true})).toBeEnabled()
  await capture('schemes-1366')
  await page.locator('input[type=file]').setInputFiles(path.join(root,'frontend/src/mocks/fixtures/demo-invalid.xlsx'))
  await expect(page.getByText('Excel 导入失败，请修正全部问题后重试')).toBeVisible()
  await expect(page.locator('.ant-alert-error li')).toHaveCount(2)
  await page.getByRole('button',{name:'开始评估',exact:true}).click()
  await expect(page.locator('.ranking-row')).toHaveCount(4)
  await expect(page.locator('.excluded-row')).toContainText('B 不合规')
  await capture('dashboard-1366')
  const initial = await page.locator('.ranking-row').first().innerText()
  await page.getByText('施工总包',{exact:true}).click()
  await expect(page.locator('.weight-label').nth(2)).toContainText('53.8')
  await page.waitForTimeout(900)
  const contractor = await page.locator('.ranking-row').first().innerText()
  if (initial === contractor) throw new Error('角色切换后贴近度未更新')
  await page.getByText('住户',{exact:true}).click()
  await expect(page.locator('.weight-label').first()).toContainText('48.3')
  await page.waitForTimeout(900)
  await page.getByRole('slider',{name:'居住品质权重'}).focus()
  await page.keyboard.press('End')
  await expect(page.locator('.ranking-row').first()).toContainText('E 被支配')
  await page.waitForTimeout(900)
  await page.getByText('政府',{exact:true}).click()
  await expect(page.locator('.ranking-row').first()).toContainText('C MiC 高标准化')
  await page.locator('.score-button').first().click()
  await expect(page.getByRole('dialog')).toContainText('原始输入')
  await expect(page.getByRole('dialog')).toContainText('依据')
  await capture('trace-1366')
  await page.keyboard.press('Escape')
  await page.setViewportSize({width:1920,height:1080})
  await capture('dashboard-1920')
  for (const width of [320,375,414,768]) {
    await page.setViewportSize({width,height:900})
    const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
    if (overflow) throw new Error('看板横向溢出：'+width)
  }
  await page.setViewportSize({width:1366,height:768})
  await page.locator('nav a[href$="/chat"]').click()
  await expect(page.getByRole('button',{name:'生成 Markdown 报告',exact:true})).toBeEnabled()
  await page.getByLabel('快捷问题').getByRole('button').first().click()
  await expect(page.locator('.chat-message.assistant').last().locator('.section-heading .ant-tag').first()).toHaveText('已完成',{timeout:30_000})
  await page.locator('.chat-feed').evaluate(node => { node.scrollTop = 0 })
  await capture('chat-1366')
  const rule = page.getByRole('button',{name:/查看规则 .* 的依据/}).first()
  await rule.click()
  await expect(page.getByRole('dialog')).toContainText('依据')
  await page.keyboard.press('Escape')
  await page.getByRole('button',{name:'生成 Markdown 报告',exact:true}).click()
  const downloadButton = page.getByRole('button',{name:'下载 Markdown（.md）',exact:true})
  await expect(downloadButton).toBeVisible({timeout:45_000})
  const downloadWait = page.waitForEvent('download')
  await downloadButton.click()
  const download = await downloadWait
  await download.saveAs(path.join(output,'demo-report.md'))
  await page.setViewportSize({width:1920,height:1080})
  await capture('chat-1920')
  await page.getByRole('link',{name:'项目总览',exact:false}).click()
  await page.getByRole('button',{name:'新建项目',exact:true}).click()
  await page.getByRole('textbox',{name:'项目名称'}).fill('T7 新建导入验收')
  await page.getByRole('button',{name:'保存项目',exact:true}).click()
  await expect(page.getByRole('heading',{name:'T7 新建导入验收'})).toBeVisible()
  await page.locator('input[type=file]').setInputFiles(path.join(root,'frontend/src/mocks/fixtures/demo-import.xlsx'))
  await expect(page.getByRole('button',{name:'开始评估',exact:true})).toBeEnabled()
  await page.getByRole('button',{name:'开始评估',exact:true}).click()
  await expect(page.locator('.ranking-row')).toHaveCount(4)
  if (errors.length) throw new Error(errors.join('\n'))
  await writeFile(path.join(output,'verification.json'),JSON.stringify({
    viewports:['1366x768','1920x1080'],mobileWidths:[320,375,414,768],
    flows:['项目列表','全部导入错误','评估与排名','角色更新贴近度','滑杆触发换位','评分溯源','流式追问','规则引用','报告下载','新建项目导入评估'],
    consoleErrors:errors,roleOrderNote:'当前四角色名次相同；100% 品质权重触发 E 方案升至第一。',
  },null,2))
  console.log('界面完整流程通过；截图、报告和录屏已保存。')
} finally {
  await context.close()
  await page.video()?.saveAs(path.join(output,'roles-and-weights.webm'))
  await browser.close()
}
