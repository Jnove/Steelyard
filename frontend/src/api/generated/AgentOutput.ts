/* 自动生成，请运行 npm run gen:types 更新。 */

export type Report = string;
export type Intent = "new_eval" | "whatif" | "explain" | "reweight";
export type Text = string;
export type Start = number;
export type End = number;
export type UnverifiedNumbers = NumberIssue[];
export type Node = string;
export type ElapsedMs = number;
export type ToolCalls = string[];
export type Traces = NodeTrace[];
export type Cached = boolean;

export interface AgentOutput {
  report: Report;
  intent: Intent;
  unverified_numbers: UnverifiedNumbers;
  traces: Traces;
  cached: Cached;
}
export interface NumberIssue {
  text: Text;
  start: Start;
  end: End;
}
export interface NodeTrace {
  node: Node;
  elapsed_ms: ElapsedMs;
  tool_calls: ToolCalls;
}
