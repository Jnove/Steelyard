# 自定义添加：设计说明

> 状态：**设计中**（2026-10）。本文决定"运行期自定义添加"这件事怎么做，
> 以及为什么这么做。实现按文末的分片计划推进。
>
> 涉及四类自定义内容：**字段 / 参数、规则 / 指标、角色权重模板、枚举选项**。

---

## 一、要解决的根本矛盾

现有架构是**构建期生成**的一条链：

```
backend/app/models/params.py
  → scripts/export_schema.py        → data/schema/*.json
  → scripts/gen_field_table.py      → docs/fields.generated.md
  → scripts/make_template.py        → data/schemes/方案录入模板.xlsx
  → frontend npm run gen:types      → frontend/src/api/generated/*.ts
  → frontend npm run sync:mock      → 前端 mock 里的 schema 与样例副本
```

CI 会重新跑这条链并要求 `git diff --exit-code` 干净（见 `docs/archive/professional-rules-2026-10.md` §8.3）。
规则侧同理：`rules/*.yaml` 是唯一权威，`scripts/check_rules.py` 与引擎**共用同一套模型**
（`RuleDef` + `analyze_expression`），所以"check_rules 说通过"与"引擎能加载"永远是一回事。

**而"自定义添加"要求运行期就能加字段和规则。** 直接改 `params.py` / `rules/*.yaml`
是不可接受的：那是构建产物，改了就要人肉跑整条链、还会绕过评审与 CI。

### 决策：**覆盖层（overlay）**，而不是改构建产物

内建内容仍走构建期生成；自定义内容进入**独立的覆盖层**，在运行期与内建内容合并：

| 层 | 权威来源 | 谁能改 | 什么时候生效 |
| --- | --- | --- | --- |
| 内建 | `params.py` + `rules/*.yaml` | 开发者，走 git + CI | 构建 / 重启 |
| 自定义（覆盖层） | 数据库表 | 使用者在界面上 | 保存即生效 |

**覆盖层永远不能改变内建内容**：不能覆盖同名内建字段、不能占用已存在的规则 ID。
冲突的直接拒绝保存。

### 第二条决策：自定义是**草稿台**，最终权威仍是 YAML + git

覆盖层提供**导出**功能：把定稿的自定义内容导出成 `rules/*.yaml` 片段与 `params.py` 字段片段，
由开发者提交进仓库，随后从覆盖层移除。这样：

- 专业化、需要评审的规则最终仍然进 git、受 CI 保护；
- 探索期、只针对某个项目的一次性指标可以留在覆盖层；
- 生产环境可以**关闭自定义写入**（见第六节），避免有人绕过 CI 改规则。

---

## 二、数据模型

新增 4 张表（SQLModel，随现有 SQLite 一起迁移）：

### 2.1 `custom_field`（自定义字段）

| 列 | 说明 |
| --- | --- |
| `key` | 字段名（英文小写下划线，唯一；不得与内建字段/派生量重名） |
| `label` / `unit` / `group` | 中文名 / 单位 / 所属分组（分组沿用 `GROUP_ORDER` 五项） |
| `kind` | `number` / `ratio`（0–1 小数）/ `enum` / `list` |
| `options` | `enum`、`list` 的候选值 |
| `description` | 说明（进 schema 的 description） |
| `enabled` / `created_at` / `created_by` | 开关与审计 |

### 2.2 `custom_rule`（自定义规则）

| 列 | 说明 |
| --- | --- |
| `id` | 规则 ID（如 `X-01`；不得与内建规则 ID 重复，全局唯一） |
| `name` / `type`（hard/metric）/ `dimension` | 与内建规则同构 |
| `when` / `check` / `message` / `severity` | hard 用 |
| `value` / `scoring` / `weight_in_dimension` | metric 用 |
| `source` | 出处（沿用"规范编号+条号"或"经验规则（…组）：理由"两种写法） |
| `enabled` / `created_at` / `created_by` | 开关与审计 |

### 2.3 `weight_template`（自定义角色权重模板）

`name` / `note` / `source` / `matrix`（4×4，存 JSON）/ `weights`（或直接给四个数）/ 审计列。
与 `rules/weights.yaml` 的四个角色**并列**出现在前端下拉框里，内建四个不可编辑。

### 2.4 `custom_option`（自定义枚举选项）

`field`（`risk_features` / `irregularity_items` / 某个自定义 `enum` 字段）/ `value` / 排序 / 审计列。
读取预设时 = 内建选项（`RISK_FEATURE_OPTIONS` 等）+ 该表的自定义项。

