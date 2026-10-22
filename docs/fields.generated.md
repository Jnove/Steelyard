# 字段对照表（自动生成）

> 本文件由 `scripts/gen_field_table.py` 从 `data/schema/*.schema.json` 渲染，**不要手改**。模型或字段元信息变更后，请重新运行脚本：
> 
> ```bash
> uv run --project backend python scripts/gen_field_table.py
> ```

CI 会跑 `gen_field_table.py --check`，结果与磁盘不一致即失败，防止文档与代码漂移。


## 一、项目参数（ProjectParams）

### 项目参数

项目层（地块条件）参数，对所有候选方案相同

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `site_area` | 用地面积 | m² | number | 否 · 必录 | — |
| `far_max` | 容积率上限 | — | number | 否 | — |
| `density_max` | 建筑密度上限 | — | number | 否 | — |
| `height_max` | 限高上限 | m | number | 否 | — |
| `climate_zone` | 气候分区 | — | string | 否 | 取值：严寒 / 寒冷 / 夏热冬冷 / 夏热冬暖 / 温和；— |
| `seismic_intensity` | 抗震设防烈度 | — | string | 否 | 取值：6度(0.05g) / 7度(0.10g)；— |
| `province` | 所在省份 | — | string | 否 | 取值：BJ / TJ / HE / SX / NM / LN / JL / HL / SH / JS / ZJ / AH / FJ / JX / SD / HA / HB / HN / GD / GX / HI / CQ / SC / GZ / YN / XZ / SN / GS / QH / NX / XJ；预设：BJ / TJ / HE / SX / NM / LN / JL / HL / SH / JS / ZJ / AH / FJ / JX / SD / HA / HB / HN / GD / GX / HI / CQ / SC / GZ / YN / XZ / SN / GS / QH / NX / XJ；— |
| `standard_packs` | 适用标准册 | — | array<string> | 否 | 预设：GB / BJ / TJ / HE / SX / NM / LN / JL / HL / SH / JS / ZJ / AH / FJ / JX / SD / HA / HB / HN / GD / GX / HI / CQ / SC / GZ / YN / XZ / SN / GS / QH / NX / XJ；— |
| `project_notes` | 案例来源与边界 | — | string | 否 | — |
| `scoring_exclusions` | 暂不纳入评分的代理指标 | — | array<string> | 否 | 预设：G-05 / Q-05 / Q-06；— |

## 二、方案参数（SchemeParams）

### 方案参数

方案层（设计输入）参数，每个候选方案独立

#### 基本信息

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `structure_type` | 结构体系 | — | string | 否 · 必录 | 取值：剪力墙 / 框架-剪力墙 / 框架 / 钢结构 / MiC；— |
| `mic_system` | MiC 体系类型 | — | string | 否 | 取值：模块化框架结构 / 模块化全预制剪力墙结构 / 模块化叠合剪力墙结构 / 模块化箱模框架结构 / 模块化箱模框架-剪力墙结构 / 模块化箱模剪力墙结构；— |
| `mic_precast_wall_shear_ratio` | 预制墙底剪力占比 | — | number | 否 | — |
| `scheme_notes` | 方案数据说明 | — | string | 否 | — |
| `units` | 总户数 | 户 | integer | 否 · 必录 | — |
| `unit_mix` | 户型配比 | 户 | object<integer> | 否 | — |
| `custom` | 自定义字段 | — | object<any> | 否 | — |

