# PR：T2 数据模型与方案 CRUD

## 做了什么

按 AGENTS.md "数据模型"一节落实 ProjectParams / SchemeParams / 评估结果 Pydantic 模型，并加上 SQLModel 持久化与项目 / 方案 CRUD。字段频繁调整是常态（10 月上旬还会动），所以设计上让"改字段只动 `app/models/params.py` 一个文件"。

### 模型 `backend/app/models/`

- **`params.py`** —— `ProjectParams`（5 字段）+ `SchemeParams`（19 字段）。每个字段都带 `description` / `unit` / `group` / `label`，写在 `json_schema_extra` 里；前端表单与 Excel 模板都从这里生成。
- **`eval.py`** —— `ComplianceItem` / `MetricResult` / `DimensionScores` / `RankResult` / `EvalResult`，结构对应 AGENTS.md 的结果 JSON 示例。`ComplianceStatus = "passed" | "failed" | "insufficient_data"`。
- **`orm.py`** —— `Project` / `Scheme` / `EvalResultRow` 三个 SQLModel 表。方案参数整体存 JSON 列；`is_whatif` 与 `parent_id` 在表顶层（不进 params）。

### 校验

- 面积 / 长度 / 数量 `> 0`
- 比例类字段 `0–1`（`density_max` / `inner_area_ratio` / `south_room_ratio` / `window_floor_ratio` / `std_floor_repeat` / `prefab_ratio_est`）；若用户填 1–100 的数，报 `请填小数，如 0.82（不要用百分数）`
- `window_wall_ratio` 是嵌套字典，对每个朝向的值做同样的 0–1 校验
- `structure_type` / `climate_zone` 走枚举；`structure_type` 五个值见下表
- `unit_mix` 之和必须等于 `units`（同时给两个时）
- `risk_features` 预设 `RISK_FEATURE_OPTIONS`，允许自定义
- `far_max`（容积率上限）**不**走 0–1 校验，因为它是无量纲系数（中国常见 0.5–4.0）

### 持久化 `backend/app/db.py`

- lazy engine：默认从 settings 读 SQLite URL；测试用 `override_engine_for_testing` 注入内存 SQLite
- `init_db()` 启动时建表，SQLite 路径父目录若不存在则自动创建

### 接口

```
POST   /api/projects                         # 创建项目
GET    /api/projects                         # 项目列表
GET    /api/projects/{id}                    # 项目详情
PUT    /api/projects/{id}                    # 更新项目
DELETE /api/projects/{id}                    # 删除项目（含其下方案与评估结果）

POST   /api/projects/{id}/schemes            # 新增方案
GET    /api/projects/{id}/schemes            # 方案列表（默认不返回 what-if）
GET    /api/projects/{id}/schemes?include_whatif=true
PUT    /api/projects/{id}/schemes/{sid}      # 更新方案
DELETE /api/projects/{id}/schemes/{sid}      # 删除方案

GET    /api/schema                           # 三套 schema 一起返回
GET    /api/schema/project                   # 项目参数
GET    /api/schema/scheme                    # 方案参数
GET    /api/schema/eval                      # 评估结果
```

### 工程

- `scripts/export_schema.py` 把与 `/api/schema` 同样的内容写到 `data/schema/*.schema.json`，前端 / Excel 模板生成器可直接消费。
- `main.py` 把 `app.mount("/api", ...)` 换成 `app.include_router(..., prefix="/api")`，让 `/docs` 拿到完整 OpenAPI（之前 mount 不会把子路由暴露到根 spec）。

## 如何运行

```bash
make dev-backend                       # 端口 8000，启动自动建表
curl http://127.0.0.1:8000/api/health # {"status":"ok","version":"0.1.0"}
# 打开 http://127.0.0.1:8000/docs 看完整字段说明与单位
```

导出 schema 到 `data/schema/`：

```bash
uv run --project backend python scripts/export_schema.py
```

## 如何测试

```bash
make test         # = cd backend && uv run pytest   （35 项）
make lint         # = ruff check . + 前端 tsc
```

### 实测结果（本机）

```
$ uv run ruff check .
All checks passed!

$ uv run pytest
tests/test_db_crud.py ............                                       [ 34%]
tests/test_health.py .                                                   [ 37%]
tests/test_models_params.py ..................                           [ 88%]
tests/test_schema_endpoint.py ....                                       [100%]
======================== 35 passed, 1 warning in 0.29s ========================
```

`/docs` 页面每个字段都带中文 description / label / unit / group（已用 `/openapi.json` 验证）。

## 字段清单（人工审核用）

### ProjectParams（5 字段，全 Optional）

| 字段名 | 中文名 | 单位 | 分组 | 必填 |
|---|---|---|---|---|
| site_area | 用地面积 | m² | 基本信息 | 否 |
| far_max | 容积率上限 | — | 基本信息 | 否 |
| density_max | 建筑密度上限 | — | 基本信息 | 否 |
| height_max | 限高上限 | m | 基本信息 | 否 |
| climate_zone | 气候分区 | — | 基本信息 | 否 |

### SchemeParams（19 字段，除 risk_features 外全 Optional）

