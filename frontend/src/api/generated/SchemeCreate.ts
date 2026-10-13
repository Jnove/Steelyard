/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 方案名称（项目内唯一）
 */
export type Name = string;
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
 * 最高住宅入户层的层序，不得用含非住宅层的总层数代替
 */
export type HighestOccupiedFloor = number | null;
/**
 * 最高住宅入户层楼面距室外设计地面的实际高度，不是建筑总高
 */
export type HighestOccupiedFloorHeight = number | null;
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
 * 基础形式（筏形 / 桩筏基础的混凝土强度等级不应低于 C30）
 */
export type FoundationType = (("筏形基础" | "桩筏基础" | "独立基础" | "条形基础" | "桩基础") | null) &
  ("筏形基础" | "桩筏基础" | "独立基础" | "条形基础" | "桩基础");
/**
 * 地基与基础的设计工作年限（不应低于上部结构的设计工作年限）
 */
export type FoundationWorkingLife = number | null;
/**
 * 钢结构体系类型（仅在结构体系选“钢结构”时填写；不同体系最大适用高度不同）
 */
export type SteelSystem = (("框架" | "框架-中心支撑" | "框架-偏心支撑（延性墙板）" | "筒体和巨型框架") | null) &
  ("框架" | "框架-中心支撑" | "框架-偏心支撑（延性墙板）" | "筒体和巨型框架");
/**
 * 是否设置地下室（超过 50 m 的钢结构房屋应设置地下室）
 */
export type HasBasement = boolean | null;
/**
 * 剪力墙截面厚度（高层 ≥160 mm、多层 ≥140 mm；错层处 ≥250 mm）
 */
export type ShearWallThickness = number | null;
/**
 * 矩形截面框架梁的截面宽度（不应小于 200 mm）
 */
export type FrameBeamWidth = number | null;
/**
 * 框架柱截面形状（矩形柱按边长、圆形柱按直径判定）
 */
export type FrameColumnShape = (("矩形" | "圆形") | null) & ("矩形" | "圆形");
/**
 * 框架柱截面尺寸（矩形填边长、圆形填直径：≥300 / ≥350 mm）
 */
export type FrameColumnSize = number | null;
/**
 * 筏形 / 桩筏基础底板上下贯通钢筋配筋率（不应小于 0.15%，填百分数）
 */
export type RaftRebarRatio = number | null;
/**
 * 基础埋置深度（超过 50 m 的钢结构：天然地基不宜小于 H/15、桩基不宜小于 H/20）
 */
export type FoundationDepth = number | null;
/**
 * 是否存在错层（错层处柱、平面外受力剪力墙有专门的截面与混凝土要求）
 */
export type HasStaggeredFloor = boolean | null;
/**
 * 框架是否为单跨框架（钢结构：甲、乙类与高层丙类不应采用单跨框架）
 */
export type IsSingleSpanFrame = boolean | null;
/**
 * 超限高层不规则项（结构计算判定后勾选；留空为未核对，明确填写 [] 为已核对无不规则项）
 */
export type IrregularityItems = string[] | null;
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
 * 基坑开挖深度（用于危大工程判定：≥3m 须专项施工方案，≥5m 须专家论证）
 */
export type ExcavationDepth = number | null;
/**
 * 混凝土模板支撑搭设高度（用于危大工程判定：≥5m 须专项方案，≥8m 须专家论证）
 */
export type FormworkHeight = number | null;
/**
 * 外脚手架形式（附着式升降与悬挑式一律属危大工程）
 */
export type ScaffoldType = (("落地式钢管脚手架" | "附着式升降脚手架" | "悬挑式脚手架") | null) &
  ("落地式钢管脚手架" | "附着式升降脚手架" | "悬挑式脚手架");
/**
 * 脚手架搭设高度（落地式：≥24m 须专项方案，≥50m 须专家论证）
 */
export type ScaffoldHeight = number | null;
/**
 * 基坑支护形式（排桩 ≥C25、两墙合一下的地下连续墙 ≥C30）
 */
export type RetainingType = (("排桩" | "地下连续墙" | "土钉墙" | "放坡开挖" | "其他") | null) &
  ("排桩" | "地下连续墙" | "土钉墙" | "放坡开挖" | "其他");
/**
 * 支护结构混凝土强度等级（填 C 后的数值；与上部结构分开填）
 */
export type RetainingConcreteGrade = number | null;
/**
 * 基坑工程设计工作年限（不应小于 1 年）
 */
export type ExcavationWorkingLife = number | null;
/**
 * 基坑内支撑 / 锚拉体系（混凝土内支撑 ≥C25；锚杆自由段 ≥5.0m）
 */
export type BraceType = (("混凝土内支撑" | "钢支撑" | "锚杆（锚拉）" | "无内支撑与锚拉") | null) &
  ("混凝土内支撑" | "钢支撑" | "锚杆（锚拉）" | "无内支撑与锚拉");
/**
 * 锚杆自由段长度（不应小于 5.0 m）
 */
export type AnchorFreeLength = number | null;
/**
 * 预估装配率
 */
export type PrefabRatioEst = number | null;
/**
 * 绿地率（绿地面积 / 用地面积）
 */
export type GreenRatio = number | null;
/**
 * 是否为假设推演副本（T8 用）
 */
export type IsWhatif = boolean;
/**
 * 若为 what-if，指向所基于的原方案
 */
export type ParentId = number | null;

/**
 * 创建方案请求体。
 */
export interface SchemeCreate {
  name: Name;
  params?: SchemeParams;
  is_whatif?: IsWhatif;
  parent_id?: ParentId;
}
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
  highest_occupied_floor?: HighestOccupiedFloor;
  highest_occupied_floor_height?: HighestOccupiedFloorHeight;
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
  foundation_type?: FoundationType;
  foundation_working_life?: FoundationWorkingLife;
  steel_system?: SteelSystem;
  has_basement?: HasBasement;
  shear_wall_thickness?: ShearWallThickness;
  frame_beam_width?: FrameBeamWidth;
  frame_column_shape?: FrameColumnShape;
  frame_column_size?: FrameColumnSize;
  raft_rebar_ratio?: RaftRebarRatio;
  foundation_depth?: FoundationDepth;
  has_staggered_floor?: HasStaggeredFloor;
  is_single_span_frame?: IsSingleSpanFrame;
  irregularity_items?: IrregularityItems;
  std_floor_repeat?: StdFloorRepeat;
  component_types?: ComponentTypes;
  risk_features?: RiskFeatures;
  excavation_depth?: ExcavationDepth;
  formwork_height?: FormworkHeight;
  scaffold_type?: ScaffoldType;
  scaffold_height?: ScaffoldHeight;
  retaining_type?: RetainingType;
  retaining_concrete_grade?: RetainingConcreteGrade;
  excavation_working_life?: ExcavationWorkingLife;
  brace_type?: BraceType;
  anchor_free_length?: AnchorFreeLength;
  prefab_ratio_est?: PrefabRatioEst;
  green_ratio?: GreenRatio;
}
