import type { ThemeConfig } from 'antd'

/** 筑衡的唯一视觉配置；图表、CSS 变量和组件共用。 */
export const tokens = {
  primary: '#075e49', ink: '#17332d', muted: '#526962', surface: '#ffffff',
  background: '#f4f8f6', border: '#d7e2dc', danger: '#ad3648', success: '#09694b',
  warning: '#8c5b15', soft: '#e2f3eb', dangerSoft: '#fff0f1', transparent: 'transparent',
  accent: '#1BE49A', accentInk: '#073d2c', glowMint: '#1BE49A', glowLilac: '#C8A7DD',
  chart: ['#08775b', '#8370ae', '#b27532', '#427898', '#637065'],
  dimensions: { quality: '#08775b', structure: '#8370ae', construction: '#a76d29', green: '#427898' },
  scene: { building: '#eaf6ef', facade: '#99d9c5', roof: '#fcfffd', plate: '#d1e9e1', edge: '#739a8b', ground: '#e9eeeb' },
  glass: {
    fill: 'rgba(255, 255, 255, .30)', content: 'rgba(255, 255, 255, .76)',
    edge: 'rgba(255, 255, 255, .90)', blur: '22px',
    sheen: 'linear-gradient(135deg, rgba(255,255,255,.82), rgba(255,255,255,.06) 43%, rgba(255,255,255,.42))',
    shadow: '0 3px 7px rgba(40, 73, 59, .07), 0 24px 58px -16px rgba(38, 67, 58, .19), inset 0 1px 0 rgba(255,255,255,.96), inset 0 -1px 0 rgba(255,255,255,.36)',
    floatShadow: '0 2px 5px rgba(47, 77, 65, .09), 0 32px 60px -16px rgba(44, 72, 60, .24), inset 0 1px 0 rgba(255,255,255,.97), inset 1px 0 0 rgba(255,255,255,.64)',
  },
  font: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  mono: '"Cascadia Code", "SFMono-Regular", monospace',
  fontSize: 14, small: 12, medium: 16, large: 20, title: 28, display: 36,
  radius: 22, radiusSmall: 10, radiusFloat: 28, duration: 360,
}
export const theme: ThemeConfig = {
  token: { colorPrimary: tokens.primary, colorInfo: tokens.primary, colorSuccess: tokens.success,
    colorWarning: tokens.warning, colorError: tokens.danger, colorText: tokens.ink,
    colorTextSecondary: tokens.muted, colorBgLayout: tokens.background, colorBorder: tokens.border,
    borderRadius: tokens.radiusSmall, borderRadiusLG: tokens.radius, fontSize: tokens.fontSize, fontFamily: tokens.font, controlHeight: 44 },
  components: {
    Layout: { headerBg: tokens.transparent, siderBg: tokens.transparent },
    Slider: { trackBg: tokens.primary, handleColor: tokens.primary },
    Button: { primaryShadow: '0 6px 16px rgba(7,94,73,.18)', defaultShadow: '0 2px 3px rgba(38,67,58,.04)' },
    Table: { headerBg: '#eef5f1', rowHoverBg: '#edf6f1', borderColor: '#e0e8e2' },
    Segmented: { trackBg: 'rgba(224,235,229,.68)', itemSelectedBg: '#ffffff' },
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
