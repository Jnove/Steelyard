# GitHub main 与 professional-rules 分支的规则合并评审

> 评审对象：`origin/main` 上的 `9923b3b feat:更新四个yaml`（yushibujue369@qq.com，2026-10-12 19:57）
> 对照对象：本地 `jnove/professional-rules` 分支（HEAD `af4ef81`，另有 3 条规则未提交）
> 数据来源：本地克隆里已抓取的远端对象 + 仓库自带校验器实测
> 限制：本次评审环境**无法直连 github.com**（TLS `schannel: SEC_E_NO_CREDENTIALS`，DNS 亦不可用），
> 因此看不到 Actions 运行日志，也看不到 9923b3b 之后是否还有新提交。换到有网环境请先 `git fetch` 复核。

## 一、两边现状

| 项目 | GitHub `origin/main` | 本地 `jnove/professional-rules` |
| --- | --- | --- |
| HEAD | `9923b3b` | `af4ef81`（与远端同步） |
| 规则条数 | **22**（C 7 / K 2 / G 5 / Q 6 / S 2） | **35**（C 18 / K 2 / G 2 / Q 4 / S 9），其中 C-18、S-08、S-09 未提交 |
| 校准状态 | K-01、K-02、S-01、S-02 仍是 `【示例】`+`TODO` 出处；C-04~C-07、G-02~G-05、Q-04~Q-06 是本次新增 | 分三轮按规范原文核定 31 条（[open-items 1.1](open-items.md)），其后 `af4ef81` 又加 S-07 高宽比；已提交 32 条，另有 3 条未提交 |
| `weights.yaml` | 换成 `dimensions:` + `roles:` 嵌套、**5 个维度**（多出 `compliance`）、5 个角色 | 4 角色 × 4×4 AHP 互反矩阵，与引擎一致 |
| 未提交改动 | — | 28 个文件 512 行（MiC 体系 `mic_system`、`concrete_grade`、C-18、S-08/S-09 及重生成的 schema / 前端类型 / 字段表 / Excel 模板） |

复核命令：

```bash
git log --oneline main..origin/main                      # main 上多出来的提交
git grep -n -E "^(- id:|  name:)" 9923b3b -- rules       # 远端那套规则的清单
```

## 二、先判断一件事：那个提交很可能没有部署出去

按 [.github/workflows/ci.yml](../.github/workflows/ci.yml) 的作业图：`backend` 作业会跑
`scripts/check_rules.py`，任何错误即退出码 1；`package` 与 `deploy` 都 `needs: [backend, frontend]`。
把 9923b3b 的 `rules/` 抽出来用仓库自己的校验器跑，结果是：

```
汇总：6 个文件，13 个错误，4 个警告   （退出码 1）
```

错误全部集中在 `weights.yaml`（`未知角色 dimensions / roles / validation`、`缺少角色
['government','developer','contractor','resident']`）。据此推断：**CI 在 backend 作业就红了，
package / deploy 被跳过，生产仍是 `de59585`**。

推论的意义：main 上那批新编号（C-04~C-07、G-02~G-05、Q-04~Q-06）**还没有对外成为既成事实**
（报告、前端、库里都还不会出现），所以两边现在都还有改号自由——但必须先定哪一套是权威。

复核命令（可复现）：

```bash
mkdir -p /tmp/mainrules && git archive --format=tar -o /tmp/mainrules/rules.tar 9923b3b rules \
  && tar -xf /tmp/mainrules/rules.tar -C /tmp/mainrules
uv run --project backend python scripts/check_rules.py --rules-dir /tmp/mainrules/rules
```

## 三、`weights.yaml` 两方案对照

### 3.1 差异在哪

GitHub 版（72 行）用 `dimensions:` 声明 5 个维度（`compliance` / `quality` / `structure` /
`construction` / `green`），再在 `roles:` 下按角色给字典权重，末尾还有一段 `validation:`：

```yaml
roles:
  government:
    label: 政府
    weights: {compliance: 0.35, quality: 0.15, structure: 0.25, construction: 0.10, green: 0.15}
    rationale: "政府首先关注强制性规范和结构安全底线……"
```

