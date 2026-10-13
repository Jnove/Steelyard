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

ScaffoldType = Literal["落地式钢管脚手架", "附着式升降脚手架", "悬挑式脚手架"]
"""外脚手架形式。

只收这三类，因为它们对应**不同的危大工程门槛**（依据：住建部令第37号《危险性较大的
分部分项工程安全管理规定》配套的建办质〔2018〕31号 附件1/附件2）：

- 落地式钢管脚手架：搭设高度 ≥24 m 须编专项施工方案，≥50 m 须专家论证；
- 附着式升降脚手架、悬挑式脚手架：**一律属于危大工程**（无高度门槛），
  其中附着式提升高度 ≥150 m、悬挑式分段架体高度 ≥20 m 还须专家论证。

前者有阈值可判，后两者是"只要采用就成立"，因此本系统只对落地式做阈值判定，
其余两类在规则文件头部说明里交代，避免对每个方案都刷一条同义提示。
"""
SCAFFOLD_TYPES: tuple[str, ...] = (
    "落地式钢管脚手架",
    "附着式升降脚手架",
    "悬挑式脚手架",
)

FoundationType = Literal["筏形基础", "桩筏基础", "独立基础", "条形基础", "桩基础"]
"""基础形式。

只区分**规范给了不同下限**的几类（依据 GB 55003—2021《建筑与市政地基基础通用规范》，
全文强制）：

- 筏形基础、桩筏基础：混凝土强度等级不应低于 C30（第6.3.5条）；
- 其余形式（独立基础、条形基础、桩基础）：该条未给混凝土强度下限，
  规则里判为"不适用"，而不是硬套 C30。

基础形式单独成字段，是因为"上部结构相同、基础做法不同"会直接改变材料要求与造价，
属于方案比选里应当显式比较的一项。
"""
FOUNDATION_TYPES: tuple[str, ...] = ("筏形基础", "桩筏基础", "独立基础", "条形基础", "桩基础")

RetainingType = Literal["排桩", "地下连续墙", "土钉墙", "放坡开挖", "其他"]
"""基坑支护形式。

同样只区分**规范给了不同下限**的几类（GB 55003—2021 第7.2节）：

- 排桩：桩身混凝土强度等级不应低于 C25（第7.2.4条）；
- 两墙合一的地下连续墙：混凝土强度等级不应低于 C30（第7.2.5条）；
- 土钉墙、放坡开挖等无混凝土构件或规范未给专门下限，判为"不适用"。
"""
RETAINING_TYPES: tuple[str, ...] = ("排桩", "地下连续墙", "土钉墙", "放坡开挖", "其他")

SteelSystem = Literal["框架", "框架-中心支撑", "框架-偏心支撑（延性墙板）", "筒体和巨型框架"]
"""钢结构体系类型。

依据 GB/T 50011—2010（2024年版）第8.1.1条 表8.1.1「钢结构房屋适用的最大高度（m）」：
同一烈度下不同体系的最大适用高度差一倍以上（6、7度 0.10g 列：框架 110、
框架-中心支撑 220、框架-偏心支撑（延性墙板）240、筒体和巨型框架 300），
所以必须分体系取值，不能给钢结构一个笼统限值。
"""
STEEL_SYSTEMS: tuple[str, ...] = (
    "框架",
    "框架-中心支撑",
    "框架-偏心支撑（延性墙板）",
    "筒体和巨型框架",
)

BraceType = Literal["混凝土内支撑", "钢支撑", "锚杆（锚拉）", "无内支撑与锚拉"]
"""基坑内支撑 / 锚拉体系。

依据 GB 55003—2021 第7.2节：混凝土内支撑的混凝土强度等级不应低于 C25（第7.2.6条）、
锚拉结构的锚杆自由段长度不应小于 5.0 m（第7.2.8条）。钢支撑与"无内支撑与锚拉"
在本规范里没有对应的混凝土等级或锚杆长度要求，规则中判为"不适用"。
"""
BRACE_TYPES: tuple[str, ...] = ("混凝土内支撑", "钢支撑", "锚杆（锚拉）", "无内支撑与锚拉")

