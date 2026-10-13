"""项目与方案的输入参数模型。

字段严格按 AGENTS.md "数据模型"一节，单位 / 分组 / 中文 label 写在
``json_schema_extra`` 中。前端表单与 Excel 模板都从这里生成，避免重复定义。

约定：
- 除方案名称外所有参数字段均为 ``Optional``，真实数据常有缺项，缺项由评估阶段处理。
- 长度用 m，面积用 m²，比例类字段用 0–1 的小数，不用百分数。
- 比例类字段若收到 1–100 之间的数，报错并提示 "请填小数，如 0.82"。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.engine.regions import (
    GB_PACK,
    PROVINCE_BY_CODE,
    PROVINCE_CODES,
    is_region_code,
    pack_options,
)

# —— 枚举与预设选项 —— #

StructureType = Literal["剪力墙", "框架-剪力墙", "框架", "钢结构", "MiC"]
"""结构体系。可选值集中放在下面元组里，方便前端下拉与脚本导出。"""

STRUCTURE_TYPES: tuple[str, ...] = ("剪力墙", "框架-剪力墙", "框架", "钢结构", "MiC")

ClimateZone = Literal["严寒", "寒冷", "夏热冬冷", "夏热冬暖", "温和"]
CLIMATE_ZONES: tuple[str, ...] = ("严寒", "寒冷", "夏热冬冷", "夏热冬暖", "温和")

SeismicIntensity = Literal["6度(0.05g)", "7度(0.10g)"]
"""抗震设防烈度。

只保留这两档，是为了**保证每个取值都有对应的规则**：浙江全省最高设防烈度为
7 度（0.10g）（浙江省《超限高层建筑工程抗震设计导则》条文说明），
所以这两档已覆盖浙江全部地块。将来若服务省外项目，再一起补规则。
"""
SEISMIC_INTENSITIES: tuple[str, ...] = ("6度(0.05g)", "7度(0.10g)")

MiCSystem = Literal[
    "模块化框架结构",
    "模块化全预制剪力墙结构",
    "模块化叠合剪力墙结构",
    "模块化箱模框架结构",
    "模块化箱模框架-剪力墙结构",
    "模块化箱模剪力墙结构",
]
"""MiC（混凝土模块化建筑）的体系类型。

