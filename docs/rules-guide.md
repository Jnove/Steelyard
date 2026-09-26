# 规则编写指南（给土木与建筑专业的同学）

> 这份文档面向**没写过代码、但懂建筑专业的同学**。你只需要会写字和处理简单表格，
> 就能写出筑衡引擎能读懂的规则。读完这份指南，你应当能独立写出符合
> `check_rules` 校验的硬约束与评分指标，并通过 GitHub 网页提交 Pull Request。

整个文档尽量口语化；遇到术语当场解释；所有数值都标注「示例数值」，
**不引用任何真实规范条文号**——这些由对应专业组填写。

---

## 目录

1. [五分钟看懂 YAML](#1-五分钟看懂-yaml)
2. [字段对照表（自动生成，不要手改）](#2-字段对照表自动生成不要手改)
3. [硬约束（hard）怎么写](#3-硬约束hard怎么写)
4. [评分指标（metric）怎么写](#4-评分指标metric怎么写)
5. [source 字段怎么填](#5-source-字段怎么填)
6. [在 GitHub 网页上修改规则并提交 PR](#6-在-github-网页上修改规则并提交-pr)
7. [怎么看 check_rules 报错](#7-怎么看-check_rules-报错)
8. [一页速查卡](#8-一页速查卡)

---

## 1. 五分钟看懂 YAML

筑衡的规则文件都是 YAML 格式（文件后缀 `.yaml` 或 `.yml`）。YAML 的设计目标就是
"人能直接读"，所以你只需要记住下面几条规则。

### 1.1 缩进：用 2 个空格，不要用 Tab

YAML 用**缩进**表示层级关系，缩进多的属于缩进少的「下面」。缩进必须用空格键，
**严禁用 Tab 键**——混用空格和 Tab 是 90% 的报错来源。

下面这段是对的（每个 `- ` 前 0 空格，字段前 2 空格）：

```yaml
- id: C-03
  name: 住宅层高下限
  type: hard
  check: "floor_height >= 3.0"
```

下面这段是错的（用了 Tab 缩进）：

```yaml
- id: C-03
  name: 住宅层高下限
⇥type: hard
⇥check: "floor_height >= 3.0"
```

> 「⇥」表示一个 Tab 字符。VS Code 默认按一下 Tab 会插入 4 个空格，那样没事；
> 但**如果你从网上复制粘贴、或者从 Excel 粘贴到文本编辑器**，很容易带进真 Tab。
> 检查办法：在编辑器右下角看到「Spaces: 4」或类似字样才对。

### 1.2 冒号：必须是英文半角冒号 `:`

YAML 用**冒号**分隔"字段名"和"字段值"，且必须是英文半角冒号（`:`）。
中文里那种「：」比英文「:」宽一格，**YAML 不认**。

```yaml
# ✅ 正确：英文冒号
id: C-03

# ❌ 错误：中文冒号
id：C-03
```

编辑器里看到全角「：」就立刻改成半角「:」。本仓库的 `check_rules` 会自动报这一类错。

### 1.3 列表：用 `- ` 开头

同一层的多个项目用 `- ` 起头，且 `- ` 后必须跟一个空格：

```yaml
- id: K-01
  name: 标准层重复率
- id: K-02
  name: 单栋户数
```

### 1.4 引号：什么时候该加引号

**最简原则**：值里没有特殊字符（`#`、冒号、引号、换行）就不加引号；
有就加双引号 `"..."`。

```yaml
name: 住宅层高下限         # ✅ 中文不强制加引号
check: "floor_height >= 3.0"  # ✅ 含 >= 和空格，加双引号更安全
message: '层高 {floor_height} m 低于 3.0 m'  # ✅ 也可用单引号
```

### 1.5 最常见的三种错误速查

| 错误样子 | 错在哪里 | 怎么改 |
| --- | --- | --- |
| `⇥check: "..."` | 用了 Tab 缩进 | 全选当前层，按一次 Tab → 改成 2 个空格 |
| `id：C-03` | 用了中文全角冒号 | 把 `：` 替换成英文 `:` |
| 子键缩进与兄弟节点差 1 个空格 | 缩进不齐（典型表现：第二条规则的子键比第一条多缩了一格） | 让所有同辈字段对齐到同一列（建议 2 或 4 空格） |

每个错误 `check_rules` 都会单独报一行，并指出**行号**，照着行号找就行。

---

## 2. 字段对照表（自动生成，不要手改）

写规则时经常会问"这个字段叫什么？单位是 m 还是 m²？"——下面的表把
项目层、方案层与派生量全部列出来。**它由脚本从 JSON Schema 自动渲染**，
改模型后请重新跑：

```bash
uv run --project backend python scripts/gen_field_table.py
```

CI 会用 `--check` 选项校验，磁盘文件与重新生成结果不一致就报错，
防止文档与代码漂移。详见 [fields.generated.md](fields.generated.md)。

> 一句话记忆：**字段名用英文小写下划线；单位看表；比例字段一律填 0–1 小数**
> （如 0.82 表示 82%，不要写 82）。

---

## 3. 硬约束（hard）怎么写

硬约束：方案**违反**这一条，就直接**标红、踢出排名**——不参与比选。
每条硬约束对应一行规则 YAML。

### 3.1 字段一览

| 字段 | 是否必填 | 含义 |
| --- | --- | --- |
| `id` | ✅ | 规则编号，全局唯一，建议用 `C-XX`（Compliance） |
| `name` | ✅ | 中文名，给前端 / 报告看 |
| `type` | ✅ | 固定写 `hard` |
| `check` | ✅ | 一个布尔表达式，违反即不通过 |
| `message` | 可选 | 不通过时给用户看的说明，可以用 `{字段名}` 占位实际取值 |
| `when` | 可选 | 守卫表达式：为真时才检查 `check`；详见 3.4 |
| `source` | ✅ | 条文 / 经验出处，见第 5 节 |

`check` 表达式支持的运算符：`>=`、`<=`、`>`、`<`、`==`、`!=`、`and`、`or`、`not`，
以及 `contains`（判断列表是否含某元素）。

### 3.2 示例 1：简单比较

> 层高不低于 3.0 m（示例数值，待专业组确认条文号）。

```yaml
- id: C-03
  name: 住宅层高下限
  type: hard
  check: "floor_height >= 3.0"
  message: "层高 {floor_height} m 低于 3.0 m"
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`hard_simple.yaml`](../../backend/tests/fixtures/guide_examples/hard_simple.yaml)。

### 3.3 示例 2：用派生量

派生量由引擎在评估时计算（详见字段对照表的"派生量"段）。
规则里直接当字段名引用即可：

> 体形系数（外表面积 / 体积）不超过 0.5（示例数值）。

```yaml
- id: C-SHAPE
  name: 体形系数上限
  type: hard
  check: "shape_coefficient <= 0.5"
  message: "体形系数 {shape_coefficient} 偏大，建筑能耗与造价不利"
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`hard_derived.yaml`](../../backend/tests/fixtures/guide_examples/hard_derived.yaml)。

### 3.4 示例 3：带 `when` 条件

`when` 是一个布尔表达式；**只有它为真时才执行 `check`**。常见用法：
"只在某种结构 / 某种气候区 / 某种体量下"才检查某项。

> 仅当结构体系是钢结构时，要求方案把「防火达标」列入风险特征（示例规则）。

```yaml
- id: C-STEEL-COAT
  name: 钢结构防火涂层（条件检查）
  type: hard
  when: "structure_type == '钢结构'"
  check: "risk_features contains '防火达标'"
  message: "钢结构方案必须把「防火达标」列入风险特征并由人工复核"
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`hard_when.yaml`](../../backend/tests/fixtures/guide_examples/hard_when.yaml)。

---

## 4. 评分指标（metric）怎么写

评分指标：方案**不会因不达标被踢出**，但每个指标算一个 0–100 的分数，
最后按维度加权汇总。**指标不是"有没有"的问题，而是"好不好"的问题。**

### 4.1 用「画一条折线」来理解 points

每个 metric 都有一段 `scoring.points`，形如：

```yaml
scoring:
  kind: piecewise
  points:
    - [0.50, 0]
    - [0.80, 70]
    - [0.95, 100]
```

把它当成**画一条折线**：

- **横轴**是指标的真实取值（比如"标准层重复率 = 0.82"）；
- **纵轴**是分数（0 到 100）；
- 列表里每一对 `[指标值, 分数]` 就是折线上的一个**控制点**；
- 引擎在两个控制点之间**线性插值**（拉一条直线），落到折线上读出分数。

**画 points 之前，先想清楚三个问题**：

1. **多少算 0 分？**（最差情况）——这是第一个控制点的横坐标。
2. **多少算 100 分？**（最理想情况）——这是最后一个控制点的横坐标。
3. **中间有没有拐点？**（不线性变化的位置）——拐点也要单独列。

写完三个问题，`points` 就出来了。

### 4.2 三种常见形态

#### (1) 越大越好

![越大越好](img/metric_bigger_is_better.png)

> 标准层重复率越高，模板与构件周转越好。

```yaml
- id: K-01
  name: 标准层重复率（越大越好）
  type: metric
  dimension: construction
  value: "std_floor_repeat"
  scoring:
    kind: piecewise
    points:
      - [0.50, 0]
      - [0.80, 70]
      - [0.95, 100]
  weight_in_dimension: 1
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`metric_bigger_is_better.yaml`](../../backend/tests/fixtures/guide_examples/metric_bigger_is_better.yaml)。

#### (2) 越小越好

![越小越好](img/metric_smaller_is_better.png)

> 单栋户数过多会导致电梯排队与疏散困难，越少越好。

注意：**横轴仍按 x 从小到大排列**（必须严格递增），纵轴随之递减。

```yaml
- id: K-02
  name: 单栋户数（越小越好）
  type: metric
  dimension: quality
  value: "units_per_building"
  scoring:
    kind: piecewise
    points:
      - [60, 100]
      - [120, 70]
      - [200, 0]
  weight_in_dimension: 1
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`metric_smaller_is_better.yaml`](../../backend/tests/fixtures/guide_examples/metric_smaller_is_better.yaml)。

#### (3) 适中最好

![适中最好](img/metric_optimal_in_middle.png)

> 南向比例太低不利于日照，太高又牺牲通风与户型多样性；0.55 附近最理想。

适中最好 = **points 先升后降**。横轴仍按 x 严格递增；纵轴先升到 100，
到达峰值后再降回 0：

```yaml
- id: K-03
  name: 主要房间南向比例（适中最好）
  type: metric
  dimension: quality
  value: "south_room_ratio"
  scoring:
    kind: piecewise
    points:
      - [0.20, 0]
      - [0.55, 100]
      - [0.90, 0]
  weight_in_dimension: 1
  source: "TODO(专业组)：示例数值，正式条文号待补"
```

完整文件见 [`metric_optimal_in_middle.yaml`](../../backend/tests/fixtures/guide_examples/metric_optimal_in_middle.yaml)。

### 4.3 `weight_in_dimension` 是什么意思

每个 metric 都属于某个**维度**（`dimension`，取值见下表）；同一维度内的所有
metric 按 `weight_in_dimension` **加权平均**成"维度分"。

| dimension 取值 | 中文名 | 含义 |
| --- | --- | --- |
| `quality` | 居住品质 | 采光、通风、户型、电梯服务等 |
| `structure` | 结构安全 | 结构选型、抗震、风险特征 |
| `construction` | 施工友好 | 标准化、装配率、构件种类 |
| `green` | 绿色低碳 | 装配率、节能、得房率 |

**举例**：假设 `construction` 维度有 3 个 metric：

| metric | weight_in_dimension |
| --- | --- |
| 标准层重复率 | 1 |
| 预制构件种类数（越小越好） | 2 |
| 装配率 | 1 |

那它们的分数按 1 : 2 : 1 加权平均。如果三个 metric 各自是 80 / 60 / 100 分，
那 `construction` 维度分 = (80×1 + 60×2 + 100×1) / (1+2+1) = 75 分。

权重是相对值（不需要加起来 = 100），只要在同一维度内互相比较即可。

### 4.4 字段一览

| 字段 | 是否必填 | 含义 |
| --- | --- | --- |
| `id` | ✅ | 规则编号，建议 `K-XX`（Key metric） |
| `name` | ✅ | 中文名 |
| `type` | ✅ | 固定写 `metric` |
| `dimension` | ✅ | 所属维度，取值见 4.3 |
| `value` | ✅ | 字段名或表达式 |
| `scoring.kind` | ✅ | 现阶段固定 `piecewise`（分段线性） |
| `scoring.points` | ✅ | 控制点列表，每项 `[指标值, 分数]`，x 必须严格递增 |
| `weight_in_dimension` | ✅ | 同维度内的相对权重（正数） |
| `source` | ✅ | 条文 / 经验出处，见第 5 节 |

---

## 5. source 字段怎么填

`source` 是这条规则的**出处**，告诉看报告的人"你凭什么这么判 / 这么打分"。
统一写法：

### 5.1 来自规范原文

```
"GB 55038-2025 第 4.2.3 条"
"JGJ 100-2015 第 5.1.2 条"
```

格式建议：**规范编号 + 条文号**，中间用空格隔开。如果一个规则同时参考多条规范，
用分号分隔：

```
"GB 55038-2025 第 4.2.3 条；JGJ 100-2015 第 5.1.2 条"
```

### 5.2 经验规则（土木组）：理由

如果你写的是"组内经验判断，没有对应规范"，用下面的格式：

```
"经验规则（土木组）：标准层越多，模板与构件周转越高"
```

「组名」可以是「土木组 / 建筑组 / 结构组」等，方便追溯"这是谁拍板的"。
「理由」一句话说清"为什么这么定"，别只写"经验"两个字。

### 5.3 示例数值占位

写指南 / 示例时，**先用 `TODO(专业组)：示例数值，正式条文号待补` 占位**，
不要编造任何条文号，也不要凭空写一个阈值。专业组核对完规范原文后再改写。

---

## 6. 在 GitHub 网页上修改规则并提交 PR

完全不用装 Git / Python / VS Code。**整个流程在浏览器里完成**。

### 6.1 打开规则文件

1. 打开仓库首页 `https://github.com/<org>/zhuheng`（org 名称问队长）。
2. 顶部导航点 **Code**，进入文件浏览器。
3. 进入 `rules/` 目录（如 `rules/quality.yaml`）。每个文件名末尾的 `.yaml`
   表示"YAML 格式"，不是必填项。
4. 点击右上角的 ✏️ **Edit this file** 图标。

### 6.2 编辑

1. GitHub 会让你"Fork this repository"——意思是先在你自己的账号下复制一份。
   第一次会让你授权，授权完会自动跳回编辑器。
2. 直接在网页编辑器里改 YAML：
   - 想加新规则，把光标移到文件末尾另起一行，复制一条已有规则改字段值；
   - 想改阈值，改对应数字；
   - 改完滚动到页面底部。
3. 顶部会有提示："**Propose changes**"。在第一个框写"一句话说明这次改了什么"，
   例如 `quality: K-04 调整南向比例分段点`；第二个框可以留空（详细说明放到
   PR 描述里）。

### 6.3 提交

1. 点 **Propose changes** 按钮，GitHub 会把你的改动提交到你的 fork，并自动开一个
   Pull Request（PR）。
2. PR 标题默认就是你刚才写的那句话，可以再改；描述里写清楚"为什么这么改，
   改了哪些数值，有没有参考的规范"。
3. 点 **Create pull request**。
4. 等几分钟后页面会出现 `check_rules` / `pytest` 的检查结果：
   - ✅ 全绿 = 合并等队长审核；
   - ❌ 有红 = 点 **Details** 看失败原因，回到第 6.2 步继续改。

### 6.4 评审与合并

- 队长 / 高年级同学会在 PR 下面评论，问你"为什么改 0.55 不是 0.50"之类的；
  在评论框直接回复即可，每次回复都会自动保存到 PR 历史。
- 评审通过后，队长点 **Merge pull request** → **Confirm merge**，
  改动就合到主分支了。

---

## 7. 怎么看 check_rules 报错

`check_rules` 是仓库自带的小工具，**改完规则后跑一遍**就能发现常见错误。
本节用 5 条实际跑出来的典型报错讲怎么改。

### 7.1 怎么跑

```bash
# 校验整个 rules/ 目录
uv run --project backend python scripts/check_rules.py

# 只校验单个文件
uv run --project backend python scripts/check_rules.py rules/quality.yaml
```

跑完会输出每个文件的 ERROR / WARNING 清单，末尾一行「汇总：X 个文件，
Y 个 ERROR，Z 个 WARNING」。**任何 ERROR 都会让脚本退出码 = 1**，
CI 也会因此失败——必须改完再推。

### 7.2 五条典型报错与解法

下面 5 条都来自仓库 `backend/tests/fixtures/guide_examples/_bad/`，
你也可以自己跑一遍看：

```bash
uv run --project backend python scripts/check_rules.py backend/tests/fixtures/guide_examples/_bad/
```

#### (1) `TAB_INDENT` · 检测到 Tab 缩进

```
[ERROR] hard_tab_indent.yaml:8 · TAB_INDENT ·
  检测到 Tab 缩进。YAML 要求用 2 空格缩进，请把 Tab 替换为空格。
```

**原因**：第 8 行以 Tab 开头（或行内有 Tab）。

**怎么改**：
- **网页编辑器**：右下角点 "Indent mode" 切换到 Spaces，复制粘贴进文本框，
  GitHub 自动按 4 空格处理；
- **VS Code 等本地编辑器**：按 `Ctrl+H` 调出替换，正则模式开起来，搜索 `^\t+`
  替换成 2 个空格，全选文件替换一次；
- 如果只有一两行，直接删除 Tab 重打 2 个空格。

#### (2) `CHINESE_COLON` · 检测到中文冒号

```
[ERROR] hard_chinese_colon.yaml:5 · CHINESE_COLON ·
  检测到中文冒号「：」。YAML 的 key 与 value 之间
  必须用英文半角冒号「:」，请替换。
```

**原因**：键名后面用了全角 `：` 而不是半角 `:`。

**怎么改**：把那一行的中文冒号 `：` 改成英文冒号 `:`。如果你不知道怎么区分，
看宽度：英文 `:` 是窄的；中文 `：` 是宽的、和汉字一样宽。

#### (3) `UNALIGNED` · 同一缩进级别内重复出现 key「X」

```
[WARNING] hard_unaligned.yaml:12 · UNALIGNED ·
  同一缩进级别内重复出现 key「id」（行 5 与行 12），
  通常是缩进不齐导致兄弟节点错位，请检查。
```

**原因**：两条规则（或两个键）的缩进空格数不一致，导致 YAML 把它们当成
"同辈"重复了。

**怎么改**：让同一文件内所有 `- ` 顶头、所有 `id: / name: / type:` 等子键缩进 2 空格，
**全文对齐到同一列**。VS Code 里按 `Shift+Alt+F` 格式化（如果有 Prettier 配置）。

#### (4) `METRIC_POINTS_NOT_MONOTONIC` · points 第一列必须严格递增

```
[ERROR] metric_points_not_monotonic.yaml:1 · METRIC_POINTS_NOT_MONOTONIC ·
  points 第一列必须严格递增，当前是 [0.95, 0.8, 0.5]。
  「适中最好」的指标应当先升后降，但仍要严格递增。
```

**原因**：`points` 列表里的横坐标（第一个数字）没有按从小到大排。

**怎么改**：把控制点按横坐标从小到大排：

```yaml
points:
  - [0.50, 0]    # ← 最小 x 在最上面
  - [0.80, 70]
  - [0.95, 100]  # ← 最大 x 在最下面
```

**「越小越好」也一样**：横坐标从小到大写，分数纵坐标递减即可表达。

#### (5) `METRIC_BAD_DIMENSION` · dimension 必须是合法维度

```
[ERROR] metric_missing_dimension.yaml:1 · METRIC_BAD_DIMENSION ·
  dimension 必须是 ('quality', 'structure', 'construction', 'green') 之一，
  实际是 'cost'
```

**原因**：写错了 `dimension` 字段。

**怎么改**：从四个合法值里选一个——见 4.3 节的表格。
如果你新加了一个维度，需要先和队长对齐改 `app/models/eval.py` 的 `DimensionKey`，
**不要**直接在 YAML 里造新值，否则前端 / 评分都会崩。

### 7.3 错误汇总速查表

| 错误码 | 含义 | 怎么改 |
| --- | --- | --- |
| `TAB_INDENT` | 用了 Tab 缩进 | 替换为空格 |
| `CHINESE_COLON` | 用了中文全角冒号 | 改成英文半角 `:` |
| `UNALIGNED` | 缩进不齐 | 让所有子键对齐到同一列 |
| `MISSING_FIELD` | 缺必填字段（id/name/type） | 补上字段 |
| `METRIC_POINTS_NOT_MONOTONIC` | points 第一列未严格递增 | 按 x 升序重排 |
| `METRIC_BAD_DIMENSION` | dimension 取值不合法 | 从四选一里挑 |
| `METRIC_MISSING_SCORING` | metric 规则缺 `scoring` 子对象 | 补上 `scoring.kind` 与 `scoring.points` |
| `HARD_MISSING_CHECK` | hard 规则缺 `check` 表达式 | 补上一个布尔表达式 |
| `YAML_PARSE` | YAML 整体解析失败 | 通常是上面几类之一导致，先修格式错误再重跑 |

---

## 8. 一页速查卡

> 打印出来贴在桌上。

### YAML 速记

- 缩进：2 空格；**禁用 Tab**。
- 冒号：英文半角 `:`；**禁用全角 `：`**。
- 列表：`- `（横线 + 空格）。
- 引号：含特殊字符或中文以外的多字符值，用双引号包起来。

### 一条 hard 规则的最小骨架

```yaml
- id: C-XX             # 编号，全局唯一
  name: 中文名           # 给前端 / 报告看
  type: hard             # 固定
  check: "字段 运算符 阈值"  # 布尔表达式
  message: "提示 {字段}"   # 可选：{字段} 会被实际值替换
  # when: "条件"         # 可选：条件为真才检查
  source: "规范编号 第 X 条"  # 或 "TODO(专业组)：..."
```

### 一条 metric 规则的最小骨架

```yaml
- id: K-XX
  name: 中文名
  type: metric
  dimension: quality     # quality / structure / construction / green
  value: "字段名"        # 或表达式
  scoring:
    kind: piecewise      # 现阶段唯一支持的类型
    points:
      - [x1, y1]
      - [x2, y2]
      - [x3, y3]
  weight_in_dimension: 1 # 同维度内的相对权重
  source: "经验规则（XX组）：理由"
```

### points 三种画法

| 类型 | x 怎么排 | y 怎么排 |
| --- | --- | --- |
| 越大越好 | 从小到大 | 从小到大 |
| 越小越好 | 从小到大 | 从大到小 |
| 适中最好 | 从小到大，**峰值后再继续递增** | 先升后降 |

### 常用命令

```bash
# 校验所有规则
uv run --project backend python scripts/check_rules.py

# 校验单个文件
uv run --project backend python scripts/check_rules.py rules/quality.yaml

# 重新生成字段对照表（模型改了之后跑）
uv run --project backend python scripts/gen_field_table.py

# 跑完测试看指南里的示例还过不过
make test
```

### 改完规则要做的 3 件事

1. 跑 `scripts/check_rules.py`，**所有 ERROR 都得消除**。
2. 在 PR 描述里写清楚改了哪些字段、参考了哪条规范、为什么这么改。
3. 等 CI 全绿、队长评审通过后才会合并；任何红色 ❌ 都不能合。

---

**文档维护**：土木组 / 建筑组同学都可以改这份文档。
改完之后跑一遍 `make test` 确认示例还能通过校验，再提交 PR。
