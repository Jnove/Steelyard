/* 自动生成，请运行 npm run gen:types 更新。 */

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
 * 项目所在省级行政区（两字母地区码，如 ZJ）。用于提示「所选的地方册是否与项目所在地一致」
 */
export type Province = (string | null) &
  (
    | "BJ"
    | "TJ"
    | "HE"
    | "SX"
    | "NM"
    | "LN"
    | "JL"
    | "HL"
    | "SH"
    | "JS"
    | "ZJ"
    | "AH"
    | "FJ"
    | "JX"
    | "SD"
    | "HA"
    | "HB"
    | "HN"
    | "GD"
    | "GX"
    | "HI"
    | "CQ"
    | "SC"
    | "GZ"
    | "YN"
    | "XZ"
    | "SN"
    | "GS"
    | "QH"
    | "NX"
    | "XJ"
  );
/**
 * 适用的规则册；留空＝只用国家标准（GB）。GB 永远生效、不能去掉；加进省级地区码后，该省的地方规则才会参与评估
 */
export type StandardPacks = string[] | null;
/**
 * 项目资料出处、真实资料与教学假设的边界；仅作案例说明，不参与评分
 */
export type ProjectNotes = string | null;

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
  province?: Province;
  standard_packs?: StandardPacks;
  project_notes?: ProjectNotes;
}
