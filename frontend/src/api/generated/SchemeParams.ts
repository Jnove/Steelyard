/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 结构体系
 */
export type StructureType = (("剪力墙" | "框架-剪力墙" | "框架" | "钢结构" | "MiC") | null) &
  ("剪力墙" | "框架-剪力墙" | "框架" | "钢结构" | "MiC");
/**
 * MiC 体系类型（结构体系选 MiC 时填写）
 */
export type MicSystem = (
  | (
      | "模块化框架结构"
      | "模块化全预制剪力墙结构"
      | "模块化叠合剪力墙结构"
      | "模块化箱模框架结构"
      | "模块化箱模框架-剪力墙结构"
      | "模块化箱模剪力墙结构"
    )
  | null
) &
  (
    | "模块化框架结构"
    | "模块化全预制剪力墙结构"
    | "模块化叠合剪力墙结构"
    | "模块化箱模框架结构"
    | "模块化箱模框架-剪力墙结构"
    | "模块化箱模剪力墙结构"
  );
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
 * 卧室、起居室的采光系数（小数，0.022 即 2.2%）
 */
export type DaylightFactor = number | null;
/**
 * 日照标准日的日照时数（杭州为大寒日）
 */
export type SunlightHours = number | null;
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
 * 钢筋混凝土结构实心楼板厚度
 */
export type SlabThickness = number | null;
/**
 * 结构设计工作年限
 */
export type DesignWorkingLife = number | null;
/**
 * 楼栋最小平面宽度（用于算高宽比；一般取进深方向的最小宽度）
 */
export type MinPlanWidth = number | null;
/**
 * 结构混凝土强度等级（填 C 后的数值，如 C30 填 30）
 */
export type ConcreteGrade = number | null;
/**
 * 超限高层不规则项（结构计算判定后勾选，见建质〔2015〕67号 附件1）
 */
export type IrregularityItems = string[];
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
/**
 * 绿地率（绿地面积 / 用地面积）
 */
export type GreenRatio = number | null;

/**
 * 方案层（设计输入）参数，每个候选方案独立
 */
export interface SchemeParams {
  structure_type?: StructureType;
  mic_system?: MicSystem;
  units?: Units;
  unit_mix?: UnitMix;
  floor_height?: FloorHeight;
  inner_area_ratio?: InnerAreaRatio;
  south_room_ratio?: SouthRoomRatio;
  window_floor_ratio?: WindowFloorRatio;
  window_wall_ratio?: WindowWallRatio;
  elevators_per_unit?: ElevatorsPerUnit;
  daylight_factor?: DaylightFactor;
  sunlight_hours?: SunlightHours;
  gfa?: Gfa;
  footprint?: Footprint;
  buildings?: Buildings;
  floors?: Floors;
  envelope_area?: EnvelopeArea;
  volume?: Volume;
  slab_thickness?: SlabThickness;
  design_working_life?: DesignWorkingLife;
  min_plan_width?: MinPlanWidth;
  concrete_grade?: ConcreteGrade;
  irregularity_items?: IrregularityItems;
  std_floor_repeat?: StdFloorRepeat;
  component_types?: ComponentTypes;
  risk_features?: RiskFeatures;
  custom?: Custom;
  prefab_ratio_est?: PrefabRatioEst;
  green_ratio?: GreenRatio;
}
/**
 * 自定义字段的值：键是自定义字段名，值按字段类型（数值 / 比例 / 文本 / 列表）。界面上由覆盖层注册表渲染成一个个独立输入项，本字段本身不直接展示（见 app/custom/fields.py 与 docs/design-custom-add.md）
 */
export interface Custom {
  [k: string]: unknown;
}
