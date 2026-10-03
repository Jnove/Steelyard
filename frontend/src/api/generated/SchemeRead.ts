/* 自动生成，请运行 npm run gen:types 更新。 */

export type Id = number;
export type ProjectId = number;
export type Name = string;
/**
 * 结构体系
 */
export type StructureType = (("剪力墙" | "框架-剪力墙" | "框架" | "钢结构" | "MiC") | null) &
  ("剪力墙" | "框架-剪力墙" | "框架" | "钢结构" | "MiC");
/**
 * 总户数
 */
export type Units = number | null;
/**
 * 户型配比：键为户型名称（如 1室1厅），值为户数
 */
export type UnitMix = {
  [k: string]: number;
} | null;
/**
 * 层高
 */
export type FloorHeight = number | null;
/**
 * 得房率（套内面积 / 建筑面积）
 */
export type InnerAreaRatio = number | null;
/**
 * 主要房间南向比例
 */
export type SouthRoomRatio = number | null;
/**
 * 窗地比（窗面积 / 地面积）
 */
export type WindowFloorRatio = number | null;
/**
 * 各朝向窗墙比，键为朝向（南/北/东/西），值为 0-1 小数
 */
export type WindowWallRatio = {
  [k: string]: number;
} | null;
/**
 * 每单元电梯数
 */
export type ElevatorsPerUnit = number | null;
/**
 * 总建筑面积
 */
export type Gfa = number | null;
/**
 * 建筑基底面积
 */
export type Footprint = number | null;
/**
 * 楼栋数
 */
export type Buildings = number | null;
/**
 * 层数
 */
export type Floors = number | null;
/**
 * 建筑外表面积
 */
export type EnvelopeArea = number | null;
/**
 * 建筑体积
 */
export type Volume = number | null;
/**
 * 标准层重复率
 */
export type StdFloorRepeat = number | null;
/**
 * 预制构件种类数
 */
export type ComponentTypes = number | null;
/**
 * 风险特征列表（预设见 RISK_FEATURE_OPTIONS，允许自定义）
 */
export type RiskFeatures = string[];
/**
 * 预估装配率
 */
export type PrefabRatioEst = number | null;
export type IsWhatif = boolean;
export type ParentId = number | null;
export type CreatedAt = string;
export type UpdatedAt = string;

/**
 * 方案读取响应。
 */
export interface SchemeRead {
  id: Id;
  project_id: ProjectId;
  name: Name;
  params: SchemeParams;
  is_whatif: IsWhatif;
  parent_id: ParentId;
  created_at: CreatedAt;
  updated_at: UpdatedAt;
}
/**
 * 方案层（设计输入）参数，每个候选方案独立
 */
export interface SchemeParams {
  structure_type?: StructureType;
  units?: Units;
  unit_mix?: UnitMix;
  floor_height?: FloorHeight;
  inner_area_ratio?: InnerAreaRatio;
  south_room_ratio?: SouthRoomRatio;
  window_floor_ratio?: WindowFloorRatio;
  window_wall_ratio?: WindowWallRatio;
  elevators_per_unit?: ElevatorsPerUnit;
  gfa?: Gfa;
  footprint?: Footprint;
  buildings?: Buildings;
  floors?: Floors;
  envelope_area?: EnvelopeArea;
  volume?: Volume;
  std_floor_repeat?: StdFloorRepeat;
  component_types?: ComponentTypes;
  risk_features?: RiskFeatures;
  prefab_ratio_est?: PrefabRatioEst;
}
