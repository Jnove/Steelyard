# 自定义添加：设计说明

> 状态：**后端已实现，管理界面待做**（2026-10-13）。本文保留设计与分片记录；
> 本次合并修复及验收以 [集成评审](rules-round2-custom-integration.md) 为准。
> 当前只有 `risk_features` 开放追加候选；`irregularity_items` 保持封闭专业清单。
> 内建角色现有五个。现有录入表单支持 `params.custom`，动态 Excel 入口为
> `GET /api/excel/template` 与 `GET /api/excel/projects/{id}/export`。
> 生产自定义写接口关闭；地区选择、规则版本与地域适用性配置尚未实现。
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
与 `rules/weights.yaml` 的五个角色**并列**出现在前端下拉框里，内建角色不可编辑。

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

**生产开关**：`APP_ENV=prod` 时**关闭所有自定义写接口**（403），读接口照常开放
（前端要能渲染使用者加的选项、模板、字段与留痕）。理由与 `POST /api/rules/reload` 同一口径：
生产环境的规则与字段变更应当走 Git 提交 + CI 校验，而不是在线上悄悄改。

**审计（片 4 已落地）**：

- 单独一张 `custom_audit` 表，记录"发生过什么"（四张内容表记录"现在有什么"）；
- **只追加**：只有 `record` 与 `list_entries`，没有修改与删除接口——能被改的留痕没有意义；
  清空自定义内容时也不应连带清掉它，否则就查不出"谁删的"；
- **与业务写操作同一个事务**：`record` 只 `add` + `flush`、**不 commit**，
  由调用方那次写操作一起提交，于是"改成功但没留痕"或"留痕了但没改成功"都不会发生；
- 四类内容的**新增与删除**都埋点（选项 / 模板 / 规则 / 字段），删除时先把原值写进
  `detail` 再删，否则删完就说不清"删掉的是什么"；
- 读接口 `GET /api/custom/audit`，新的在前，`limit` 默认 100、上限 500；
- 每条记录带 `operator` / `action` / `kind` / `target` / `summary` / `detail`，
  界面展开一条就能看到当时到底改了什么。

**操作者标识（占位实现，接入登录后替换）**：取自可选的 `X-Operator` 头。
头可以伪造，所以**生产写接口本身是关的**，这个标识用于开发环境内的自查与演示，
**不作为权限判据**。归一化规则（`app/custom/audit.py::normalize_operator`）：

- **HTTP 头按规范只能是 ASCII**，所以中文名必须由客户端**百分号编码**后传
  （浏览器里 `encodeURIComponent('张三')`），后端解回 UTF-8；
  推荐直接用**工号**这类 ASCII 标识，中文名则用百分号编码——这一条是写测试时被
  httpx 的 `UnicodeEncodeError` 逼出来的真实限制，不是设想；
- 控制字符清掉、空白折叠、超长截断（64 字符上限）；
- 空值统一成 `anonymous`（留痕里的空值最难解释）。

**前端提示**：对自定义规则 / 字段显示"未进入 git、不参与 CI 校验"，避免被当成已评审内容
（这条仍待前端落地，接口已把 `source_file` / `custom: true` 与留痕都备好了）。

---

## 七、分片计划与验收标准

| 片 | 内容 | 验收 |
| --- | --- | --- |
| **1** | 自定义枚举选项 + 自定义角色权重模板 | 新增选项后 `/api/schema` 与表单下拉出现；新增模板后排序页可选且 CR<0.1 校验生效；清表后行为与内建一致 |
| **2** | 自定义字段（`custom` 保留字段 + 摊平 + schema/表单/Excel 动态列） | 新字段出现在表单与 Excel 导出列；规则可引用；`known_field_names` 含该字段；内建产物零 diff |
| **3** | 自定义规则（校验同源 + 规则合并 + 编辑器 + 导回 YAML） | 非法规则被拒并给中文原因；合法规则参与评估与报告溯源；导出片段可直接提交进 `rules/` 并通过 CI |
| **4** | 权限与审计完善、生产开关、文档 | prod 下写接口 403；审计字段齐全；`docs/` 更新完毕 |

