# T3：规则引擎与规则校验

分支 `feat/rules-engine`（基于 `docs/rules-guide`，因为要在 T9 的 `check_rules.py` 和
规则编写指南上继续做；`main` 还停在 T1 骨架）。

---

## 做了什么

### 1. 确定性引擎（`backend/app/engine/`）

**完全不调用大模型**，`evaluate` 是纯函数：不读库、不依赖时间或随机数，同样输入必然同样输出。

| 文件 | 职责 |
| --- | --- |
| `metrics.py` | 派生量集中定义（7 个），每个带中文名、单位、公式字符串、依赖字段 |
| `scoring.py` | 分段线性求分 + 公式字符串渲染 |
| `rules.py` | `RuleDef` 规则定义、表达式求值与静态检查、`evaluate` 判定与维度聚合 |

**派生量**（T3 要求的四个 + 沿用 T9 已发布的三个）：

| 字段名 | 中文名 | 公式 |
| --- | --- | --- |
| `far` | 容积率 | `gfa / site_area` |
| `density` | 建筑密度 | `footprint / site_area` |
| `shape_coef` | 体形系数 | `envelope_area / volume` |
| `height` | 建筑总高 | `floors * floor_height` |
| `units_per_building` | 单栋户数 | `units / buildings` |
| `units_per_floor` | 每层户数 | `units / (floors * buildings)` |
| `floor_efficiency` | 楼层效率 | `footprint * floors / gfa` |

`formula` 字符串会原样写进评估结果，报告里能直接看到"这个数是怎么算出来的"。
`compute` 与 `formula` 由测试用表达式求值交叉验证，防止改了公式忘了改注释。

**表达式**用 `simpleeval` 求值（**不用 `eval`**），只放开 `min` / `max` / `abs` / `round` / `len`
五个函数。加载时解析 AST 做静态检查，节点走白名单（属性访问、下标、推导式、lambda 一律拒绝），
名字必须是已知字段、派生量或允许的函数，拼错用 `difflib` 给候选。

指南 §3.1 向非程序员承诺过的 `contains` 运算符不是 Python 语法，解析前改写成 `in`
（`risk_features contains '深基坑'` → `('深基坑') in (risk_features)`），对用户完全透明。

**缺数据不抛异常**：hard 记 `insufficient_data`，metric 不计分，并记下缺哪些**原始**字段
（引用 `shape_coef` 但 `volume` 没填时，报出来的是 `volume`——那才是规则作者能去补的东西）。

**维度得分**＝该维度内有分数的指标按 `weight_in_dimension` 加权平均；
**`coverage`**＝有分数的权重 / 适用指标总权重。`not_applicable` 的指标不计入分母。

### 2. 数据模型扩展（`backend/app/models/eval.py`）

T2 的模型表达不了引擎需要的两种状态，做了向后兼容的扩展：

- `ComplianceStatus` 增加 `not_applicable`（`when` 不成立）；新增 `MetricStatus`；
- `MetricResult.score` 改为可空（数据不足 / 不适用时为 `null`），并加 `missing_fields`、
  `weight_in_dimension`、`rule_id`、`name`；
- `ComplianceItem` 加 `severity`、`formula`、`missing_fields`；
- 新增 `DimensionCoverage`；`EvalResult` 加 `scheme_name` 与 `has_blocking_failure`。

`data/schema/eval.schema.json` 已重新导出。

### 3. 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/projects/{id}/evaluate` | 跑规则 + 指标 + 评分，结果写入 `eval_results` |
| GET | `/api/projects/{id}/evaluate` | 读上一次结果，不重算 |
| GET | `/api/rules` | 规则定义 + 派生量定义 + 出处仍是 TODO 的规则 ID |
| POST | `/api/rules/reload` | 热重载，**仅 `APP_ENV=dev`**，生产返回 403 |

