/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 方案标识，对应 schemes 表里的 id
 */
export type SchemeId = string;
/**
 * 方案名称，报告与看板展示用
 */
export type SchemeName = string;
/**
 * 规则 ID，例如 C-03
 */
export type RuleId = string;
/**
 * 规则中文名
 */
export type Name = string;
/**
 * 判定结果
 */
export type Status = "passed" | "failed" | "insufficient_data" | "not_applicable";
/**
 * 严重程度，来自规则的 severity 字段
 */
export type Severity = "error" | "warning";
/**
 * 实际取值；只有能从 check 里认出被比较字段时才有
 */
export type Value = number | null;
/**
 * 规则要求的限值，例如 '>= 3.0'
 */
export type Limit = string | null;
/**
 * 判定所用的 check 表达式，供报告溯源
 */
export type Formula = string;
/**
 * 规范条文出处
 */
export type Source = string | null;
/**
 * status 为 insufficient_data 时，缺少的原始字段名
 */
export type MissingFields = string[];
/**
 * 人类可读的判定说明
 */
export type Message = string;
/**
 * 合规判定清单
 */
export type Compliance = ComplianceItem[];
/**
 * 规则 ID，例如 K-01
 */
export type RuleId1 = string;
/**
 * 指标中文名
 */
export type Name1 = string;
/**
 * 指标状态
 */
export type Status1 = "scored" | "insufficient_data" | "not_applicable";
/**
 * 计算得到的指标值
 */
export type Value1 = number | null;
/**
 * 该指标 0-100 的得分；数据不足或不适用时为 null
 */
export type Score = number | null;
/**
 * 所属评估维度
 */
export type Dimension = "quality" | "structure" | "construction" | "green";
/**
 * 同维度内的相对权重
 */
export type WeightInDimension = number;
/**
 * 评分公式或说明
 */
export type Formula1 = string;
/**
 * 规则来源（专业组 / 规范）
 */
export type Source1 = string;
/**
 * status 为 insufficient_data 时，缺少的原始字段名
 */
export type MissingFields1 = string[];
/**
 * 居住品质
 */
export type Quality = number;
/**
 * 结构安全
 */
export type Structure = number;
/**
 * 施工友好
 */
export type Construction = number;
/**
 * 绿色低碳
 */
export type Green = number;
/**
 * 居住品质
 */
export type Quality1 = number;
/**
 * 结构安全
 */
export type Structure1 = number;
/**
 * 施工友好
 */
export type Construction1 = number;
/**
 * 绿色低碳
 */
export type Green1 = number;
/**
 * TOPSIS 贴近度，0-1
 */
export type Closeness = number;
/**
 * 在所有参与排序方案中的排名，从 1 开始
 */
export type Rank = number;

/**
 * 合规清单 + 指标值 + 维度得分 + 排名，一并交给报告生成器
 */
export interface EvalResult {
  scheme_id: SchemeId;
  scheme_name?: SchemeName;
  compliance?: Compliance;
  metrics?: Metrics;
  dimension_scores?: DimensionScores;
  dimension_coverage?: DimensionCoverage;
  /**
   * TOPSIS 排序结果；尚未参与排序时为 null
   */
  topsis?: RankResult | null;
}
/**
 * 对应 rules/*.yaml 中一条规则的判定结果
 */
export interface ComplianceItem {
  rule_id: RuleId;
  name: Name;
  status: Status;
  severity?: Severity;
  value?: Value;
  limit?: Limit;
  formula?: Formula;
  source?: Source;
  missing_fields?: MissingFields;
  message: Message;
}
/**
 * 键为指标 ID，values 为指标结果
 */
export interface Metrics {
  [k: string]: MetricResult;
}
/**
 * 单条 metric 规则的计算值、得分、所在维度与公式出处
 */
export interface MetricResult {
  rule_id: RuleId1;
  name: Name1;
  status?: Status1;
  value?: Value1;
  score?: Score;
  dimension: Dimension;
  weight_in_dimension?: WeightInDimension;
  formula: Formula1;
  source: Source1;
  missing_fields?: MissingFields1;
}
/**
 * 四维度加权得分
 */
export interface DimensionScores {
  quality?: Quality;
  structure?: Structure;
  construction?: Construction;
  green?: Green;
}
/**
 * 四维度数据覆盖率，0–1 小数
 */
export interface DimensionCoverage {
  quality?: Quality1;
  structure?: Structure1;
  construction?: Construction1;
  green?: Green1;
}
/**
 * TOPSIS 贴近度与排名
 */
export interface RankResult {
  closeness: Closeness;
  rank: Rank;
}