#### 居住品质

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `floor_height` | 层高 | m | number | 否 | — |
| `inner_area_ratio` | 得房率 | — | number | 否 | — |
| `south_room_ratio` | 南向比例 | — | number | 否 | — |
| `window_floor_ratio` | 窗地比 | — | number | 否 | — |
| `window_wall_ratio` | 窗墙比 | — | object<number> | 否 | — |
| `elevators_per_unit` | 电梯数/单元 | 台 | integer | 否 | — |
| `highest_occupied_floor` | 最高住宅入户层 | 层 | integer | 否 | — |
| `highest_occupied_floor_height` | 最高入户层楼面高度 | m | number | 否 | — |
| `daylight_factor` | 采光系数 | — | number | 否 | — |
| `sunlight_hours` | 日照时数 | h | number | 否 | — |
| `daylight_standard_day` | 日照标准日 | — | string | 否 | 取值：大寒日 / 冬至日；— |
| `living_space_count` | 居住空间总数 | 个 | integer | 否 | — |
| `daylight_room_count` | 满足日照空间数 | 个 | integer | 否 | — |
| `clear_height` | 室内净高 | m | number | 否 | — |
| `has_fresh_air` | 设新风/中央空调 | — | boolean | 否 | — |
| `has_stretcher_elevator` | 设担架电梯 | — | boolean | 否 | — |
| `has_accessible_elevator` | 设无障碍电梯 | — | boolean | 否 | — |
| `total_elevators` | 电梯总台数 | 台 | integer | 否 | — |

#### 结构与造价

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `gfa` | 总建筑面积 | m² | number | 否 · 必录 | — |
| `footprint` | 基底面积 | m² | number | 否 | — |
| `buildings` | 楼栋数 | 栋 | integer | 否 | — |
| `floors` | 层数 | 层 | integer | 否 · 必录 | — |
| `envelope_area` | 外表面积 | m² | number | 否 | — |
| `volume` | 建筑体积 | m³ | number | 否 | — |
| `slab_thickness` | 楼板厚度 | mm | number | 否 | — |
| `design_working_life` | 结构设计工作年限 | 年 | integer | 否 | — |
| `min_plan_width` | 最小平面宽度 | m | number | 否 | — |
| `concrete_grade` | 混凝土强度等级 | MPa | number | 否 | — |
| `structural_height_classification` | 结构高度分类 | — | string | 否 | 取值：高层 / 多层；— |
| `foundation_type` | 基础形式 | — | string | 否 | 取值：筏形基础 / 桩筏基础 / 独立基础 / 条形基础 / 桩基础；— |
| `foundation_concrete_grade` | 基础混凝土强度等级 | MPa | number | 否 | — |
| `foundation_working_life` | 地基基础工作年限 | 年 | integer | 否 | — |
| `steel_system` | 钢结构体系 | — | string | 否 | 取值：框架 / 框架-中心支撑 / 框架-偏心支撑（延性墙板） / 筒体和巨型框架；— |
| `has_basement` | 是否设地下室 | — | boolean | 否 | — |
| `shear_wall_thickness` | 剪力墙截面厚度 | mm | number | 否 | — |
| `frame_beam_width` | 框架梁截面宽度 | mm | number | 否 | — |
| `frame_column_shape` | 框架柱截面形状 | — | string | 否 | 取值：矩形 / 圆形；— |
| `frame_column_size` | 框架柱截面尺寸 | mm | number | 否 | — |
| `raft_rebar_ratio` | 筏基底板贯通筋配筋率 | % | number | 否 | — |
| `foundation_depth` | 基础埋置深度 | m | number | 否 | — |
| `has_staggered_floor` | 是否存在错层 | — | boolean | 否 | — |
| `staggered_concrete_grade` | 错层处构件混凝土等级 | MPa | number | 否 | — |
| `has_out_of_plane_staggered_wall` | 错层处是否有平面外受力墙 | — | boolean | 否 | — |
| `staggered_wall_thickness` | 错层处平面外受力墙厚度 | mm | number | 否 | — |
| `is_single_span_frame` | 是否单跨框架 | — | boolean | 否 | — |
| `irregularity_items` | 超限不规则项 | — | array<string> | 否 | 预设：扭转不规则 / 凹凸不规则 / 楼板不连续 / 刚度突变 / 尺寸突变 / 构件间断 / 承载力突变 / 局部不规则 / 高位转换 / 厚板转换 / 复杂连接 / 多重复杂；— |

