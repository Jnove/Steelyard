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
export interface AhpResult {
  weights: number[]; lambda_max: number; ci: number; cr: number; ri: number; consistent: boolean
}
export interface WeightsUsed {
  source: 'role' | 'weights' | 'pairwise_matrix'
  criteria: string[]; weights: number[]; role?: string | null; role_name?: string | null
  note: string; ahp?: AhpResult | null; consistency_warning?: string | null
}
export interface RolesResponse { criteria: string[]; roles: WeightsUsed[]; needs_review: string[] }
export interface TopsisResult {
  schemes: { index: number; closeness: number; distance_to_best: number; distance_to_worst: number; rank: number }[]
  ideal_best: number[]; ideal_worst: number[]; weights: number[]
}
export interface SensitivityResult {
  baseline_weights: number[]; baseline_ranks: number[]; baseline_top_index: number | null
  cells: { criterion: string; criterion_index: number; delta: number; weights: number[];
    top_index: number | null; ranks: number[]; rank_changed: boolean; top_changed: boolean }[]
  flip_points: { criterion: string; criterion_index: number; baseline_weight: number;
    flip_weight: number | null; new_top_index: number | null }[]
}
export interface ParetoResult { non_dominated: number[]; dominated_by: Record<string, number[]> }
export interface RankAcceptabilityResult {
  probabilities: number[][]; first_place_probability: number[]; samples: number; concentration: number; seed: number
}
export interface RankedScheme {
  scheme_id: string; scheme_name: string; dimension_scores: number[]; closeness: number; rank: number
  is_non_dominated: boolean; dominated_by: string[]
  /** 仅在离线自定义权重没有精确引擎快照时为 null。 */
  first_place_probability: number | null
}
/** 对齐 T4 草案；离线模式未提供的分析明确为 null。 */
export interface RankResponse {
  project_id: number; criteria: string[]; weights_used: WeightsUsed
  /** TOPSIS、帕累托、敏感性和概率数组的输入顺序，不是名次顺序。 */
  participant_ids?: string[]
  ranking: RankedScheme[]
  excluded: { scheme_id: string; scheme_name: string; reason: string; failed_rules: string[] }[]
  topsis: TopsisResult; sensitivity: SensitivityResult | null; pareto: ParetoResult
  rank_acceptability: RankAcceptabilityResult | null; elapsed_ms: number
  demo?: DemoMetadata
}
export interface RankInput { role?: string; weights?: number[] }
export interface FieldMetadata {
  name: string; label: string; description: string; unit: string; group: string; type: string; required: boolean
  essential?: boolean; enum?: (string | number | boolean | null)[]
  options?: Record<string, string> | (string | { value: string; label: string })[]
  constraints: { minimum?: number; maximum?: number; exclusiveMinimum?: number;
    exclusiveMaximum?: number; minLength?: number; maxLength?: number }
}
export interface FieldSchema { title: string; description: string; group_order: string[]; fields: FieldMetadata[] }
export interface SchemaResponse { project_params: FieldSchema; scheme_params: FieldSchema; eval_result: FieldSchema }
