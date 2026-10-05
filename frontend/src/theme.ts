import type { ThemeConfig } from 'antd'

/** 筑衡的唯一视觉配置；图表、CSS 变量和组件共用。 */
export const tokens = {
  primary: '#2f5bb7', ink: '#182940', muted: '#64748b', surface: '#ffffff',
  background: '#f3f5f8', border: '#dce3ed', danger: '#b83c42', success: '#22765f',
  warning: '#996619', soft: '#eaf0fb', dangerSoft: '#fff0ef', transparent: 'transparent',
  chart: ['#2f5bb7', '#b96b30', '#237e78', '#786099', '#7b8799'],
  dimensions: { quality: '#2f5bb7', structure: '#786099', construction: '#b96b30', green: '#237e78' },
  font: '"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  mono: '"Cascadia Code", "SFMono-Regular", monospace',
  fontSize: 14, small: 12, medium: 16, large: 20, title: 28, display: 36,
  radius: 8, radiusSmall: 4, duration: 360,
}
export const theme: ThemeConfig = {
  token: { colorPrimary: tokens.primary, colorInfo: tokens.primary, colorSuccess: tokens.success,
    colorWarning: tokens.warning, colorError: tokens.danger, colorText: tokens.ink,
    colorTextSecondary: tokens.muted, colorBgLayout: tokens.background, colorBorder: tokens.border,
    borderRadius: tokens.radius, fontSize: tokens.fontSize, fontFamily: tokens.font, controlHeight: 38 },
  components: { Layout: { headerBg: tokens.surface, siderBg: tokens.surface }, Slider: { trackBg: tokens.primary } },
}
export function installTheme(): void {
  const colors = ['primary','ink','muted','surface','background','border','danger','success','warning','soft','dangerSoft','transparent'] as const
  for (const key of colors) document.documentElement.style.setProperty('--color-' + key, tokens[key])
  for (const [key,value] of Object.entries(tokens.dimensions)) document.documentElement.style.setProperty('--dimension-' + key, value)
  for (const key of ['fontSize','small','medium','large','title','display','radius','radiusSmall'] as const)
    document.documentElement.style.setProperty('--' + key, tokens[key] + 'px')
  document.documentElement.style.setProperty('--font-body', tokens.font)
  document.documentElement.style.setProperty('--font-mono', tokens.mono)
}
