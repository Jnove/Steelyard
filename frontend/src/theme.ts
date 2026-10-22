import type { ThemeConfig } from 'antd'

/** 筑衡的唯一视觉配置；图表、CSS 变量和组件共用。 */
export const tokens = {
  primary: '#327473', ink: '#243635', muted: '#657572', surface: '#ffffff',
  background: '#f8faf9', border: '#e4eae8', danger: '#ab3f46', success: '#327473',
  warning: '#8c611e', soft: '#dbf0ef', dangerSoft: '#fcf1f2', transparent: 'transparent',
  accent: '#9dd5d4', accentInk: '#243635', glowMint: '#9dd5d4', glowLilac: '#dbf0ef',
  // Categorical scheme identities; avoid using these colours to encode rank positions.
  chart: ['#327473', '#b65c19', '#4169b1', '#a34d83', '#887426'],
  dimensions: { quality: '#327473', structure: '#53748a', construction: '#986c3c', green: '#4d8278' },
  scene: { building: '#e4e9e4', facade: '#58867e', roof: '#fafcf8', plate: '#d1e9e1', edge: '#839b90', ground: '#e9eeeb', frame: '#bfd0c5', module: '#7c9891', inset: '#294b44', rooftop: '#c5d0c5' },
  glass: {
    fill: '#ffffff', content: '#ffffff', edge: '#e4eae8', blur: '0px',
    sheen: 'none', shadow: 'none', floatShadow: 'none',
  },
  font: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  mono: '"Cascadia Code", "SFMono-Regular", monospace',
  // Body and controls: 16px; secondary text and chart ticks: at least 14px.
  fontSize: 16, small: 14, medium: 16, large: 20, title: 28, display: 36,
  radius: 8, radiusSmall: 6, radiusFloat: 8, duration: 180,
}
/** 同一方案在录入表、雷达与比较视图中使用同一种颜色，不随排序改变。 */
export function schemeColor(id: string | number): string {
  const numeric = Number(id)
  const index = Number.isSafeInteger(numeric) && numeric > 0 ? numeric - 1
    : Array.from(String(id)).reduce((sum, char) => (sum * 31 + char.charCodeAt(0)) >>> 0, 0)
  return tokens.chart[index % tokens.chart.length]
}
export const theme: ThemeConfig = {
  token: { colorPrimary: tokens.primary, colorInfo: tokens.primary, colorSuccess: tokens.success,
    colorWarning: tokens.warning, colorError: tokens.danger, colorText: tokens.ink,
    colorTextSecondary: tokens.muted, colorBgLayout: tokens.background, colorBorder: tokens.border,
    borderRadius: tokens.radiusSmall, borderRadiusLG: tokens.radius, fontSize: tokens.fontSize, fontSizeSM: tokens.small, fontFamily: tokens.font, controlHeight: 40 },
  components: {
    Layout: { headerBg: tokens.transparent, siderBg: tokens.transparent },
    Slider: { trackBg: tokens.primary, handleColor: tokens.primary },
    Button: { primaryShadow: 'none', defaultShadow: 'none', controlHeightLG: 44 },
    Table: { headerBg: tokens.surface, rowHoverBg: tokens.background, borderColor: tokens.border, fontSize: tokens.fontSize, cellPaddingBlock: 14 },
    Segmented: { trackBg: tokens.background, itemSelectedBg: tokens.surface },
    Modal: { borderRadiusLG: 10 }, Drawer: { paddingLG: 24 },
  },
}
export function installTheme(): void {
  const colors = ['primary','ink','muted','surface','background','border','danger','success','warning','soft','dangerSoft','transparent','accent','accentInk','glowMint','glowLilac'] as const
  for (const key of colors) document.documentElement.style.setProperty('--color-' + key, tokens[key])
  for (const [key,value] of Object.entries(tokens.dimensions)) document.documentElement.style.setProperty('--dimension-' + key, value)
  for (const [key,value] of Object.entries(tokens.glass)) document.documentElement.style.setProperty('--glass-' + key, value)
  for (const key of ['fontSize','small','medium','large','title','display','radius','radiusSmall','radiusFloat'] as const)
    document.documentElement.style.setProperty('--' + key, tokens[key] + 'px')
  document.documentElement.style.setProperty('--font-body', tokens.font)
  document.documentElement.style.setProperty('--font-mono', tokens.mono)
}