取值直接对应浙江省《混凝土模块化建筑技术导则》（浙建管发〔2026〕118号）
第6.1.8条 表6.1.8「模块化建筑的最大适用高度」的行：MiC 的最大适用高度按
体系类型分档，所以不区分体系就没法判。表中另有「部分框支剪力墙」两行，
需要框支层信息，暂未纳入。
"""
MIC_SYSTEMS: tuple[str, ...] = (
    "模块化框架结构",
    "模块化全预制剪力墙结构",
    "模块化叠合剪力墙结构",
    "模块化箱模框架结构",
    "模块化箱模框架-剪力墙结构",
    "模块化箱模剪力墙结构",
)

# 风险特征预设选项（用户可自由补充自定义项）
RISK_FEATURE_OPTIONS: list[str] = [
    "大悬挑",
    "高大空间",
    "深基坑",
    "高支模",
    "超长结构",
    "不规则建筑",
    "超限构件",
    "复杂地质",
]

#: 超限高层「不规则项」预设（建质〔2015〕67号 附件1）。
#:
#: 前 8 项对应表2（同时具有三项及以上即属规则性超限），后 4 项对应表4
#: （具有任一项即属超限）。这些项本来就是**由结构计算判定的结果**（例如
#: 扭转位移比 > 1.2 才算"扭转不规则"），所以做成声明式清单，而不是让使用者
#: 去填十几个原始比值。表3 的"显著不规则"项另需核定，暂未纳入。
IRREGULARITY_OPTIONS: list[str] = [
    "扭转不规则",
    "凹凸不规则",
    "楼板不连续",
    "刚度突变",
    "尺寸突变",
    "构件间断",
    "承载力突变",
    "局部不规则",
    "高位转换",
    "厚板转换",
    "复杂连接",
    "多重复杂",
]

# 表单分组顺序，前端按这个顺序展示 tab
GROUP_ORDER: tuple[str, ...] = (
    "基本信息",
    "居住品质",
    "结构与造价",
    "施工与安全",
    "绿色低碳",
)


def _meta(unit: str, group: str, label: str, **extra: object) -> dict[str, object]:
    """拼装 ``json_schema_extra`` 片段，统一字段元信息格式。"""
    return {"unit": unit, "group": group, "label": label, **extra}


def _reject_percentage(v: object) -> object:
    """若用户把 0-1 的小数填成了 1–100 之间的数，给出明确错误。

    注：1.0 与 0.0 都是合法的（100% 与 0%），所以区间是 (1, 100]。
    """
    if isinstance(v, bool):  # 避免 True/False 被误判
        return v
    if isinstance(v, (int, float)) and 1 < v <= 100:
        raise ValueError("请填小数，如 0.82（不要用百分数）")
    return v


class ProjectParams(BaseModel):
    """项目层参数：地块条件，对所有方案相同。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "项目参数",
            "description": "项目层（地块条件）参数，对所有候选方案相同",
            "group_order": list(GROUP_ORDER),
        }
    )

    site_area: float | None = Field(
        None,
        description="用地面积",
        gt=0,
        json_schema_extra=_meta("m²", "基本信息", "用地面积", essential=True),
    )
    far_max: float | None = Field(
        None,
        description="容积率上限（无量纲系数，中国常见 0.5–4.0）",
        gt=0,
        json_schema_extra=_meta("—", "基本信息", "容积率上限"),
    )
    density_max: float | None = Field(
        None,
        description="建筑密度上限（小数，0.30 = 30%）",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "基本信息", "建筑密度上限"),
    )
    height_max: float | None = Field(
        None,
        description="建筑限高上限",
        gt=0,
        json_schema_extra=_meta("m", "基本信息", "限高上限"),
    )
    climate_zone: ClimateZone | None = Field(
        None,
        description="建筑气候分区",
        json_schema_extra=_meta("—", "基本信息", "气候分区", enum=list(CLIMATE_ZONES)),
    )
    seismic_intensity: SeismicIntensity | None = Field(
        None,
        description="抗震设防烈度（浙江全省最高为 7 度 0.10g）",
        json_schema_extra=_meta("—", "基本信息", "抗震设防烈度", enum=list(SEISMIC_INTENSITIES)),
    )
    province: str | None = Field(
        None,
        description=(
            "项目所在省级行政区（两字母地区码，如 ZJ）。"
            "用于提示「所选的地方册是否与项目所在地一致」"
        ),
        json_schema_extra=_meta("—", "基本信息", "所在省份", enum=list(PROVINCE_CODES)),
    )
    standard_packs: list[str] | None = Field(
        None,
        description=(
            "适用的规则册；留空＝只用国家标准（GB）。GB 永远生效、不能去掉；"
            "加进省级地区码后，该省的地方规则才会参与评估"
        ),
        json_schema_extra=_meta("—", "基本信息", "适用标准册", options=pack_options()),
    )

    @field_validator("density_max", mode="before")
    @classmethod
    def _check_density_max(cls, v: object) -> object:
        return _reject_percentage(v)

    @field_validator("province")
    @classmethod
    def _check_province(cls, v: str | None) -> str | None:
        """省份必须是注册表里的地区码。"""
        if v is None:
            return None
        code = v.strip().upper()
        if code not in PROVINCE_BY_CODE:
            raise ValueError(
                f"未知的省份代码「{v}」；可用的是 {len(PROVINCE_CODES)} 个省级行政区"
                "（见 backend/app/engine/regions.py）"
            )
        return code

    @field_validator("standard_packs")
    @classmethod
    def _check_standard_packs(cls, v: list[str] | None) -> list[str] | None:
        """册必须都是已知的，且**必须包含 GB**（留空表示"只用国标"）。

        去重并保持顺序。GB 不在列表里时**直接报错**，而不是悄悄替你补上——
        静默补上会让人以为自己关掉了国标，实际没有。国家标准是所有项目的底线。

        这里刻意把"留空"与"给了列表"分开：留空沿用"只用国标"，
        列表则必须显式含 ``GB``。这样新项目不会因为多了一个默认值字段，
        就被前端当成"参数已经填过了"（前端按"字段是否全为空"判断新建项目）。
        """
        if v is None:
            return None
        codes = list(dict.fromkeys(v))
        unknown = [c for c in codes if not is_region_code(c)]
        if unknown:
            raise ValueError(
                f"未知的标准册 {unknown}；可用 GB 或省级地区码"
                f"（共 {len(PROVINCE_CODES)} 个省级行政区）"
            )
        if GB_PACK not in codes:
            raise ValueError(
                f"标准册必须包含 {GB_PACK}：国家标准是底线，不能关掉。"
                '要加地方册请把地区码一起写进来，例如 ["GB", "ZJ"]'
            )
        return codes


