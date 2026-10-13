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

## 二、方案参数（SchemeParams）

### 方案参数

方案层（设计输入）参数，每个候选方案独立

#### 基本信息

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `structure_type` | 结构体系 | — | string | 否 · 必录 | 取值：剪力墙 / 框架-剪力墙 / 框架 / 钢结构 / MiC；— |
| `mic_system` | MiC 体系类型 | — | string | 否 | 取值：模块化框架结构 / 模块化全预制剪力墙结构 / 模块化叠合剪力墙结构 / 模块化箱模框架结构 / 模块化箱模框架-剪力墙结构 / 模块化箱模剪力墙结构；— |
| `units` | 总户数 | 户 | integer | 否 · 必录 | — |
| `unit_mix` | 户型配比 | 户 | object<integer> | 否 | — |

#### 居住品质

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `floor_height` | 层高 | m | number | 否 | — |
| `inner_area_ratio` | 得房率 | — | number | 否 | — |
| `south_room_ratio` | 南向比例 | — | number | 否 | — |
| `window_floor_ratio` | 窗地比 | — | number | 否 | — |
| `window_wall_ratio` | 窗墙比 | — | object<number> | 否 | — |
| `elevators_per_unit` | 电梯数/单元 | 台 | integer | 否 | — |
| `daylight_factor` | 采光系数 | — | number | 否 | — |
| `sunlight_hours` | 日照时数 | h | number | 否 | — |

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

#### 绿色低碳

| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- | --- |
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