ColumnShape = Literal["矩形", "圆形"]
"""框架柱截面形状（GB 55008—2021 第4.4.4条第2款对两种形状给了不同下限）：

- 矩形截面柱：边长不应小于 300 mm；
- 圆形截面柱：直径不应小于 350 mm。
"""
COLUMN_SHAPES: tuple[str, ...] = ("矩形", "圆形")


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

    @field_validator("density_max", mode="before")
    @classmethod
    def _check_density_max(cls, v: object) -> object:
        return _reject_percentage(v)


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
    structural_height_classification: Literal["高层", "多层"] | None = Field(
        None,
        description="结构专业核定的高层 / 多层分类（按所适用结构条文核定，不从住宅建筑高度分类自动推定）",
        json_schema_extra=_meta("—", "结构与造价", "结构高度分类", enum=["高层", "多层"]),
    )
    foundation_type: FoundationType | None = Field(
        None,
        description="基础形式（筏形 / 桩筏基础的混凝土强度等级不应低于 C30）",
        json_schema_extra=_meta("—", "结构与造价", "基础形式", enum=list(FOUNDATION_TYPES)),
    )
    foundation_concrete_grade: float | None = Field(
        None,
        description="基础混凝土强度等级（填 C 后的数值，如 C30 填 30；不从上部结构等级推定）",
        gt=0,
        json_schema_extra=_meta("MPa", "结构与造价", "基础混凝土强度等级"),
    )
    foundation_working_life: int | None = Field(
        None,
        description="地基与基础的设计工作年限（不应低于上部结构的设计工作年限）",
        gt=0,
        json_schema_extra=_meta("年", "结构与造价", "地基基础工作年限"),
    )
    steel_system: SteelSystem | None = Field(
        None,
        description="钢结构体系类型（仅在结构体系选“钢结构”时填写；不同体系最大适用高度不同）",
        json_schema_extra=_meta("—", "结构与造价", "钢结构体系", enum=list(STEEL_SYSTEMS)),
    )
    has_basement: bool | None = Field(
        None,
        description="是否设置地下室（超过 50 m 的钢结构房屋应设置地下室）",
        json_schema_extra=_meta("—", "结构与造价", "是否设地下室"),
    )
    # —— 构件与构造（GB 55008—2021 第4.4节的最小截面与配筋要求）—— #
    # 这些都是"设计输出"，但都是强制下限；填了就能判，不填按"数据不足"处理，
    # 不会误判为通过——这正是本系统对设计输出类字段的一贯口径。
    shear_wall_thickness: float | None = Field(
        None,
        description="剪力墙截面厚度（高层 ≥160 mm、多层 ≥140 mm；错层处 ≥250 mm）",
        gt=0,
        json_schema_extra=_meta("mm", "结构与造价", "剪力墙截面厚度"),
    )
    frame_beam_width: float | None = Field(
        None,
        description="矩形截面框架梁的截面宽度（不应小于 200 mm）",
        gt=0,
        json_schema_extra=_meta("mm", "结构与造价", "框架梁截面宽度"),
    )
    frame_column_shape: ColumnShape | None = Field(
        None,
        description="框架柱截面形状（矩形柱按边长、圆形柱按直径判定）",
        json_schema_extra=_meta("—", "结构与造价", "框架柱截面形状", enum=list(COLUMN_SHAPES)),
    )
    frame_column_size: float | None = Field(
        None,
        description="框架柱截面尺寸（矩形填边长、圆形填直径：≥300 / ≥350 mm）",
        gt=0,
        json_schema_extra=_meta("mm", "结构与造价", "框架柱截面尺寸"),
    )
    raft_rebar_ratio: float | None = Field(
        None,
        description="筏形 / 桩筏基础底板上下贯通钢筋配筋率（不应小于 0.15%，填百分数）",
        gt=0,
        json_schema_extra=_meta("%", "结构与造价", "筏基底板贯通筋配筋率"),
    )
    foundation_depth: float | None = Field(
        None,
        description="基础埋置深度（超过 50 m 的钢结构：天然地基不宜小于 H/15、桩基不宜小于 H/20）",
        gt=0,
        json_schema_extra=_meta("m", "结构与造价", "基础埋置深度"),
    )
    has_staggered_floor: bool | None = Field(
        None,
        description="是否存在错层（错层处柱、平面外受力剪力墙有专门的截面与混凝土要求）",
        json_schema_extra=_meta("—", "结构与造价", "是否存在错层"),
    )
    staggered_concrete_grade: float | None = Field(
        None,
        description="错层处框架柱 / 平面外受力剪力墙的最低核定混凝土强度等级（填 C 后数值，不从全局结构等级推定）",
        gt=0,
        json_schema_extra=_meta("MPa", "结构与造价", "错层处构件混凝土等级"),
    )
    has_out_of_plane_staggered_wall: bool | None = Field(
        None,
        description="错层处是否存在平面外受力剪力墙（专业核定；未填写表示未核对）",
        json_schema_extra=_meta("—", "结构与造价", "错层处是否有平面外受力墙"),
    )
    staggered_wall_thickness: float | None = Field(
        None,
        description="错层处平面外受力剪力墙的最低核定截面厚度（不从一般剪力墙厚度推定）",
        gt=0,
        json_schema_extra=_meta("mm", "结构与造价", "错层处平面外受力墙厚度"),
    )
    is_single_span_frame: bool | None = Field(
        None,
        description="框架是否为单跨框架（钢结构：甲、乙类与高层丙类不应采用单跨框架）",
        json_schema_extra=_meta("—", "结构与造价", "是否单跨框架"),
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
    excavation_depth: float | None = Field(
        None,
        description="基坑开挖深度（用于危大工程判定：≥3m 须专项施工方案，≥5m 须专家论证）",
        gt=0,
        json_schema_extra=_meta("m", "施工与安全", "基坑开挖深度"),
    )
    formwork_height: float | None = Field(
        None,
        description="混凝土模板支撑搭设高度（用于危大工程判定：≥5m 须专项方案，≥8m 须专家论证）",
        gt=0,
        json_schema_extra=_meta("m", "施工与安全", "模板支撑高度"),
    )
    scaffold_type: ScaffoldType | None = Field(
        None,
        description="外脚手架形式（附着式升降与悬挑式一律属危大工程）",
        json_schema_extra=_meta("—", "施工与安全", "脚手架形式", enum=list(SCAFFOLD_TYPES)),
    )
    scaffold_height: float | None = Field(
        None,
        description="脚手架搭设高度（落地式：≥24m 须专项方案，≥50m 须专家论证）",
        gt=0,
        json_schema_extra=_meta("m", "施工与安全", "脚手架搭设高度"),
    )
    retaining_type: RetainingType | None = Field(
        None,
        description="基坑支护形式（排桩 ≥C25、两墙合一下的地下连续墙 ≥C30）",
        json_schema_extra=_meta("—", "施工与安全", "基坑支护形式", enum=list(RETAINING_TYPES)),
    )
    retaining_wall_two_in_one: bool | None = Field(
        None,
        description="地下连续墙是否采用两墙合一（仅地下连续墙需核定，其他支护可填否；未填写表示未核对，不按否处理）",
        json_schema_extra=_meta("—", "施工与安全", "地下连续墙是否两墙合一"),
    )
    retaining_concrete_grade: float | None = Field(
        None,
        description="支护结构混凝土强度等级（填 C 后的数值；与上部结构分开填）",
        gt=0,
        json_schema_extra=_meta("MPa", "施工与安全", "支护混凝土强度等级"),
    )
    excavation_working_life: float | None = Field(
        None,
        description="基坑工程设计工作年限（不应小于 1 年）",
        gt=0,
        json_schema_extra=_meta("年", "施工与安全", "基坑工作年限"),
    )
    brace_type: BraceType | None = Field(
        None,
        description="基坑内支撑 / 锚拉体系（混凝土内支撑 ≥C25；锚杆自由段 ≥5.0m）",
        json_schema_extra=_meta("—", "施工与安全", "内支撑 / 锚拉体系", enum=list(BRACE_TYPES)),
    )
    brace_concrete_grade: float | None = Field(
        None,
        description="混凝土内支撑的混凝土强度等级（填 C 后数值；不从支护桩墙等级推定）",
        gt=0,
        json_schema_extra=_meta("MPa", "施工与安全", "内支撑混凝土强度等级"),
    )
    anchor_free_length: float | None = Field(
        None,
        description="锚杆自由段长度（不应小于 5.0 m）",
        gt=0,
        json_schema_extra=_meta("m", "施工与安全", "锚杆自由段长度"),
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