#### 施工与安全

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `std_floor_repeat` | 标准层重复率 | — | number | 否 | — |
| `component_types` | 预制构件种类 | 种 | integer | 否 | — |
| `risk_features` | 风险特征 | — | array<string> | 否 | 预设：大悬挑 / 高大空间 / 深基坑 / 高支模 / 超长结构 / 不规则建筑 / 超限构件 / 复杂地质；— |
| `excavation_depth` | 基坑开挖深度 | m | number | 否 | — |
| `formwork_height` | 模板支撑高度 | m | number | 否 | — |
| `scaffold_type` | 脚手架形式 | — | string | 否 | 取值：落地式钢管脚手架 / 附着式升降脚手架 / 悬挑式脚手架；— |
| `scaffold_height` | 脚手架搭设高度 | m | number | 否 | — |
| `retaining_type` | 基坑支护形式 | — | string | 否 | 取值：排桩 / 地下连续墙 / 土钉墙 / 放坡开挖 / 其他；— |
| `retaining_wall_two_in_one` | 地下连续墙是否两墙合一 | — | boolean | 否 | — |
| `retaining_concrete_grade` | 支护混凝土强度等级 | MPa | number | 否 | — |
| `excavation_working_life` | 基坑工作年限 | 年 | number | 否 | — |
| `brace_type` | 内支撑 / 锚拉体系 | — | string | 否 | 取值：混凝土内支撑 / 钢支撑 / 锚杆（锚拉） / 无内支撑与锚拉；— |
| `brace_concrete_grade` | 内支撑混凝土强度等级 | MPa | number | 否 | — |
| `anchor_free_length` | 锚杆自由段长度 | m | number | 否 | — |

#### 绿色低碳

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `per_capita_green` | 人均公共绿地 | m²/人 | number | 否 | — |
| `sx_land_use_class` | 山西用地类别 | — | string | 否 | 取值：低层 / 多层Ⅰ类 / 多层Ⅱ类 / 高层Ⅰ类；— |
| `prefab_ratio_est` | 预估装配率 | — | number | 否 | — |
| `green_ratio` | 绿地率 | — | number | 否 | — |

## 三、评估结果（EvalResult）

### 方案评估结果

合规清单 + 指标值 + 维度得分 + 排名，一并交给报告生成器

| 字段名 | 中文名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `scheme_id` | scheme_id | string | 是 | — |
| `scheme_name` | scheme_name | string | 否 | — |
| `compliance` | compliance | array<string> | 否 | — |
| `metrics` | metrics | object<string> | 否 | — |
| `dimension_scores` | dimension_scores | string | 否 | — |
| `dimension_coverage` | dimension_coverage | string | 否 | — |
| `topsis` | topsis | string | 否 | — |

## 四、派生量

### 派生量（引擎在评估时计算，不在 Pydantic 模型里）

规则和指标里可以直接用 ``value`` 引用下面的字段名，效果等同于评估时算出的数。

| 字段名 | 中文名 | 单位 | 公式 | 说明 |
| --- | --- | --- | --- | --- |
| `far` | 容积率 | — | `gfa / site_area` | 总建筑面积与用地面积之比；与项目层 far_max 比较即可判上限。 |
| `density` | 建筑密度 | — | `footprint / site_area` | 基底面积与用地面积之比，0–1 小数；与项目层 density_max 比较。 |
| `shape_coef` | 体形系数 | — | `envelope_area / volume` | 外表面积与体积之比，越小越利于节能。 |
| `height` | 建筑总高 | m | `floors * floor_height` | 层数乘层高；与项目层 height_max 比较即可判限高。 |
| `units_per_building` | 单栋户数 | 户/栋 | `units / buildings` | 疏散与电梯服务的关键指标。 |
| `units_per_floor` | 每层户数 | 户/层 | `units / (floors * buildings)` | 决定标准层交通核大小。 |
| `floor_efficiency` | 楼层效率 | — | `footprint * floors / gfa` | 基底与层数对总建筑面积的利用率，越接近 1 越理想。 |
| `height_width_ratio` | 高宽比 | — | `floors * floor_height / min_plan_width` | 建筑总高与最小平面宽度之比；JGJ 3—2010 第3.3.2条 表3.3.2 给出上限，用词为「不宜」。 |
