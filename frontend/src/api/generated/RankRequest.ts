/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 角色键，先查 rules/weights.yaml（government / developer / contractor / resident），再查运行期自定义的权重模板（可用 custom:<id> 或模板名）
 */
export type Role = string | null;
/**
 * 直接给权重，4 个非负数，顺序是 quality / structure / construction / green；会自动归一化
 */
export type Weights = number[] | null;
/**
 * 4×4 两两比较矩阵，走 AHP 解权重
 */
export type PairwiseMatrix = number[][] | null;
/**
 * 是否让存在 error 级硬约束未通过的方案参与排名。默认 false：它们不参与排序，但会在 excluded 里列出并注明原因
 */
export type IncludeNoncompliant = boolean;
/**
 * 是否把 what-if 副本一并纳入排序（需要 evaluate 时也带上了它们）
 */
export type IncludeWhatif = boolean;
/**
 * 名次概率的抽样组数
 */
export type MonteCarloSamples = number;
/**
 * Dirichlet 集中度；越大越贴近基准权重
 */
export type MonteCarloConcentration = number;
/**
 * 蒙特卡洛随机种子；同 seed 结果完全可复现
 */
export type Seed = number;

/**
 * role、weights、pairwise_matrix 必须且只能提供一项
 */
export interface RankRequest {
  role?: Role;
  weights?: Weights;
  pairwise_matrix?: PairwiseMatrix;
  include_noncompliant?: IncludeNoncompliant;
  include_whatif?: IncludeWhatif;
  monte_carlo_samples?: MonteCarloSamples;
  monte_carlo_concentration?: MonteCarloConcentration;
  seed?: Seed;
}
