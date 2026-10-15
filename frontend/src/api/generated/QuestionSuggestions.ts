/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * @minItems 1
 * @maxItems 3
 */
export type Questions = [string] | [string, string] | [string, string, string];
export type Source = "model" | "fake";

export interface QuestionSuggestions {
  questions: Questions;
  source: Source;
}