- **evaluate 幂等**：同一项目重复评估先删旧结果再写，不会越评越多行。
- 默认只评正式方案，`?include_whatif=true` 才带上 what-if 副本。
- 规则在启动时加载一次，**加载失败不阻断启动**：规则由非程序员维护，写错一条不该让
  整个演示起不来；真正的闸门是 CI 里的 `check_rules`，而 `/api/rules` 会把失败原因原样返回。
- 新增 `APP_ENV` 配置项（已写进 `.env.example`）。

### 4. `scripts/check_rules.py` 重写

报错格式按 T3 规格统一：

```
错误  rules/quality.yaml:13  K-01 — 错在哪 — 怎么改：具体动作
└─┬─┘ └────────┬──────────┘ └─┬─┘
严重程度   文件名:行号        规则编号
```

- **行号是真实行号**，来自 PyYAML 的 node mark，沿 Pydantic 错误路径下钻，
  能精确到出问题的那个控制点（`scoring.points.1.1`）。T9 版打印的是"第几条规则"，
  一个文件放多条规则时几乎没法定位。
- **结构校验复用引擎的 `RuleDef`**，保证"check_rules 说通过"和"引擎能加载"永远是一回事。
- PyYAML 的英文 `problem` 逐条翻成中文（"这一行的缩进和上一行对不齐，YAML 读不懂它属于谁"）。
- 有错误退出码 1，只有警告退出码 0（`source` 还挂着 TODO 属于警告）。

### 5. 种子规则

`rules/` 下五个文件共 12 条格式示例（4 hard + 8 metric），覆盖四个维度、`when` 条件、
派生量、`contains`、`severity`，以及越大越好 / 越小越好 / 适中最好三种分段折线。

**阈值和分段点都是随手取的**：`name` 一律加「【示例】」前缀，`source` 一律写
`TODO(专业组)：示例数值，正式条文号待补`，**没有任何真实规范条文号**（详见下面「留给专业组」）。

`rules/_template.yaml` 是带详细中文注释的空白模板，以下划线开头，引擎与 `check_rules` 都跳过。

---

## 与 T3 规格的偏离

规格说的 `check_rules.py`、派生量、规则 ID 格式，T9 都已经在 `docs/rules-guide.md` 里
对非程序员做过承诺，两边不一致。已确认按 **T3 为准**，把 T9 侧一并改过来：

| 冲突点 | 处理 |
| --- | --- |
| 派生量 `shape_coefficient` / `total_height` | 改名为 T3 的 `shape_coef` / `height`，并补上缺失的 `far` / `density`；指南、字段表、2 个 fixture、1 项测试断言同步 |
| 规则 ID `C-SHAPE` / `C-STEEL-COAT` 等 8 个不合 `^[CQSKG]-\d{2}$` | 强制正则，fixture 与指南示例改号（`C-10` / `C-11` / `C-90`…）；quality 维度的示例指标前缀从 `K-` 改为 `Q-`，与文件对应 |
| 指南承诺的 `contains` 运算符不是 Python 语法 | 加载时语法糖改写成 `in`，指南与 fixture 不动 |
| `check_rules` 报错格式与错误码 | 按 T3 格式重写，不再打印英文错误码；`test_guide_examples` 的 6 个断言改为按中文说明匹配，按错误码断言的用例移到 `test_check_rules.py`（直接读 `Issue.code`） |

另外两处是实现过程中发现的问题，一并改了（都在本任务范围内）：

1. **移除 T9 的 `UNALIGNED` 文本启发式**。它靠"同一缩进级别出现重复 key"判断错位，
   而一个文件放多条规则时每条都有自己的 `id` / `name`——写完五个种子规则文件后
   一跑就刷出 40 多条误报。缩进不齐改由 PyYAML 自己报（行号更准），
   再把它的英文 problem 翻成中文。新增的 `DUPLICATE_KEY` 按列表项分块，只在同一条规则内比较。
2. **`gen_field_table.py` 的派生量清单改从 `metrics.py` import**。原先两处各写一份，
   改了一边忘了另一边就会悄悄漂移。

