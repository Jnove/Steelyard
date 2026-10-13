/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 规则总条数
 */
export type RuleCount = number;
/**
 * 硬约束条数
 */
export type HardCount = number;
/**
 * 评分指标条数
 */
export type MetricCount = number;
/**
 * 规则编号：国家层面标准形如 C-03（全局唯一），地方标准形如 ZJ-S-01（地区码 + 维度字母 + 两位数字）
 */
export type Id = string;
/**
 * 规则所属的「册」：GB 是国家标准册（永远生效），其余是省级册（默认关闭，由项目选择）。地方规则的 ID 地区码必须与本字段一致
 */
export type Pack = string;
/**
 * 规则中文名，给前端与报告看
 */
export type Name = string;
/**
 * hard 硬约束 / metric 评分指标
 */
export type Type = "hard" | "metric";
/**
 * 条文或经验出处，报告里会原样引用
 */
export type Source = string;
/**
 * 可选守卫表达式；为假时该规则不适用，状态记为 not_applicable
 */
export type When = string | null;
/**
 * hard 规则的布尔表达式，为假即不通过
 */
export type Check = string | null;
/**
 * 不通过时的说明，可用 {字段名} 占位实际取值
 */
export type Message = string | null;
/**
 * hard 规则的严重程度；error 标红并踢出排名，warning 仅提示
 */
export type Severity = "error" | "warning";
/**
 * metric 所属维度
 */
export type Dimension = ("quality" | "structure" | "construction" | "green") | null;
/**
 * metric 的取值：字段名或表达式
 */
export type Value = string | null;
/**
 * 评分方式；现阶段只支持 piecewise（分段线性）
 */
export type Kind = "piecewise";
/**
 * 控制点列表，每项 [指标值, 分数]；指标值严格递增，分数在 0–100 之间
 */
export type Points = [number, number][];
/**
 * 同维度内的相对权重，正数，默认 1
 */
export type WeightInDimension = number;
/**
 * 来自 rules/ 下的哪个文件
 */
export type SourceFile = string;
/**
 * 全部规则
 */
export type Rules = RuleRead[];
/**
 * 字段名，规则里直接引用
 */
export type Name1 = string;
/**
 * 中文名
 */
export type Label = string;
/**
 * 单位；无量纲为 —
 */
export type Unit = string;
/**
 * 计算公式
 */
export type Formula = string;
/**
 * 依赖的原始字段
 */
export type Deps = string[];
/**
 * 说明
 */
export type Note = string;
/**
 * 全部派生量定义
 */
export type DerivedQuantities = DerivedQuantityRead[];
/**
 * source 里仍含 TODO 的规则 ID；这些规则的出处尚未落实，报告里应提示
 */
export type TodoSourceIds = string[];

/**
 * 当前加载的全部规则与派生量定义
 */
export interface RulesResponse {
  rule_count: RuleCount;
  hard_count: HardCount;
  metric_count: MetricCount;
  rules: Rules;
  derived_quantities: DerivedQuantities;
  todo_source_ids: TodoSourceIds;
}
/**
 * 一条规则的对外描述：规则本体 + 它来自哪个文件。
 */
export interface RuleRead {
  definition: RuleDef;
  source_file: SourceFile;
}
/**
 * 规则定义，字段含义见 rules/_template.yaml
 */
export interface RuleDef {
  id: Id;
  pack?: Pack;
  name: Name;
  type: Type;
  source: Source;
  when?: When;
  check?: Check;
  message?: Message;
  severity?: Severity;
  dimension?: Dimension;
  value?: Value;
  /**
   * metric 的评分定义
   */
  scoring?: ScoringDef | null;
  weight_in_dimension?: WeightInDimension;
}
/**
 * metric 规则的评分定义。目前只有分段线性一种。
 */
export interface ScoringDef {
  kind: Kind;
  points: Points;
}
/**
 * 派生量的对外描述。
 */
export interface DerivedQuantityRead {
  name: Name1;
  label: Label;
  unit: Unit;
  formula: Formula;
  deps: Deps;
  note?: Note;
}
