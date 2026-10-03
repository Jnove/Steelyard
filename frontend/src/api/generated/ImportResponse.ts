/* 自动生成，请运行 npm run gen:types 更新。 */

export type Id = number;
/**
 * 实际写入的方案名（已做项目内唯一化）
 */
export type Name = string;
export type Created = ImportCreatedItem[];
/**
 * 出错方案名；项目层错误为 null
 */
export type Scheme = string | null;
/**
 * 出错字段的英文名
 */
export type Field = string | null;
/**
 * 字段中文名
 */
export type Label = string;
/**
 * 面向用户的错误说明
 */
export type Message = string;
export type Errors = ImportErrorItem[];
/**
 * 是否顺便把 xlsx 里的项目参数写入了空项目
 */
export type ProjectParamsUpdated = boolean;

/**
 * 导入结果。
 */
export interface ImportResponse {
  created?: Created;
  errors?: Errors;
  project_params_updated?: ProjectParamsUpdated;
}
/**
 * 成功创建的方案记录。
 */
export interface ImportCreatedItem {
  id: Id;
  name: Name;
}
/**
 * 单条导入错误（与 ``app.excel.ParseError`` 对应的 API 形态）。
 */
export interface ImportErrorItem {
  scheme?: Scheme;
  field?: Field;
  label: Label;
  message: Message;
}
