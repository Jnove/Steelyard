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
  // 体量展台：暖白模型 + 深青玻璃 + 沙色底板；SVG 回退与 WebGL 共用同一组颜色。
  scene: {
    building: '#e7ddc9', facade: '#2f5b55', roof: '#fbf7ee', plate: '#d7e3d8', edge: '#9fae9f',
    ground: '#e9ece4', frame: '#d9d1c0', module: '#7f8c81', inset: '#264a43', rooftop: '#c9c2b2',
    body: '#e7ddc9', bodyCool: '#e3ddcf', bodyWarm: '#e9dcc3', frameBody: '#e7e0d0', neutralBody: '#f2ede2',
    stone: '#ddd4c1', stoneEdge: '#c4baa6', terrace: '#d7e3d8', terraceEdge: '#bccbbd',
    board: '#d2c8b6', band: '#c9c0ae', roofDeck: '#b9b2a2', louver: '#4f584f',
    glass: '#345a5e', glassDark: '#1b2f2e', glassLight: '#6f958c',
    glassModular: '#5f8c8c', glassFrame: '#5d878b',
    skyTop: '#fff7e7', skyHorizon: '#e6efea', skyGround: '#c9c1b1',
    metal: '#8e8474', metalDark: '#4c4538', plant: '#7f9b88', plantAlt: '#6a8a76',
    trunk: '#8a7157', shadow: '#2c4a43', paper: '#fdfaf2', warm: '#d97757',
  },
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