---

## 三、引擎侧改动（最小侵入）

### 3.1 方案层加一个保留字段 `custom`

`SchemeParams` 增加：

```python
custom: dict[str, float | int | str | list[str]] = Field(default_factory=dict)
```

自定义字段的值都存在这里，**不动态造 Pydantic 模型**（动态模型会牵动校验、序列化、
OpenAPI 与前端类型，代价远大于收益）。

### 3.2 命名空间摊平

`build_namespace(project, scheme.params)` 在合并完成后，把 `custom` 里的键**摊平到顶层**，
于是规则里可以像引用内建字段那样写 `my_custom_ratio >= 0.5`。

`known_field_names()` 增加"自定义字段名"这一来源（从注册表读），
这样 `analyze_expression` 的字段存在性检查、`check_rules`、前端补全都跟着一致。

### 3.3 规则集合并

引擎加载 = `load_rules_from_dir(rules/)` + 数据库里的 `custom_rule`。
- 加载前对自定义规则跑**与 check_rules 完全相同**的校验（`RuleDef` 模型 + `analyze_expression`
  + points 单调性与分值范围 + ID 唯一性），不通过直接拒绝保存并把中文报错返回界面；
- `/api/rules/reload`（dev 专用）同时重载两者；
- 自定义规则与内建规则在报告里同样带 `rule_id` / `source` / `formula`，溯源能力不降级。

### 3.4 不变式（必须守住）

1. `check_rules` 通过 ⟺ 引擎能加载（自定义规则复用同一套校验，不另写一套）；
2. 内建产物（schema / 字段表 / Excel 模板 / 前端类型）与提交内容保持一致（CI 不变）；
3. 覆盖层不得覆盖内建字段名、派生量名、规则 ID、角色名；
4. 关掉覆盖层（清表或关闭开关）后，系统回到与纯内建完全一致的行为。

---

## 四、API 设计

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST/PATCH/DELETE | `/api/custom/fields` | 自定义字段 CRUD（POST 前做重名与类型校验） |
| GET/POST/PATCH/DELETE | `/api/custom/rules` | 自定义规则 CRUD（保存前跑校验器，失败返回 422 + 中文报错） |
| GET/POST/DELETE | `/api/custom/weight-templates` | 权重模板 CRUD（保存前做互反性与 CR 检查） |
| GET/POST/DELETE | `/api/custom/options` | 枚举选项 CRUD |
| GET | `/api/custom/export` | 导出为 `rules/*.yaml` 片段 + `params.py` 字段片段（见第一节第二条决策） |
| GET | `/api/schema`（改造） | 把自定义字段并入 `scheme_params`、把自定义选项并入 `options` |

写接口受 `APP_ENV` 约束：**默认只在 dev 开放**，与 `/api/rules/reload` 的处理保持一致。

---

## 五、前端

- **方案表单**：已按 `/api/schema` 动态渲染，自定义字段自动出现（按 `group` 落到对应 tab）；
- **新增「自定义」设置页**：四个 tab —— 字段 / 规则 / 权重模板 / 枚举选项；
  规则编辑器提供"选字段 + 填阈值或分段点"的表单式写法，并即时显示校验报错；
- **排序页**：角色下拉框 = 内建四个角色 + 自定义权重模板；
- **方案录入 Excel 模板**：`make_template.py` 仍只生成内建字段（构建期产物不变），
  另提供运行期导出接口，把自定义字段**追加为额外列**；导入时把自定义列写进 `custom`。

---

## 六、生产开关与审计

- `APP_ENV=prod` 时**关闭所有自定义写接口**（403），只读；
- 所有自定义记录带 `created_at` / `created_by`（先落一个简单的操作者标识，
  后续接登录时替换）；
- 前端对自定义规则/字段显示"未进入 git、不参与 CI 校验"的提示，避免被当成已评审内容。

---

## 七、分片计划与验收标准