顺手修掉指南里示例文件的相对链接层级（`../../backend` → `../backend`，原先指到了仓库外）。

**新增依赖**：`simpleeval`（AGENTS.md 技术栈内的选型）、`pyyaml`（原本只是传递依赖，
规则加载与 `check_rules` 直接用它，显式声明）。都在技术栈范围内。

---

## 如何运行

```bash
make dev-backend
```

然后（`make seed` 先灌一套虚构样例数据，项目 id 假设是 1）：

```bash
curl -X POST http://localhost:8000/api/projects/1/evaluate
```

看当前加载了哪些规则与派生量：

```bash
curl http://localhost:8000/api/rules
```

改完 `rules/*.yaml` 不用重启，热重载一次（仅开发环境）：

```bash
curl -X POST http://localhost:8000/api/rules/reload
```

校验规则文件：

```bash
uv run --project backend python scripts/check_rules.py
```

---

## 如何测试

```bash
make test
```

```
281 passed, 2 warnings in 8.60s
```

```bash
make lint
```

```
All checks passed!
```

```bash
make docs-check
```

```
check_rules 退出码 0（5 个文件，0 个错误，12 个警告——全是 source 的 TODO）
gen_field_table --check 退出码 0
gen_metric_charts 3 张图已写出
```

本次新增 5 个测试文件，共 181 项：

| 文件 | 覆盖 |
| --- | --- |
| `test_scoring.py` | 端点、点间插值、两端外截断、先升后降；以及"用错折线段"这类具体实现错误（0.875 应得 85 分而不是 62.5） |
| `test_metrics.py` | 每个派生量的 `compute` 与 `formula` 交叉验证、缺数据、分母为 0、布尔值不当数字 |
| `test_rules_engine.py` | `RuleDef` 字段校验、`contains` 改写、表达式静态检查、14 个错误 YAML、`when` 三态、缺数据、维度加权与覆盖率、确定性 |
| `test_check_rules.py` | 报错格式与**真实行号**逐条断言、拼写建议、退出码 |
| `test_evaluate_endpoint.py` | 幂等、落库、what-if 过滤、空方案、`reload` 的环境门控 |

错误 YAML 放在 `backend/tests/fixtures/rules_bad/`，引擎侧与脚本侧共用同一批。

### check_rules 对每种错误的输出