**各片状态**：片 1、片 3、片 2、片 4 均已落地，**回灌路径也已落地**，
落地记录与验证证据见第九节。

每片结束都要：跑 `check_rules` + `pytest` + 前端测试、重跑生成链确认零 diff
（**外加 `export_frontend_fixtures.py --grid-step 10`**——CI 有一条"离线快照与当前规则一致"
的检查，改了规则不重导会直接红）、更新 `docs/open-items.md`，并推到独立分支。

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
| 开放枚举标记 | `app/models/params.py` | `risk_features` 加 `extensible=True`；`irregularity_items` 保持封闭；**只有打了标的字段**才允许追加候选值 |
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

### 片 3：自定义规则（2026-10，**先于片 2 做**）

**为什么调换顺序**：片 2 的自定义字段单独落地时"没有规则能给它打分"，价值要等片 3 才兑现；
反过来，自定义规则只用内建字段就已经**立刻有用**（例如"本次比选自定：得房率低于 0.75 扣分"），
而且它不需要动 `params.py`，也就不牵动生成链。所以先做规则、后做字段。

**校验同源落到了实处**：把"一条规则的结构与表达式校验"从 `scripts/check_rules.py`
**搬进引擎**（新模块 `app/engine/rule_check.py`），双方共用一份：

- 跑 `check_rules` 与在界面上新增规则，用的是同一个 `check_rule_problems`，
  报错码、中文说明与"怎么改"完全一致；
- `scripts/check_rules.py` 从此只负责**文件级**的事：Tab/全角冒号文本扫描、YAML 解析与行号、
  跨文件 ID 重复、`weights.yaml`、以及渲染成 `文件名:行号 规则ID — 说明 — 怎么改`。
  重构后 `check_rules` 实测与此前完全一致（0 错误 0 警告，53 个校验器测试全过）。

