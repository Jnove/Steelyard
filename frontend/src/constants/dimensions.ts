import { tokens } from '../theme'
export const dimensions = [
  { key: 'quality', label: '居住品质', short: '品质', color: tokens.dimensions.quality },
  { key: 'structure', label: '结构安全', short: '结构', color: tokens.dimensions.structure },
  { key: 'construction', label: '施工友好', short: '施工', color: tokens.dimensions.construction },
  { key: 'green', label: '绿色低碳', short: '绿色', color: tokens.dimensions.green },
] as const
export type DimensionKey = typeof dimensions[number]['key']
export const isMock = import.meta.env.VITE_USE_MOCK === 'true'
