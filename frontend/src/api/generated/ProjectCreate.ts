/* 自动生成，请运行 npm run gen:types 更新。 */

/**
 * 项目名称
 */
export type Name = string;
/**
 * 用地面积
 */
export type SiteArea = number | null;
/**
 * 容积率上限（无量纲系数，中国常见 0.5–4.0）
 */
export type FarMax = number | null;
/**
 * 建筑密度上限（小数，0.30 = 30%）
 */
export type DensityMax = number | null;
/**
 * 建筑限高上限
 */
export type HeightMax = number | null;
/**
 * 建筑气候分区
 */
export type ClimateZone = (("严寒" | "寒冷" | "夏热冬冷" | "夏热冬暖" | "温和") | null) &
  ("严寒" | "寒冷" | "夏热冬冷" | "夏热冬暖" | "温和");
/**
 * 抗震设防烈度（浙江全省最高为 7 度 0.10g）
 */
export type SeismicIntensity = (("6度(0.05g)" | "7度(0.10g)") | null) & ("6度(0.05g)" | "7度(0.10g)");

/**
 * 创建项目请求体。
 */
export interface ProjectCreate {
  name: Name;
  params?: ProjectParams;
}
/**
 * 项目层（地块条件）参数，对所有候选方案相同
 */
export interface ProjectParams {
  site_area?: SiteArea;
  far_max?: FarMax;
  density_max?: DensityMax;
  height_max?: HeightMax;
  climate_zone?: ClimateZone;
  seismic_intensity?: SeismicIntensity;
}