| 字段名 | 中文名 | 单位 | 分组 | 必填 |
|---|---|---|---|---|
| structure_type | 结构体系 | — | 基本信息 | 否 |
| units | 总户数 | 户 | 基本信息 | 否 |
| unit_mix | 户型配比 | 户 | 基本信息 | 否 |
| floor_height | 层高 | m | 居住品质 | 否 |
| inner_area_ratio | 得房率 | — | 居住品质 | 否 |
| south_room_ratio | 南向比例 | — | 居住品质 | 否 |
| window_floor_ratio | 窗地比 | — | 居住品质 | 否 |
| window_wall_ratio | 窗墙比 | — | 居住品质 | 否 |
| elevators_per_unit | 电梯数/单元 | 台 | 居住品质 | 否 |
| gfa | 总建筑面积 | m² | 结构与造价 | 否 |
| footprint | 基底面积 | m² | 结构与造价 | 否 |
| buildings | 楼栋数 | 栋 | 结构与造价 | 否 |
| floors | 层数 | 层 | 结构与造价 | 否 |
| envelope_area | 外表面积 | m² | 结构与造价 | 否 |
| volume | 建筑体积 | m³ | 结构与造价 | 否 |
| std_floor_repeat | 标准层重复率 | — | 施工与安全 | 否 |
| component_types | 预制构件种类 | 种 | 施工与安全 | 否 |
| risk_features | 风险特征 | — | 施工与安全 | 否 |
| prefab_ratio_est | 预估装配率 | — | 绿色低碳 | 否 |

注：方案 `name` 不在 SchemeParams 里，它是 SQLModel `Scheme` 表的字段（项目内必填且唯一）。

## 枚举值

- `structure_type`：`剪力墙` / `框架-剪力墙` / `框架` / `钢结构` / `MiC`
- `climate_zone`：`严寒` / `寒冷` / `夏热冬冷` / `夏热冬暖` / `温和`
- `RISK_FEATURE_OPTIONS`（预设）：`大悬挑` / `高大空间` / `深基坑` / `高支模` / `超长结构` / `不规则建筑` / `超限构件` / `复杂地质`

## 设计选择与注意点

1. **派生量不放进模型**：例如单位面积造价 / 体形系数 / 容积率实际值等由引擎（T3 起）从原始字段推导，不让它们出现在 Pydantic 模型里，避免改一次字段要同步多处。
2. **`far_max` 不走 0-1 校验**：容积率在中国是 0.5–4.0 的无量纲系数（如 2.5），不是百分比。误判会导致用户填不进去。
3. **`window_wall_ratio` 用 dict[str, float]**：AGENTS.md 写"各朝向窗墙比"，所以按朝向分键，而不是拆成多个字段。校验递归到每个 value。
4. **`unit_mix` 用 dict[str, int]（户数）而不是比例**：AGENTS.md 标的是 "户 / —"，与 `units`（总户数）做求和校验更直观。后续若需要比例形式，加一个 `unit_mix_ratio` 派生字段即可。
5. **方案 `params` 整体存 JSON**：字段会变，避免每加一个字段就跑迁移；读取时统一走 `SchemeParams.model_validate(...)` 重新校验，旧数据也能补字段。
6. **删除是级联的**：删项目会连同方案与评估结果一起清掉；删方案同理。SQLite 没有 CASCADE，所以手动循环删除。
7. **what-if 默认隐藏**：列表接口默认不返回 `is_whatif=true` 的方案，要看全部需 `?include_whatif=true`。这是 T8 假设推演的基础设施。
8. **路由从 `app.mount` 改为 `include_router(..., prefix="/api")`**：前者不会把子路由暴露到根 OpenAPI，`/docs` 看不到字段说明；后者能。

## 遗留问题

1. **ORM 模型没有 `updated_at` 触发器**：SQLAlchemy 的 `onupdate` 钩子在 SQLite + 显式赋值时不会自动触发，所以 API 层显式调用了 `datetime.now(UTC)`。切到 PostgreSQL 时可以改 server-side default。
2. **`backend/data/zhuheng.db` 在本地 `make dev-backend` 时被自动创建**：`.gitignore` 已忽略 `backend/data/`，所以不会入仓；CI 上若想把 sqlite 文件丢进产物挂卷，记得挂这个目录。
3. **`density_max` 的中文 label 是"建筑密度上限"，不带"小数"二字**：用户填 30 时会看到 `请填小数，如 0.82（不要用百分数）`，提示够了；要不要在 description 里再追加一句"必须填 0-1 小数"留给前端 review。
4. **`structure_type` 写了"框架-剪力墙"，AGENTS.md 原表里是"框剪"**：与 T1 任务描述里指定的五个枚举值一致；术语表里有冲突时以任务描述为准。
5. **绿色低碳组只有一个字段**（`prefab_ratio_est`）：T4 评估指标可以再加 `envelope_per_volume` / `carbon_intensity` 之类；现在留空没影响。
6. **未提供 import_schemes.py**：任务里没要求批量导入，留到 T2 后续或独立任务再加。
7. **`db.py` 的 `_build_engine` 用 `from pathlib import Path` 引入再路径解析**：相对路径语义（`./data/zhuheng.db`）依赖 `Path.cwd()`；若有人改了 uvicorn 启动目录，db 落点会跟着变。Docker compose 里 `WORKDIR=/app`，落到 `/app/data/`；本地 `make dev-backend` 落到 `backend/data/`。两者路径不同，已分别写入 `.gitignore`。