引擎侧只认 `government / developer / contractor / resident` 四个**顶层**键、每角色只允许
`name / note / source / matrix / weights` 五个字段（[weights.py:146-160](../backend/app/engine/weights.py#L146-L160)），
维度顺序固定为 `quality / structure / construction / green`
（[mcdm.py:51](../backend/app/engine/mcdm.py#L51)）。两套格式不是"写法不同"，是模型不同。

还有一个值得注意的点：**`compliance` 在当前架构里本来就是门槛，不是加权维度**。
[rank.py:320-371](../backend/app/api/rank.py#L320-L371) 会把 error 级硬约束未通过的方案直接排除出排名，
`EvalResult` 也只有 4 个维度分（[eval.py](../backend/app/models/eval.py)）。
所以对"通过了全部硬约束"的方案，合规项是一个常数，在加权求和里会互相抵消——
把它当成第 5 个权重，对排序结果没有影响；只有"通过但接近限值也要扣分"才需要真做成一个指标，
那是新增指标，不是给权重加一维。

### 3.2 方案 A：保留 4 维（推荐）

有两种并法，先定口径再动手：

**A1 — 采纳 GitHub 的数值口径，转成直给权重。** 丢掉 `compliance` 后按比例归一化（已算好，校验和均为 1）：

| GitHub 角色 | 5 维原值（c/q/s/c/g） | 映射到引擎角色 | 4 维直给 `weights: [quality, structure, construction, green]` |
| --- | --- | --- | --- |
| government | .35/.15/.25/.10/.15 | government | `[0.2308, 0.3846, 0.1538, 0.2308]` |
| residents | .20/.45/.15/.05/.15 | resident | `[0.5625, 0.1875, 0.0625, 0.1875]` |
| developer | .25/.20/.20/.20/.15 | developer | `[0.2667, 0.2667, 0.2667, 0.2000]` |
| construction | .30/.10/.25/.25/.10 | contractor | `[0.1429, 0.3571, 0.3571, 0.1429]` |
| design | .30/.20/.25/.10/.15 | 引擎无此角色 | 丢弃，或新增 `ROLE_KEYS`（见方案 B） |

落地写法（引擎本就支持直给 `weights`，见 [rules/weights.yaml](../rules/weights.yaml) 顶部注释）：

```yaml
government:
  name: 政府 / 保障房平台
  note: >-
    政府首先关注强制性规范和结构安全底线，同时兼顾居住品质、产业化实施与绿色目标。
    （compliance 0.35 作为硬约束门槛由引擎处理，不进加权）
  source: "经验规则（专业组）：综合 GB 55038—2025 等规范底线与治理目标赋权；数值需项目访谈或 AHP 校准"
  weights: [0.2308, 0.3846, 0.1538, 0.2308]
```

代价：直给权重没有一致性检验，`ahp` 为 `null`、CR 为空——这是引擎既有行为
（[weights.py:99-102](../backend/app/engine/weights.py#L99-L102)、`rules/weights.yaml` 顶部 55-65 行有说明），
不是本次改动引入的。

**A2 — 数值也保留分支自己的矩阵。** 只把 GitHub 版的 `label`/`rationale` 作为 `note` 素材抄过来，
`matrix` 沿用分支现有的四套。理由：GitHub 版自己在第 3 行写明"是初始专家口径，需通过项目访谈或 AHP 校准"，
而分支矩阵带着"为什么这么排"的 note 和源文件依据。

方案 A 的总改动量：**只改 `rules/weights.yaml` 一个文件**，然后跑
`uv run --project backend python scripts/check_rules.py` 即可。

### 3.3 方案 B：采纳 5 维（含 compliance 权重）

这不是改 YAML 能完成的，涉及引擎、契约、前端、测试四层，且要先回答"合规分怎么算"：

| # | 位置 | 要改什么 |
| --- | --- | --- |
| 1 | [mcdm.py:51](../backend/app/engine/mcdm.py#L51) | `CRITERION_ORDER` 由 4 元组变 5 元组；`topsis` / `sensitivity` / `pareto` 的列序全跟着变 |
| 2 | [eval.py](../backend/app/models/eval.py) | `DimensionKey` / `DimensionScores` / `DimensionCoverage` 加第 5 维，并**定义合规分的计算方式**（硬约束通过率？）——这是建模决策，没人拍板就写不出代码 |
| 3 | [weights.py:55](../backend/app/engine/weights.py#L55) | `ROLE_KEYS` 四角色变五角色（`residents`、`construction`、`design`）；注意 `construction` 与准则名撞名，读代码易混 |
| 4 | [weights.py:146-311](../backend/app/engine/weights.py#L146-L311) | 解析器改成 `dimensions:` / `roles:` / `validation:` 三段式 + 字典权重；`RoleWeightTemplate.weights` 变 5 个 |
| 5 | [rank.py:241-267](../backend/app/api/rank.py#L241-L267)、[374-385](../backend/app/api/rank.py#L374-L385) | `n = len(CRITERION_ORDER)` 的长度校验、`weights` 个数、5×5 AHP 矩阵（对"合规"做两两比较语义可疑）、打分矩阵列数 |
| 6 | [rank.py:457-474](../backend/app/api/rank.py#L457-L474) | `GET /rank/roles` 返回结构（`label`/`weights`/`rationale` vs 现在的 `name`/`note`/`source`/`ahp`） |
| 7 | [check_rules.py:709](../scripts/check_rules.py#L709)、[rules-guide.md](rules-guide.md) | CI 闸门与规则指南同步（否则写错也没人拦） |
| 8 | `data/schema/jsonschema/*.json`、`frontend/src/api/generated/*.ts` | 重新生成并提交；CI 用 `export_schema --check`、`gen:types --check` 强制一致（[ci.yml:44-50](../.github/workflows/ci.yml#L44-L50)、[ci.yml:73-76](../.github/workflows/ci.yml#L73-L76)） |
| 9 | 前端排名页、`backend/tests/test_rank_endpoint.py`、前端 fixtures | 角色下拉、滑杆、权重展示、断言全部跟着变 |

结论：**建议方案 A 先落地（恢复能用的主分支），方案 B 若确实要，单独立项**，
并且第一步是让专业组书面确认"合规是否参与加权、以什么形式参与"。

## 四、编号撞车：完整对照

main 22 条与分支 35 条按编号对齐后是三类：

### 4.1 同号不同主题（11 条）— 必须解决

| 编号 | GitHub main | 本地分支 |
| --- | --- | --- |
| C-01 | 建筑总高不超过项目限高 | 住宅层高下限 |
| C-03 | 建筑密度不超过上限 | 建筑总高不超限高 |
| C-04 | 新建住宅层高下限 | 四层及以上须设电梯 |
| C-06 | 住宅结构体系取值合法 | 南向窗墙面积比不超限 |
| C-07 | MiC 方案装配率基本门槛 | 北向窗墙面积比不超限 |
| G-01 | 预估装配率 | 体形系数（越小越好） |
| G-02 | 标准层重复率 | 预估装配率（越大越好） |
| Q-01 | 得房率 | 主要房间南向比例（越大越好） |
| Q-02 | 南向房间比例 | 得房率（越大越好） |
| Q-03 | 窗地比 | 单栋户数（越小越好，仅高层适用） |
| Q-04 | 每单元电梯数 | 采光充足度（窗地比，越大越好） |

### 4.2 同号同主题（6 条）— 直接取分支版本

| 编号 | 说明 |
| --- | --- |
| C-02 | 容积率不超上限 |
| C-05 | 十二层及以上每单元不少于两台电梯 |
| K-01 / K-02 | main 还是 `【示例】`（TODO 出处），分支已校准 |
| S-01 / S-02 | main 还是 `【示例】`，分支已校准（风险特征加权指数、钢结构人工复核） |

### 4.3 各自独有

- **仅 main 有（5 条）**：G-03 预制构件种类数、G-04 体形系数、G-05 楼层效率、Q-05 单栋户数、Q-06 标准层交通规模。
- **仅分支有（18 条）**：C-08 东西向窗墙比、C-09/C-10 建筑密度（地块上限 + 国标强制上限）、
  C-11/C-12 建筑高度控制最大值、C-13 楼板厚度、C-14 设计工作年限、C-15 采光系数、
  C-16 日照时数、C-17 绿地率、C-18 混凝土强度等级、S-03 结构体系适用性、S-04 建筑总高、
  S-05/S-06 体系最大适用高度（6/7 度）、S-07 高宽比、S-08/S-09 MiC 最大适用高度（6/7 度）。

### 4.4 处置建议：以分支为权威，把 main 当素材并入

理由：分支 35 条是 2026-10 按规范原文核定过的（过程见
[专业组规则核定记录](archive/professional-rules-2026-10.md)），
main 的 22 条里 4 条还是示例、缺窗墙比/日照/采光/绿地等强条；
而 main 真正带来新信息的只有 5 条。逐条处置：

| main 条目 | 分支对应 | 处置 |
| --- | --- | --- |
| C-01 建筑总高不超限高 | C-03 建筑总高不超限高 | 主题重复，取分支 C-03；比对后把 main 的限值口径并进 C-03 |
| C-02 容积率 | C-02 | 同号同题，取分支 |
| C-03 建筑密度 | C-09 / C-10 | 主题重复（分支拆成地块上限 + 国标），取分支 |
| C-04 新建住宅层高下限 | C-01 住宅层高下限 | 主题重复，取分支 |
| C-05 电梯两台 | C-05 | 同号同题，取分支 |
| C-06 住宅结构体系取值合法 | 无（分支 S-03 是评分指标，不是硬约束） | **并入**：占分支新号 **C-19** |
| C-07 MiC 装配率基本门槛 | 无硬约束（分支 G-02 是评分指标） | **并入**：占分支新号 **C-20**；与 G-02 的关系要定 |
| G-01 预估装配率 | G-02 预估装配率 | 主题重复，取分支 |
| G-02 标准层重复率 | K-01 标准层重复率 | 主题重复，取分支（注意维度归属：main 放 green，分支放 construction） |
| G-03 预制构件种类数 | K-02 预制构件种类数 | 主题重复，取分支（同样是 green vs construction 的归属分歧） |
| G-04 体形系数 | G-01 体形系数 | 主题重复，取分支 |
| G-05 楼层效率 | 无（`floor_efficiency` 已是派生量） | **并入**：占分支新号 **G-03** |
| Q-01 得房率 | Q-02 得房率 | 主题重复，取分支 |
| Q-02 南向房间比例 | Q-01 主要房间南向比例 | 主题重复，取分支 |
| Q-03 窗地比 | Q-04 采光充足度（窗地比） | 主题重复，取分支 |
| Q-04 每单元电梯数 | 无（C-04/C-05 是电梯硬约束） | **并入**：占分支新号 **Q-05**，先确认与 C-04/C-05 不重复 |
| Q-05 单栋户数 | Q-03 单栋户数 | 主题重复，取分支 |
| Q-06 标准层交通规模 | 无 | **并入**：占分支新号 **Q-06** |
| S-01 / S-02 | 同号同题 | 取分支 |

并入后分支从 35 条变 **40 条**：新增 C-19、C-20、G-03、Q-05、Q-06。
反方向（以 main 为权威、给分支改号）不建议——分支编号已被大量文档与证据引用：

| 位置 | 引用条数 | 可否重生成 |
| --- | --- | --- |
| `docs/*.md`（`rules-guide.md` 25、`open-items.md` 31、`professional-rules-2026-10.md` 69、`t8-fake-report.md` 41 等） | 169 | 否，含历史核定记录 |
| `docs/evidence/*.sse.txt`、`docs/screenshots/t7/demo-report.md` | 105 | 否，历史证据样本 |
| `backend/tests/`、`scripts/` | ≈114 | 其中多数是 fixtures 自己的合成编号，真正受影响的是断言真实 `rules/` 的少数用例 |
| `frontend/src/mocks/data.json` 等生成物 | 144 | 是（`scripts/export_frontend_fixtures.py`） |

## 五、待办

- [ ] 有网环境 `git fetch` 复核 `origin/main` 是否已有人修 `weights.yaml`（本地数据可能已过期）
- [ ] 定 `weights.yaml` 口径：方案 A1（转数值）/ A2（留分支矩阵）/ B（上 5 维，需立项）
- [ ] 定角色集合：是否新增 `design`（GitHub 版有，引擎现在没有）
- [ ] 定维度归属分歧：标准层重复率、预制构件种类数归 `green` 还是 `construction`
- [ ] 并入 main 的 5 条新规则并按分支方案定号（C-19、C-20、G-03、Q-05、Q-06）
- [ ] 合并后跑 `scripts/check_rules.py` + `make test`，并把 5 条新规则的 `source` 按
      「规范编号 第 X 条」或「经验规则（XX组）：理由」的格式补齐
- [ ] 更新 [open-items.md](open-items.md) 与 [archive/professional-rules-2026-10.md](archive/professional-rules-2026-10.md) 的条数