class SchemeParams(BaseModel):
    """方案层参数：单个建筑方案的全部设计输入。

    注意：方案名称与 what-if 元信息 (``is_whatif`` / ``parent_id``) 不在本模型内，
    它们是方案记录的字段而不是设计参数，存放在 SQLModel 表里。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "title": "方案参数",
            "description": "方案层（设计输入）参数，每个候选方案独立",
            "group_order": list(GROUP_ORDER),
        }
    )

    # —— 基本信息 —— #
    structure_type: StructureType | None = Field(
        None,
        description="结构体系",
        json_schema_extra=_meta(
            "—", "基本信息", "结构体系", enum=list(STRUCTURE_TYPES), essential=True
        ),
    )
    mic_system: MiCSystem | None = Field(
        None,
        description="MiC 体系类型（结构体系选 MiC 时填写）",
        json_schema_extra=_meta("—", "基本信息", "MiC 体系类型", enum=list(MIC_SYSTEMS)),
    )
    units: int | None = Field(
        None,
        description="总户数",
        gt=0,
        json_schema_extra=_meta("户", "基本信息", "总户数", essential=True),
    )
    unit_mix: dict[str, int] | None = Field(
        None,
        description="户型配比：键为户型名称（如 1室1厅），值为户数",
        json_schema_extra=_meta("户", "基本信息", "户型配比"),
    )

    # —— 居住品质 —— #
    floor_height: float | None = Field(
        None,
        description="层高",
        gt=0,
        json_schema_extra=_meta("m", "居住品质", "层高"),
    )
    inner_area_ratio: float | None = Field(
        None,
        description="得房率（套内面积 / 建筑面积）",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "居住品质", "得房率"),
    )
    south_room_ratio: float | None = Field(
        None,
        description="主要房间南向比例",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "居住品质", "南向比例"),
    )
    window_floor_ratio: float | None = Field(
        None,
        description="窗地比（窗面积 / 地面积）",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "居住品质", "窗地比"),
    )
    window_wall_ratio: dict[str, float] | None = Field(
        None,
        description="各朝向窗墙比，键为朝向（南/北/东/西），值为 0-1 小数",
        json_schema_extra=_meta("—", "居住品质", "窗墙比"),
    )
    elevators_per_unit: int | None = Field(
        None,
        description="每单元电梯数",
        ge=0,
        json_schema_extra=_meta("台", "居住品质", "电梯数/单元"),
    )
    highest_occupied_floor: int | None = Field(
        None,
        ge=1,
        description="最高住宅入户层的层序，不得用含非住宅层的总层数代替",
        json_schema_extra=_meta("层", "居住品质", "最高住宅入户层"),
    )
    highest_occupied_floor_height: float | None = Field(
        None,
        ge=0,
        description="最高住宅入户层楼面距室外设计地面的实际高度，不是建筑总高",
        json_schema_extra=_meta("m", "居住品质", "最高入户层楼面高度"),
    )
    daylight_factor: float | None = Field(
        None,
        description="卧室、起居室的采光系数（小数，0.022 即 2.2%）",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "居住品质", "采光系数"),
    )
    sunlight_hours: float | None = Field(
        None,
        description="日照标准日的日照时数（杭州为大寒日）",
        gt=0,
        json_schema_extra=_meta("h", "居住品质", "日照时数"),
    )

    # —— 结构与造价 —— #
    gfa: float | None = Field(
        None,
        description="总建筑面积",
        gt=0,
        json_schema_extra=_meta("m²", "结构与造价", "总建筑面积", essential=True),
    )
    footprint: float | None = Field(
        None,
        description="建筑基底面积",
        gt=0,
        json_schema_extra=_meta("m²", "结构与造价", "基底面积"),
    )
    buildings: int | None = Field(
        None,
        description="楼栋数",
        gt=0,
        json_schema_extra=_meta("栋", "结构与造价", "楼栋数"),
    )
    floors: int | None = Field(
        None,
        description="层数",
        gt=0,
        json_schema_extra=_meta("层", "结构与造价", "层数", essential=True),
    )
    envelope_area: float | None = Field(
        None,
        description="建筑外表面积",
        gt=0,
        json_schema_extra=_meta("m²", "结构与造价", "外表面积"),
    )
    volume: float | None = Field(
        None,
        description="建筑体积",
        gt=0,
        json_schema_extra=_meta("m³", "结构与造价", "建筑体积"),
    )
    slab_thickness: float | None = Field(
        None,
        description="钢筋混凝土结构实心楼板厚度",
        gt=0,
        json_schema_extra=_meta("mm", "结构与造价", "楼板厚度"),
    )
    design_working_life: int | None = Field(
        None,
        description="结构设计工作年限",
        gt=0,
        json_schema_extra=_meta("年", "结构与造价", "结构设计工作年限"),
    )
    min_plan_width: float | None = Field(
        None,
        description="楼栋最小平面宽度（用于算高宽比；一般取进深方向的最小宽度）",
        gt=0,
        json_schema_extra=_meta("m", "结构与造价", "最小平面宽度"),
    )
    concrete_grade: float | None = Field(
        None,
        description="结构混凝土强度等级（填 C 后的数值，如 C30 填 30）",
        gt=0,
        json_schema_extra=_meta("MPa", "结构与造价", "混凝土强度等级"),
    )
    irregularity_items: list[str] | None = Field(
        None,
        description="超限高层不规则项（结构计算判定后勾选；留空为未核对，明确填写 [] 为已核对无不规则项）",
        json_schema_extra=_meta(
            "—",
            "结构与造价",
            "超限不规则项",
            options=IRREGULARITY_OPTIONS,
            allow_custom_options=False,
            empty_means_unknown=True,
        ),
    )

    # —— 施工与安全 —— #
    std_floor_repeat: float | None = Field(
        None,
        description="标准层重复率",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "施工与安全", "标准层重复率"),
    )
    component_types: int | None = Field(
        None,
        description="预制构件种类数",
        gt=0,
        json_schema_extra=_meta("种", "施工与安全", "预制构件种类"),
    )
    risk_features: list[str] = Field(
        default_factory=list,
        description="风险特征列表（预设见 RISK_FEATURE_OPTIONS，允许自定义）",
        json_schema_extra=_meta(
            "—",
            "施工与安全",
            "风险特征",
            options=RISK_FEATURE_OPTIONS,
        ),
    )

    # —— 绿色低碳 —— #
    prefab_ratio_est: float | None = Field(
        None,
        description="预估装配率",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "绿色低碳", "预估装配率"),
    )
    green_ratio: float | None = Field(
        None,
        description="绿地率（绿地面积 / 用地面积）",
        ge=0,
        le=1,
        json_schema_extra=_meta("—", "绿色低碳", "绿地率"),
    )

    @field_validator("irregularity_items")
    @classmethod
    def _validate_irregularity_items(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unknown = sorted(set(value) - set(IRREGULARITY_OPTIONS))
        if unknown:
            raise ValueError(f"超限不规则项含未支持的选项：{'、'.join(unknown)}；请选择预设项")
        return list(dict.fromkeys(value))

    @field_validator(
        "inner_area_ratio",
        "south_room_ratio",
        "window_floor_ratio",
        "std_floor_repeat",
        "prefab_ratio_est",
        "daylight_factor",
        "green_ratio",
        mode="before",
    )
    @classmethod
    def _check_ratio(cls, v: object) -> object:
        return _reject_percentage(v)

    @field_validator("window_wall_ratio", mode="before")
    @classmethod
    def _check_window_wall_ratio(cls, v: object) -> object:
        """窗墙比是嵌套字典，对每个朝向的值都做 0-1 校验。"""
        if not isinstance(v, dict):
            return v
        for direction, ratio in v.items():
            if isinstance(ratio, (int, float)) and 1 < ratio <= 100:
                raise ValueError(
                    f"朝向 {direction} 的窗墙比 {ratio} 看起来像百分数，请填小数（如 0.40）"
                )
        return v

    @model_validator(mode="after")
    def _check_unit_mix_sum(self) -> SchemeParams:
        """若同时给了总户数与户型配比，两者必须一致。"""
        if self.units is not None and self.unit_mix:
            total = sum(self.unit_mix.values())
            if total != self.units:
                raise ValueError(f"户型配比合计 {total} 户与总户数 {self.units} 不一致")
        return self