**新增接口**（写接口仅 dev，读接口放开）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/custom/rules` | 自定义规则清单；每条带 `is_valid` 与 `problems`（存量规则校验不过时给出原因） |
| POST | `/api/custom/rules` | 新增规则，请求体就是规则本身（字段同 `rules/_template.yaml`） |
| DELETE | `/api/custom/rules/{id}` | 删除规则 |

**`X-` 是运行期自定义规则的保留前缀**（如 `X-01`）。文件里的规则用 C/Q/S/K/G；
给覆盖层一个独立前缀，才能在任何列表、报告与截图里一眼分出"进了 git 的"和"界面加的"。
`RULE_ID_PATTERN`、`BAD_RULE_ID` 的提示语与 `rules-guide` 都写明这条约定。

**合并规则**：`app/custom/rules.py::ruleset_with_custom` 把自定义规则接在内建规则**后面**，
`/api/projects/{id}/evaluate` 与 `GET /api/rules` 都走它；**没有自定义规则时返回的就是内建集合对象本身**，
所以清空覆盖层后行为与纯内建完全一致。ID 冲突由 `RuleSet.__post_init__` 再兜一层。

**比文件更严的一条**：`source` 必填、且不允许挂 TODO。自定义规则没有 CI 把关，
出处是唯一能让人复核的依据——专业组"没有条文依据就别加"的约定，在这里变成保存时的硬闸门。

**验证**（`ruff` 干净、`pytest` **508 通过**、`check_rules` 0 错误 0 警告）：

- 新增的评分指标真的参与评估：得房率 0.8 落在控制点 `[0.70, 0]`~`[0.85, 100]` 之间，
  分数按分段折线算出，并带上出处供报告溯源；
- 新增的硬约束真的会拦：层高 3.1 m 对 `floor_height >= 3.2` 判不通过；
- `GET /api/rules` 里自定义规则的 `source_file` 是"（界面自定义）"，内建规则一条不少且仍排在前面；
- 非法内容一律 422 + 与 `check_rules` 同款中文说明：未知字段、表达式拼错（带拼写候选）、
  控制点不递增、ID 格式错、ID 与内建冲突、ID 重复、缺出处、出处挂 TODO；
- 删除后回到内建规则集；`APP_ENV=prod` 时写接口 403、读接口正常。

**片 3 未完成**：①"导出自定义规则为 `rules/*.yaml` 片段"（第一节第二条决策里的回灌路径）；
②前端设置页。

### 片 2：自定义字段（2026-10）

**做法**：方案层加一个保留字段 ``SchemeParams.custom``（``dict``，schema 里带 ``hidden: true``，
前端应跳过容器本身），**不动态造 Pydantic 模型**——动态模型会牵动校验、序列化、OpenAPI 与
前端类型生成，代价远大于收益。这里只维护**注册表**（``custom_fields`` 表）：
一条记录描述一个字段的元信息。

| 部分 | 位置 | 要点 |
| --- | --- | --- |
| 保留字段 | `app/models/params.py` | `custom: dict[str, Any]`，`hidden=True`；`meta.py` 把 `hidden` 透出给前端 |
| 注册表 | `app/custom/models.py` | `custom_fields`：key / label / kind / unit / group / options / description |
| 注册表逻辑 | `app/custom/fields.py` | 校验、CRUD、并入 schema、`known_names()` |
| 命名空间摊平 | `app/engine/rules.build_namespace` | `custom` 的键摊平到顶层，规则里直接写 `bearing_wall_ratio` |
| 字段名白名单 | `app/engine/rules.known_field_names(extra=…)` | 校验自定义规则时把自定义字段并进来 |
| 接口 | `app/api/custom.py` | `GET/POST/DELETE /api/custom/fields`（写接口仅 dev） |
| schema 合并 | `app/schemas/merged.py` | 内建基线 + 覆盖层，**`/api/schema` 与 Excel 三条路径共用同一份** |

**只能追加**：字段名不得与内建字段、派生量或保留字段 `custom` 重名——否则引用它的规则
会突然算到另一个值。`build_namespace` 里还有第二道保险：`setdefault` 合并，内建字段永远优先。

**一条硬约束（必须记住）**：**内建规则（`rules/*.yaml`）不能引用自定义字段**。
`scripts/check_rules.py` 是纯文件校验、看不到运行期覆盖层，所以自定义字段只进
**自定义规则**的"已知字段"清单。定稿后应走"导出成内建字段"的路径（第一节第二条决策）。

**Excel 一致性**：`app/schemas/merged.py` 同时服务 `GET /api/schema` 与
`write_template` / `write_export` / `parse_workbook`，所以"界面上能填的字段"
与"Excel 里能填的列"永远一致：

- 传 `session` 时含覆盖层（HTTP 导入接口、`export_schemes.py`、`import_schemes.py` 已接）；
- **不传 `session` 时只有内建基线**——`scripts/make_template.py` 与前端 mock 数据走这条路，
  保证提交进仓库的构建产物永远只含内建字段，CI 的 `git diff --exit-code` 才有意义；
- 自定义字段的值在 Excel 里读写 `params["custom"]`，不落顶层（顶层会被模型丢掉）；
- 比例识别改为**先看覆盖层的 `kind: ratio` / 0–1 约束**，内建那份硬编码名字清单保留兜底
  （否则自定义比例字段会被当普通数字解析）。

**顺带修掉一个真 bug**：`app/schemas/meta.py::_simplify_type` 处理 `dict[str, Any]` 时，
Pydantic 生成的是 `"additionalProperties": true`（**布尔值**），旧代码当字典用 →
`'bool' object has no attribute 'get'` → 一上来就是 **34 个失败 + 12 个错误**。
该模块此前从未见过字典型字段，所以一直没暴露。

**验证**（`ruff` 干净、`pytest` **515 通过**、`check_rules` 0 错误 0 警告、前端 `tsc` 通过）：

- 新增字段出现在 `GET /api/schema/scheme` 的 `fields` 里，带 `"custom": true` 与
  `constraints: {minimum: 0, maximum: 1}`，内建字段一条不少且仍排在前面；删除后复原；
- 字段名与内建字段 / 派生量 / 保留字段重名，或类型、分组、候选值不合法，一律 422 + 中文建议；
- `build_namespace` 把 `custom` 摊平到顶层；**内建字段优先**（同名的自定义键顶不掉它）；
  没填的自定义字段按"缺数据"处理（判不了，而不是判不通过）；
- 自定义规则能引用自定义字段并真的参与评估（`X-07` 按"承重墙占比"打分）；
- 同一份表达式：不给覆盖层字段名 → `BAD_EXPRESSION`；给了 → 通过。这条界线被测试钉住；
- **Excel 往返**：模板里出现自定义字段的中文列名；导出→解析后值落在 `params["custom"]`；
  不传 `session` 时模板里没有该列。

**片 2 未完成**：前端设置页（片 1/2/3 共用）；"导出自定义内容为 YAML / 代码"的回灌路径。

**下一片（片 4）**：权限与审计——接入真实操作者身份（现在取 `X-Operator` 头），
生产开关与留痕补齐。

---

### 片 4：权限与审计（2026-10）

| 部分 | 位置 | 要点 |
| --- | --- | --- |
| 审计表 | `app/custom/models.py` | `custom_audit`：`at` / `operator` / `action` / `kind` / `target` / `summary` / `detail`，**只追加** |
| 审计服务 | `app/custom/audit.py`（新） | `record()` 只 `add`+`flush`、**不 commit**（与业务写操作同事务）；`list_entries()` 新的在前、上限 500；`normalize_operator()` 归一化 |
| 埋点 | 四个服务模块 | 选项 / 模板 / 规则 / 字段的**新增与删除**都留痕；删除前先把原值写进 `detail` |
| 接口 | `app/api/custom.py` | `GET /api/custom/audit`（读接口，生产也可用）；四个删除接口补上操作者 |
| 生产开关 | 既有 `_require_dev()` | 写接口 prod 403；读接口与留痕照常 |

**一个被测试逼出来的真实限制**：HTTP 头按规范只能是 ASCII——写测试时直接传
`X-Operator: 张三`，被 httpx 的 `UnicodeEncodeError` 拦下。于是 `normalize_operator`
支持**百分号编码**：中文名由客户端 `encodeURIComponent` 后传，后端解回 UTF-8；
纯 ASCII 标识（工号）原样通过。**推荐用「工号」这类 ASCII 标识做操作者**。

**验证**（`ruff` 干净、`check_rules` 0 错误 0 警告、`pytest` 全绿）：

- 四类内容各建一条、再各删一条 → **八条留痕**，新的在前，动作与类别齐全，类别中文名可直接展示；
- 删除的留痕里能看到**原值**（例如 `risk_features=临近地铁振动`）——删完就说不清是留痕的大忌；
- 操作者归一化：百分号编码的中文解回、ASCII 工号原样、控制字符清掉、空白折叠、超长截断、空值 → `anonymous`；
- 生产环境写接口 **403 且不产生新留痕**，而留痕读接口照常 200；
- `limit` 有上限（1~500）；`record()` 对未知动作 / 类别直接 `ValueError`
  ——宁可当场炸，也不要写进一条"看起来像留痕、其实没人认识"的记录。

**片 4 未完成**：接入真实登录身份（当前是 `X-Operator` 占位）；前端把留痕展示出来。

### 回灌：把覆盖层导出成可落库的片段（2026-10）

这是第一节第二条决策的落点——**覆盖层是草稿台，最终权威是 YAML + git**。

**接口**：`GET /api/custom/export`（**读**接口，生产也可用——它不改变任何内容）。

**导出四段片段 + 落地清单**：

| 片段 | 目标位置 |
| --- | --- |
| `rules_yaml` | `rules/*.yaml`（评分指标按 `dimension` 决定文件与前缀；硬约束按主题选文件） |
| `fields_python` | `app/models/params.py` 的 `SchemeParams` 类体 |
| `options_python` | `params.py` 里对应字段的候选列表（`RISK_FEATURE_OPTIONS` 等） |
| `weights_yaml` | `rules/weights.yaml` 的 `roles:` 之下 |

另外给出 `checklist`（七步落地流程，含"入库后回界面删掉草稿"）、`notes`（全局注意事项）
与一份可直接贴给人看的 `markdown`。

**三处"不替使用者决定"的地方**（写在片段注释里，而不是悄悄改）：

1. **保留前缀 `X-` 必须换掉**：`X-` 只属于运行期覆盖层。导出会按 `dimension` 给出
   **建议编号**（评分指标），或列出候选（硬约束按主题选 C / S / K），并写明要改成什么；
2. **角色键要改成英文标识并同步 `ROLE_KEYS`**：`rules/weights.yaml` 的角色键是代码里用的
   标识，中文模板名只能当 `label`；
3. **`compliance` 是独立硬门槛、不计入评分**：自定义模板只存四个评分维度，片段补一个
   内建常见参考值（0.20）并注明需专业组确认。

**强制点落在文件校验上**：`scripts/check_rules.py` 对文件里出现的 `X-` 编号报
`RUNTIME_PREFIX_IN_FILE`，并提示去换维度前缀。这条**只能放在文件层**——共享校验器
（`app/engine/rule_check.py`）还要放行运行期的 `X-` 规则；这正是"check_rules 与引擎同源"
与"回灌必须换号"两条约束的交汇处。

**验证**（`ruff` 干净、`check_rules` 0 错误 0 警告、`pytest` 全绿）：

- 空覆盖层导出的是占位注释，清单与注意事项照常给出；
- 四段片段**语法可用**：YAML 过 `yaml.safe_load`，Python 片段去掉注释行与类体缩进后过 `ast.parse`；
- 规则片段带建议编号（S 系列现有到 S-14 → 建议 S-15）；
- 权重片段补齐 `compliance`，且**不改**使用者给的四个维度值，并写明要同步 `ROLE_KEYS`；
- 文件里出现 `X-01` → `RUNTIME_PREFIX_IN_FILE`；换成 `S-99` 后该错误消失；
- 仓库现有规则文件**一条都没有**用 `X-`（这条不变式由 CI 的 `check_rules` 兜住）；
- 导出在生产环境照常 200，写接口仍 403。

> 写测试时抓到一个真 bug：候选列表的常量名不能靠 `field.upper() + "_OPTIONS"` 拼——
> `risk_features` 会拼成 `RISK_FEATURES_OPTIONS`，而真实常量叫 `RISK_FEATURE_OPTIONS`。
> 现在用显式映射，并由测试断言片段里出现的是**真实常量名**。

---

## 十、推送计划（与 PR 的关系）

按要求，本功能**不并进土木侧那条 PR**，而是**单独分支 + 单独 PR**：

| 项 | 约定 |
| --- | --- |
| 分支 | **`feat/custom-add`**（已推送） |
| base | **`main`**：土木侧 PR（#8）已合并，所以 base 就是 main；本分支已把 main 合进来，diff 只含本功能 |
| **标题** | **必须写明本次推送的具体内容**：现为「Add the runtime custom-add overlay: enum options, weight templates, custom rules and custom fields」 |
| PR | **#12**（OPEN，独立于土木侧规则的 #10） |
| **不要动** | **其它 PR 的标题**（#8 已合并、#10 是土木侧规则，都与本功能无关） |

推送前还要按老规矩跑一遍：`ruff`、`check_rules`、后端全量 `pytest`、前端 `tsc` + `npm test`，
并核对生成链幂等（`export_schema` / `gen_field_table` / `gen:types` / `sync:mock` /
`export_frontend_fixtures --grid-step 10` 的 `--check` 全过）。
