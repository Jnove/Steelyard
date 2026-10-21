/* 自动生成，请运行 npm run gen:types 更新。 */

export type Intent = "new_eval" | "whatif" | "explain" | "reweight";
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
export type Role = string | null;
export type Weights = number[] | null;
export type RuleId = string | null;
export type SchemeName = string;
export type FieldLabel = string;
export type Before =
  | string
  | number
  | boolean
  | {
      [k: string]: unknown;
    }
  | unknown[]
  | null;
export type After =
  | string
  | number
  | boolean
  | {
      [k: string]: unknown;
    }
  | unknown[]
  | null;
export type Fingerprint = string;

export interface PlanPreview {
  plan: Plan;
  proposal: ChangeProposal | null;
  fingerprint: Fingerprint;
}
export interface Plan {
  intent: Intent;
  change: SchemeChange | null;
  role: Role;
  weights: Weights;
  rule_id: RuleId;
}
export interface SchemeChange {
  scheme_id: SchemeId;
  field: Field;
  value: Value;
}
export interface ChangeProposal {
  scheme_name: SchemeName;
  field_label: FieldLabel;
  before: Before;
  after: After;
}
