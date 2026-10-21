/* 自动生成，请运行 npm run gen:types 更新。 */

export type Message = string;
export type Role = "user" | "assistant";
export type Content = string;
/**
 * @maxItems 50
 */
export type History = HistoryMessage[];
export type Intent = ("new_eval" | "whatif" | "explain" | "reweight") | null;
export type Role1 = string | null;
export type Weights = number[] | null;
export type IncludeWhatif = boolean;
export type SchemeId = number;
export type Field = string;
export type Value =
  | string
  | number
  | boolean
  | {
      [k: string]: unknown;
    }
  | unknown[]
  | null;
export type RuleId = string | null;
export type SchemeId1 = number | null;
export type ExpectedFingerprint = string | null;

export interface AgentRequest {
  message?: Message;
  history?: History;
  intent?: Intent;
  role?: Role1;
  weights?: Weights;
  include_whatif?: IncludeWhatif;
  change?: SchemeChange | null;
  rule_id?: RuleId;
  scheme_id?: SchemeId1;
  expected_fingerprint?: ExpectedFingerprint;
}
export interface HistoryMessage {
  role: Role;
  content: Content;
}
export interface SchemeChange {
  scheme_id: SchemeId;
  field: Field;
  value: Value;
}
