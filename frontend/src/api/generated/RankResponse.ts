/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 项目 id
 */
export type ProjectId = number;
/**
 * 所有分析数组的方案 ID 顺序；下标对应此列表，ranking 按名次展示
 */
export type SchemeOrder = string[];
/**
 * 准则（维度）顺序
 */
export type Criteria = string[];
/**
 * 权重来源
 */
export type Source = "role" | "weights" | "pairwise_matrix";
/**
 * 准则顺序，固定为四个维度
 */
export type Criteria1 = string[];
/**
 * 归一化后的权重，和为 1
 */
export type Weights = number[];
/**
 * 来源是 role 时的角色键
 */
export type Role = string | null;
/**
 * 来源是 role 时的角色中文名
 */
export type RoleName = string | null;
/**
 * 该角色模板是否来自运行期自定义（未进入 git、不参与 CI 校验）；报告里应据此提示读者
 */
export type IsCustom = boolean;
/**
 * 角色模板的说明；自定义权重时为空
 */
export type Note = string;
/**
 * 归一化后的权重，和为 1，顺序同 CRITERION_ORDER
 */
export type Weights1 = number[];
/**
 * 最大特征值 λmax
 */
export type LambdaMax = number;
/**
 * 一致性指标 CI = (λmax − n) / (n − 1)
 */
export type Ci = number;
/**
 * 一致性比率 CR = CI / RI；n ≤ 2 时记 0
 */
export type Cr = number;
/**
 * 本阶数对应的随机一致性指标 RI
 */
export type Ri = number;
/**
 * CR < 0.1 才算通过一致性检验
 */
export type Consistent = boolean;
/**
 * CR ≥ 0.1 时的中文提示；通过时为 null
 */
export type ConsistencyWarning = string | null;
/**
 * 方案 id
 */
export type SchemeId = string;
/**
 * 方案名称
 */
export type SchemeName = string;
/**
 * 四个维度得分，顺序同 criteria
 */
export type DimensionScores = number[];
/**
 * TOPSIS 贴近度，0–1
 */
export type Closeness = number;
/**
 * 名次，从 1 开始；并列时名次相同
 */
export type Rank = number;
/**
 * 是否为帕累托非劣方案
 */
export type IsNonDominated = boolean;
/**
 * 支配它的方案 id；非劣方案为空
 */
export type DominatedBy = string[];
/**
 * 蒙特卡洛下排第一的概率
 */
export type FirstPlaceProbability = number;
/**
 * 参与排序的方案，按名次升序
 */
export type Ranking = RankedScheme[];
/**
 * 方案 id
 */
export type SchemeId1 = string;
/**
 * 方案名称
 */
export type SchemeName1 = string;
/**
 * 为什么没参与排序
 */
export type Reason = string;
/**
 * 导致被排除的 error 级规则 ID
 */
export type FailedRules = string[];
/**
 * 未参与排序的方案及原因
 */
export type Excluded = ExcludedScheme[];
/**
 * 在输入 scores 里的行号，从 0 开始
 */
export type Index = number;
/**
 * 贴近度 C = D⁻ / (D⁺ + D⁻)，0–1
 */
export type Closeness1 = number;
/**
 * 到正理想解的欧氏距离 D⁺
 */
export type DistanceToBest = number;
/**
 * 到负理想解的欧氏距离 D⁻
 */
export type DistanceToWorst = number;
/**
 * 名次，从 1 开始；并列时名次相同
 */
export type Rank1 = number;
/**
 * 按输入顺序给出，不重排
 */
export type Schemes = SchemeCloseness[];
/**
 * 正理想解 v⁺（加权归一化空间里）
 */
export type IdealBest = number[];
/**
 * 负理想解 v⁻
 */
export type IdealWorst = number[];
/**
 * 本次排序实际使用的权重
 */
export type Weights2 = number[];
/**
 * 基准权重
 */
export type BaselineWeights = number[];
/**
 * 基准排名，按输入顺序
 */
export type BaselineRanks = number[];
/**
 * 基准第一名行号
 */
export type BaselineTopIndex = number | null;
/**
 * 被扰动的准则名
 */
export type Criterion = string;
/**
 * 被扰动的准则下标
 */
export type CriterionIndex = number;
/**
 * 扰动比例，如 -0.2 表示该准则权重下调 20%
 */
export type Delta = number;
/**
 * 扰动并重新归一化后的权重，和为 1
 */
export type Weights3 = number[];
/**
 * 该权重下的第一名方案行号
 */
export type TopIndex = number | null;
/**
 * 该权重下每个方案的名次，按输入顺序
 */
export type Ranks = number[];
/**
 * 与基准排名相比，是否有任一方案名次变化
 */
export type RankChanged = boolean;
/**
 * 第一名是否换人
 */
export type TopChanged = boolean;
/**
 * 扰动表，按 (准则, delta) 展开
 */
export type Cells = SensitivityCell[];
/**
 * 准则名
 */
export type Criterion1 = string;
/**
 * 准则下标
 */
export type CriterionIndex1 = number;
/**
 * 该准则当前的权重。翻转点在它之下表示「调低会翻」，之上表示「调高会翻」
 */