```
━━ tab_indent.yaml
  错误  tab_indent.yaml:4  （未知 ID） — 这一行用了 Tab 缩进，YAML 不接受 Tab
        — 怎么改：把行首的 Tab 全部替换成空格；同一层级统一缩 2 个空格
  （第 5、6 行同样各报一条）

━━ chinese_colon.yaml
  错误  chinese_colon.yaml:2  （未知 ID） — 这一行用了中文全角冒号「：」
        — 怎么改：把它替换成英文半角冒号「:」。半角冒号比汉字窄，全角冒号和汉字一样宽
  错误  chinese_colon.yaml:2  （未知 ID） — 第 1 项不是一条规则
        — 怎么改：每条规则写成 `- id: C-01` 开头的对象，下面缩进 2 空格写其它字段
  （第 3–6 行各报一条全角冒号）

━━ missing_required.yaml
  错误  missing_required.yaml:2  （未知 ID） — 缺少必填字段「id」
        — 怎么改：补一行 `id: C-01`（前缀字母 C/Q/S/K/G + 短横线 + 两位数字，全局唯一）
  错误  missing_required.yaml:2  （未知 ID） — 缺少必填字段「type」
        — 怎么改：补一行 `type: hard`（硬约束）或 `type: metric`（评分指标）

━━ bad_rule_id.yaml
  错误  bad_rule_id.yaml:2  C-SHAPE — 规则 ID「C-SHAPE」格式不对
        — 怎么改：必须是一个大写字母 + 短横线 + 两位数字，例如 C-03、Q-01、K-12。
          前缀按文件选：compliance 用 C，quality 用 Q，structure 用 S，construction 用 K，green 用 G

━━ duplicate_id.yaml
  错误  duplicate_id.yaml:8  C-01 — 规则 ID 重复：duplicate_id.yaml:2 已经用过这个 ID
        — 怎么改：规则 ID 必须全局唯一，给这一条换一个没用过的编号

━━ unknown_field.yaml
  错误  unknown_field.yaml:6  C-01 — 出现了无法识别的字段「serverity」
        — 怎么改：是不是想写 `severity`？多余的字段会被当成错误而不是忽略，
          免得一条规则看起来生效其实没生效

━━ points_not_monotonic.yaml
  错误  points_not_monotonic.yaml:10  K-01 — scoring.points 的指标值（每项第一个数）必须严格递增，
        当前是 [0.95, 0.8, 0.5]；「越小越好」的指标也要按指标值从小到大排，靠分数递减来表达
        — 怎么改：把控制点按第一个数字从小到大重排；「越小越好」靠分数递减表达，
          「适中最好」靠分数先升后降表达

━━ points_score_out_of_range.yaml
  错误  points_score_out_of_range.yaml:11  K-01 — 控制点「scoring.points.1.1」的分数 120 超出了 0–100
        — 怎么改：每个控制点的第二个数字是分数，必须在 0–100 之间；
          比例类指标别把 0.82 写成 82 放到分数位上

━━ expression_syntax.yaml
  错误  expression_syntax.yaml:5  C-01 — check 表达式写法不合语法：invalid syntax
        — 怎么改：检查括号是否成对、引号是否成对、比较符是否写全（要写 >= 不能写 =>）；
          判断相等要写两个等号 ==

━━ unknown_field_in_expression.yaml
  错误  unknown_field_in_expression.yaml:5  C-01 — check 表达式里的 `floor_hieght` 不是已知字段或派生量
        — 怎么改：是不是想写 `floor_height`、`std_floor_repeat`、`floor_efficiency`？
          完整字段表见 docs/fields.generated.md

━━ bad_dimension.yaml
  错误  bad_dimension.yaml:5  K-01 — dimension 只能是 quality / structure / construction / green 之一，
        当前写的是 'cost' — 怎么改：是不是想写 `construction`？从这四个里选一个；
          确实需要新维度请先找队长改 app/models/eval.py，不要直接在 YAML 里造新值

━━ type_field_mismatch.yaml
  错误  type_field_mismatch.yaml:2  C-01 — hard 规则不应该有 dimension、value、scoring 字段
        （那是 metric 规则的）；如果这条本来想写成评分指标，请把 type 改成 metric
        — 怎么改：对照 rules/_template.yaml：hard 用 check/message，metric 用 dimension/value/scoring

━━ disallowed_function.yaml
  错误  disallowed_function.yaml:6  K-01 — value 表达式调用了不允许的函数 `sum`
        — 怎么改：需要更复杂的计算请提给开发组加成派生量。只能调用 abs、len、max、min、round

━━ top_not_list.yaml
  错误  top_not_list.yaml:2  （未知 ID） — 文件顶层必须是一个规则列表
        — 怎么改：每条规则以顶头的 `- id: ...` 开头，字段缩进 2 个空格

━━ rules/compliance.yaml（种子规则，只有警告，退出码 0）
  警告  rules/compliance.yaml:14  C-01 — source 里还挂着 TODO，这条规则的出处尚未落实
        — 怎么改：核对规范原文后把 source 换成「规范编号 第 X 条」，或写成「经验规则（XX组）：理由」。
          示例规则请一并去掉 name 的「【示例】」前缀
```

---

## 留给专业组

`rules/` 下 12 条规则的 `source` 全是 `TODO(专业组)`，阈值与分段点都是随手取的格式示例，
`name` 带「【示例】」前缀。**本 PR 没有编造任何规范条文号、阈值或行业数据。**
需要专业组逐条落实的：