| 片 | 内容 | 验收 |
| --- | --- | --- |
| **1** | 自定义枚举选项 + 自定义角色权重模板 | 新增选项后 `/api/schema` 与表单下拉出现；新增模板后排序页可选且 CR<0.1 校验生效；清表后行为与内建一致 |
| **2** | 自定义字段（`custom` 保留字段 + 摊平 + schema/表单/Excel 动态列） | 新字段出现在表单与 Excel 导出列；规则可引用；`known_field_names` 含该字段；内建产物零 diff |
| **3** | 自定义规则（校验同源 + 规则合并 + 编辑器 + 导回 YAML） | 非法规则被拒并给中文原因；合法规则参与评估与报告溯源；导出片段可直接提交进 `rules/` 并通过 CI |
| **4** | 权限与审计完善、生产开关、文档 | prod 下写接口 403；审计字段齐全；`docs/` 更新完毕 |

每片结束都要：跑 `check_rules` + `pytest` + 前端测试、重跑生成链确认零 diff、
更新 `docs/open-items.md`，并推送到 `jnove/professional-rules`。

---

## 八、明确**不做**的事

- **不让自定义内容覆盖或删除内建字段、派生量、规则、角色**——只做"追加"；
- **不在运行期改 `params.py` / `rules/*.yaml`**——它们仍是构建产物，由 git 与 CI 管；
- **不为自定义字段动态生成 Pydantic 模型**——统一走 `custom` 字典 + 注册表，
  避免牵动 OpenAPI / 前端类型生成；
- **不把覆盖层当作最终权威**——定稿内容要经 `/api/custom/export` 回灌到仓库。

---

## 九、实现进度

### 片 1：自定义枚举选项 + 自定义角色权重模板（2026-10）

**已实现**

| 部分 | 位置 | 要点 |
| --- | --- | --- |
| 开放枚举标记 | `app/models/params.py` | `risk_features` / `irregularity_items` 加 `extensible=True`；**只有打了标的字段**才允许追加候选值 |
| 覆盖层表 | `app/custom/models.py` | `custom_options`（字段+值唯一）、`custom_weight_templates` |
| 选项读写与合并 | `app/custom/options.py` | 追加 / 删除 / 并入增强 schema；**内建候选值永远在前且不被替换** |
| 模板校验 | `app/custom/templates.py` | 复用 `app.engine.weights.check_one_role`（校验同源）；矩阵 CR ≥ 0.1 直接拒绝 |
| 接口 | `app/api/custom.py` | `GET/POST/DELETE /api/custom/options`、`…/weight-templates`；**写接口仅 dev**，读接口放开 |
| Schema 合并 | `app/api/schema.py` | `GET /api/schema` = 内建基线 + 自定义选项，并给出 `custom_options` 便于前端区分 |
| 排序接入 | `app/api/rank.py` | `role` 先查内建、再查自定义（`custom:<id>` 或模板名）；响应新增 `is_custom` |
| 前端 | `DashboardPage.tsx` | 决策视角下拉 = 内建四角色 + 自定义模板（带"（自定义）"后缀）+ 自定义滑杆 |

**为什么封闭枚举必须拒绝**：`structure_type`、`mic_system`、`climate_zone`、`seismic_intensity`
这些字段的取值是**规则的分支条件**。给它加一个规则不认识的取值，相关规则会静默判成"不适用"
——比报错更危险。所以扩展白名单是**显式声明**的（`extensible=True`），而不是"有 options 就能加"。

**验证**（`ruff` 干净、`pytest` 500 通过、`check_rules` 0/0、前端 `tsc` 与 52 个测试通过）：

- 新增选项后出现在 `GET /api/schema`，且只影响它挂的字段；删除后恢复原样；
- `structure_type` 被拒，报错里说清"会让规则静默失效"；
- 重复内建值 / 重复添加 / 空值 / 超长值分别给不同的中文原因；
- 自相矛盾的矩阵（CR = 0.243）被拒，并回传引擎自己的改法建议；
- 自定义模板可用 `custom:<id>` 与模板名两种方式参与排序，`weights_used.is_custom = true`，
  `note` 里带"未进入 git、不参与 CI 校验"；
- 删除模板后排序接口报"没有角色 …"并列出可选值；清空覆盖层后行为与纯内建一致；
- `APP_ENV=prod` 时写接口 403、读接口正常。

**顺带修掉一个真 bug**：`AgentTools.cache_key` 原来只把 `rules/weights.yaml` 的角色模板计入缓存键，
运行期自定义模板改了不会让报告缓存失效。现已把自定义模板一并计入。

**片 1 未完成**：自定义设置页（选项与模板的增删界面）。能力已可用——表单下拉会自动带出
自定义选项，决策视角下拉会列出自定义模板——只是增删目前只能走 API。见 `docs/open-items.md` §2.7。

**下一片（片 2）**：自定义字段。