export type BaselineWeight = number;
/**
 * 第一名首次改变时该准则的权重；整个区间内都不变则为 null
 */
export type FlipWeight = number | null;
/**
 * 翻转后的第一名行号；没有翻转则为 null
 */
export type NewTopIndex = number | null;
/**
 * 每个准则一条
 */
export type FlipPoints = FlipPoint[];
/**
 * 非劣（帕累托最优）方案的行号
 */
export type NonDominated = number[];
/**
 * 第 i 行第 r 列 = 方案 i 排第 (r+1) 名的概率；每行和为 1
 */
export type Probabilities = number[][];
/**
 * 每个方案排第一的概率
 */
export type FirstPlaceProbability1 = number[];
/**
 * 抽样组数
 */
export type Samples = number;
/**
 * Dirichlet 集中度；越大越贴近基准权重
 */
export type Concentration = number;
/**
 * 随机种子；同 seed 结果完全可复现
 */
export type Seed = number;
/**
 * 服务端计算耗时（毫秒），用于盯住滑杆的响应预算
 */
export type ElapsedMs = number;

/**
 * 权重与一致性、名次、敏感性、翻转点、帕累托、名次概率
 */
export interface RankResponse {
  project_id: ProjectId;
  scheme_order: SchemeOrder;
  criteria: Criteria;
  weights_used: WeightsUsed;
  ranking: Ranking;
  excluded: Excluded;
  topsis: TopsisResult;
  sensitivity: SensitivityResult;
  pareto: ParetoResult;
  rank_acceptability: RankAcceptabilityResult;
  elapsed_ms: ElapsedMs;
}
/**
 * 本次使用的权重及其出处
 */
export interface WeightsUsed {
  source: Source;
  criteria: Criteria1;
  weights: Weights;
  role: Role;
  role_name: RoleName;
  is_custom: IsCustom;
  note: Note;
  /**
   * 有两两比较矩阵时的一致性检验结果；直接给权重时为 null
   */
  ahp: AhpResult | null;
  consistency_warning: ConsistencyWarning;
}
/**
 * 两两比较矩阵解出的权重，以及一致性检验的中间量
 */
export interface AhpResult {
  weights: Weights1;
  lambda_max: LambdaMax;
  ci: Ci;
  cr: Cr;
  ri: Ri;
  consistent: Consistent;
}
/**
 * 参与排序的一个方案。
 */
export interface RankedScheme {
  scheme_id: SchemeId;
  scheme_name: SchemeName;
  dimension_scores: DimensionScores;
  closeness: Closeness;
  rank: Rank;
  is_non_dominated: IsNonDominated;
  dominated_by: DominatedBy;
  first_place_probability: FirstPlaceProbability;
}
/**
 * 未参与排序的方案，以及原因。
 */
export interface ExcludedScheme {
  scheme_id: SchemeId1;
  scheme_name: SchemeName1;
  reason: Reason;
  failed_rules: FailedRules;
}
/**
 * TOPSIS 原始结果，含正负理想解
 */
export interface TopsisResult {
  schemes: Schemes;
  ideal_best: IdealBest;
  ideal_worst: IdealWorst;
  weights: Weights2;
}
/**
 * 单个方案的 TOPSIS 中间量与结果。
 */
export interface SchemeCloseness {
  index: Index;
  closeness: Closeness1;
  distance_to_best: DistanceToBest;
  distance_to_worst: DistanceToWorst;
  rank: Rank1;
}
/**
 * 敏感性表与翻转点
 */
export interface SensitivityResult {
  baseline_weights: BaselineWeights;
  baseline_ranks: BaselineRanks;
  baseline_top_index: BaselineTopIndex;
  cells: Cells;
  flip_points: FlipPoints;
}
/**
 * 敏感性表里的一格：某个准则的权重乘上 ``(1 + delta)`` 之后重新排序的结果。
 */
export interface SensitivityCell {
  criterion: Criterion;
  criterion_index: CriterionIndex;
  delta: Delta;
  weights: Weights3;
  top_index: TopIndex;
  ranks: Ranks;
  rank_changed: RankChanged;
  top_changed: TopChanged;
}
/**
 * 该准则权重在 [0, 1] 内扫描时，第一名首次改变的权重值
 */
export interface FlipPoint {
  criterion: Criterion1;
  criterion_index: CriterionIndex1;
  baseline_weight: BaselineWeight;
  flip_weight: FlipWeight;
  new_top_index: NewTopIndex;
}
/**
 * 帕累托筛选（下标对应 scheme_order）
 */
export interface ParetoResult {
  non_dominated: NonDominated;
  dominated_by: DominatedBy1;
}
/**
 * 键是被支配方案的行号，值是支配它的方案行号列表
 */
export interface DominatedBy1 {
  [k: string]: number[];
}
/**
 * 名次概率矩阵
 */
export interface RankAcceptabilityResult {
  probabilities: Probabilities;
  first_place_probability: FirstPlaceProbability1;
  samples: Samples;
  concentration: Concentration;
  seed: Seed;
}
