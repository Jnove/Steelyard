// 只引用生成文件的顶层类型，避免依赖可能使用中文标题的嵌套定义。
export type { ProjectParams } from './generated/ProjectParams'
export type { SchemeParams } from './generated/SchemeParams'
export type { EvalResult } from './generated/EvalResult'
export type { ProjectRead, ProjectRead as Project } from './generated/ProjectRead'
export type { ProjectCreate } from './generated/ProjectCreate'
export type { SchemeRead, SchemeRead as Scheme } from './generated/SchemeRead'
export type { SchemeCreate } from './generated/SchemeCreate'
export type { EvaluateResponse } from './generated/EvaluateResponse'
export type { RulesResponse } from './generated/RulesResponse'
export type { ImportResponse } from './generated/ImportResponse'

export interface DemoMetadata {
  mode: 'engine-fixture' | 'custom-topsis' | 'unsupported' | 'offline-crud'
  disclaimer: string
  fixture_id: string
  unavailable: string[]
  warnings: string[]
}
/** 离线模式额外提供界面提示，不替换生成的接口类型。 */
export type WithDemo<T> = T & { demo?: DemoMetadata }
import type { RankResponse as ServerRankResponse, RankedScheme as ServerRankedScheme } from './generated/RankResponse'
export type { AhpResult, TopsisResult, SensitivityResult, ParetoResult, RankAcceptabilityResult } from './generated/RankResponse'
export type WeightsUsed = ServerRankResponse['weights_used']
export interface RolesResponse { criteria: string[]; roles: WeightsUsed[]; custom_roles?: WeightsUsed[]; needs_review: string[] }
/** 只有离线自定义权重缺少完整快照时才允许稳健性与概率为 null。 */
export type RankedScheme = Omit<ServerRankedScheme, 'first_place_probability'> & { first_place_probability: number | null }
export type RankResponse = Omit<ServerRankResponse, 'ranking' | 'sensitivity' | 'rank_acceptability'> & {
  ranking: RankedScheme[]
  sensitivity: ServerRankResponse['sensitivity'] | null
  rank_acceptability: ServerRankResponse['rank_acceptability'] | null
  demo?: DemoMetadata
}
export interface RankInput { role?: string; weights?: number[] }
export interface FieldMetadata {
  name: string; label: string; description: string; unit: string; group: string; type: string; required: boolean
  essential?: boolean; enum?: (string | number | boolean | null)[]
  allow_custom_options?: boolean; empty_means_unknown?: boolean; custom?: boolean
  options?: Record<string, string> | (string | { value: string; label: string })[]
  constraints: { minimum?: number; maximum?: number; exclusiveMinimum?: number;
    exclusiveMaximum?: number; minLength?: number; maxLength?: number }
}
export interface FieldSchema { title: string; description: string; group_order: string[]; fields: FieldMetadata[] }
export interface SchemaResponse { project_params: FieldSchema; scheme_params: FieldSchema; eval_result: FieldSchema }