| 规则 ID | 名称 | 需要确认 |
| --- | --- | --- |
| `C-01` | 住宅层高下限 | 条文号 + 阈值（示例用 3.0 m） |
| `C-02` | 容积率不超地块上限 | 是否需要这条（`far_max` 由项目录入）；条文依据 |
| `C-03` | 建筑总高不超限高 | 条文号；`severity` 该用 error 还是 warning（示例用 warning） |
| `Q-01` | 主要房间南向比例 | 峰值位置与两端分段点（示例 0.20 / 0.55 / 0.90） |
| `Q-02` | 得房率 | 分段点（示例 0.65 / 0.78 / 0.88） |
| `Q-03` | 单栋户数 | 分段点与 `when` 的高层界限（示例 `floors >= 7`） |
| `S-01` | 风险特征数量 | 是否按数量计分合理；分段点（示例 0 / 2 / 5） |
| `S-02` | 钢结构人工复核 | 该检查哪个风险特征（示例借用了 `超限构件`） |
| `K-01` | 标准层重复率 | 分段点（示例 0.50 / 0.80 / 0.95） |
| `K-02` | 预制构件种类数 | 分段点（示例 8 / 20 / 40） |
| `G-01` | 体形系数 | 分段点，且需按气候区区分（示例未区分） |
| `G-02` | 预估装配率 | 分段点（示例 0.20 / 0.50 / 0.80） |

另外需要专业组定：**各维度内指标的相对权重**（`weight_in_dimension`）。
示例里只是随手给了 1 / 2 / 3。

---

## 遗留问题

**本 PR 范围内刻意没做的**

1. **字典类字段无法在表达式里取下标**。`window_wall_ratio`（各朝向窗墙比）和 `unit_mix`
   （户型配比）是字典，但表达式禁止 `Subscript`（安全白名单）。所以现在写不出
   "南向窗墙比 ≤ 0.4" 这种规则。两个可选方向：把常用朝向做成派生量
   （`window_wall_ratio_south` 等），或在白名单里开放受限的常量下标。
   **需要专业组先说清要不要按朝向分别定规则**，再决定怎么做。
2. **`topsis` 字段仍为 `null`**。排序是 T4 的 `/api/projects/{id}/rank`，本 PR 只产出维度得分。
3. **`rules/weights.yaml` 没建**。AHP 角色权重模板是 T4 的事；引擎与 `check_rules`
   已经会跳过这个文件名。
4. **`severity=error` 的不通过项目前只标记不剔除**。`EvalResult.has_blocking_failure`
   已经算好，但"默认不参与排名"要在 T4 的 `/rank` 里落实。
5. **缺数据判定是保守的**：按"表达式**引用**到的字段有没有值"判，不看求值短路。
   `floors > 10 and elevators_per_unit >= 2` 在 `floors == 5` 时其实不需要电梯数，
   但仍判为数据不足。选这个语义是为了结果可解释且与求值顺序无关，
   代价是偶尔会把本可判定的规则记成 `insufficient_data`。如果实际用起来嫌吵，
   可以改成"先试求值，抛 TypeError 才算数据不足"。

**发现但不属于本任务的**

6. **`scripts/` 目录没进 lint 范围**。`make lint` 和 CI 都只跑 `cd backend && ruff check .`，
   `scripts/` 下的 8 个脚本从来没被检查过。用项目配置扫一遍有 3 处告警
   （`export_schemes.py` 与 `import_schemes.py` 的 import 排序，以及 `import_schemes.py`
   里一个未使用的 `get_settings`）。本 PR 只保证自己改的两个脚本干净，没动别人的文件，
   也没扩大 lint 范围。建议单独开一个小 PR 把 `scripts/` 纳进来。
7. **`rules/.gitkeep` 和 `scripts/.gitkeep` 可以删了**，两个目录早就有真文件。没动，避免噪音。
8. **指南 §4.3 的维度说明里 `green` 写了"得房率"**，但得房率在示例里归到了 `quality`。
   等专业组定稿指标归属时一并校准。

🤖 Generated with [Claude Code](https://claude.com/claude-code)
