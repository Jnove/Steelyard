import type { SchemeParams } from '../api/types'

export interface BuildingVolume { x: number; z: number; width: number; depth: number; height: number; floors: number }
export interface BuildingModel {
  volumes: BuildingVolume[]
  capped: boolean
  missing: string[]
}

const positive = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value > 0
const countValue = (value: unknown): value is number => positive(value) && Number.isSafeInteger(value)
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

/** 有上限的示意映射；位置是展示排布，绝不表示真实总平面或 BIM。 */
export function buildingModel(params: SchemeParams): BuildingModel {
  const missing = [!countValue(params.buildings) && '楼栋数', !countValue(params.floors) && '层数'].filter((item): item is string => Boolean(item))
  if (missing.length) return { volumes: [], capped: false, missing }
  const count = Math.max(1, Math.min(12, Math.floor(params.buildings!)))
  const floors = Math.max(1, Math.min(48, Math.floor(params.floors!)))
  const columns = Math.ceil(Math.sqrt(count))
  const rows = Math.ceil(count / columns)
  // 未填层高时按层数显示概念比例，不补写工程层高；平面同理。
  const height = clamp(floors * (positive(params.floor_height) ? clamp(params.floor_height, 2, 5) * .045 : .135), .45, 4.6)
  const width = positive(params.footprint) ? clamp(Math.sqrt(params.footprint / params.buildings!) * .044, .62, 1.32) : .98
  const depth = width * .74
  return {
    volumes: Array.from({ length: count }, (_, index) => ({
      x: (index % columns - (columns - 1) / 2) * 1.64,
      z: (Math.floor(index / columns) - (rows - 1) / 2) * 1.50,
      width, depth, height, floors,
    })),
    capped: params.buildings! > 12 || params.floors! > 48 || (positive(params.floor_height) && (params.floor_height < 2 || params.floor_height > 5)),
    missing: [],
  }
}
