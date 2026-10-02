# PR：T9 给非程序员的规则编写指南

## 做了什么

按任务 T9 要求，给土木与建筑专业同学写一份能在 GitHub 网页上独立完成规则编写并提交 PR 的入门指南。所有示例都通过 `check_rules` 校验，字段对照表由脚本从 JSON Schema 自动渲染并在 CI 中防漂移。

### `docs/rules-guide.md` — 主交付物

8 个章节按任务逐条对应：

1. **五分钟看懂 YAML**：缩进 / 冒号 / 列表 / 引号四件事，最常见三种错误（Tab 缩进 / 中文冒号 / 缩进不齐）每种都给出「错误写法 vs 正确写法」对照。
2. **字段对照表**：嵌入 `docs/fields.generated.md`（见下）。
3. **硬约束怎么写**：3 个示例（`hard_simple.yaml` / `hard_derived.yaml` / `hard_when.yaml`），分别演示简单比较、用派生量、带 `when` 条件。
4. **评分指标怎么写**：用「画一条折线」解释 `points`（横轴指标值 / 纵轴分数 / 分段线性插值），三种形态（越大越好 / 越小越好 / 适中最好）各配一张 `docs/img/*.png`，再讲 `weight_in_dimension` 的含义。
5. **source 怎么填**：规范编号 + 条文号；或「经验规则（XX组）：理由」；并强调必须来自亲自核对过的规范原文。
6. **在 GitHub 网页上修改规则并提交 PR**：完整分步说明（打开 → 编辑 → Fork → Propose → CI 验证 → 合并）。
7. **怎么看 check_rules 报错**：5 条典型报错（`TAB_INDENT` / `CHINESE_COLON` / `UNALIGNED` / `METRIC_POINTS_NOT_MONOTONIC` / `METRIC_BAD_DIMENSION`）的实际输出 + 改法，附错误码速查表。
8. **一页速查卡**：YAML 速记 + 两种规则骨架 + points 三种画法 + 常用命令 + 改完规则要做的 3 件事。

所有示例的阈值 / 分段点都标注「示例数值」，`source` 全部写 `TODO(专业组)：示例数值，正式条文号待补`，**未引用任何真实条文号**。

### `docs/fields.generated.md` — 由脚本生成

`scripts/gen_field_table.py` 从 `data/schema/*.schema.json` 自动渲染，包含：
- 一、项目参数（`ProjectParams`）
- 二、方案参数（`SchemeParams`），按 5 个 group 分小节
- 三、评估结果（`EvalResult`）
- 四、派生量（`shape_coefficient` / `units_per_building` / `units_per_floor` / `total_height` / `floor_efficiency`）

脚本带 `--check` 选项：与磁盘上 `docs/fields.generated.md` 不一致时退出码 1，CI 把这一步加上后，任何字段元信息改动都会强制同步文档。

### `docs/img/` — 3 张折线示意图

`scripts/gen_metric_charts.py` 用 matplotlib 生成，配色避开红绿色盲，控制点带坐标标注：

- `metric_bigger_is_better.png` — 标准层重复率（越大越好）
- `metric_smaller_is_better.png` — 单栋户数（越小越好）
- `metric_optimal_in_middle.png` — 南向比例（适中最好）

中文字体自动探测（实测用上 Source Han Sans SC），无中文字体时给 WARN 而不报错。

### `scripts/check_rules.py` — 最小可用规则校验脚本

T3 任务会做完整版，T9 先把「够用即可」的最小版实现出来，否则指南里的"示例能通过校验"就没法落地。具体校验：

| 类别 | 错误码 | 说明 |
| --- | --- | --- |
| 文本层 | `TAB_INDENT` | 行首 / 缩进位含 Tab |
| 文本层 | `CHINESE_COLON` | 形如 `key：value` 用了中文全角冒号 |
| 结构层 | `UNALIGNED` | 同一缩进级别内出现重复 key（启发式 WARNING） |
| 结构层 | `MISSING_FIELD` | 缺 id / name / type |
| 结构层 | `BAD_TYPE` | type 不是 hard / metric |
| 结构层 | `HARD_MISSING_CHECK` | hard 规则缺 `check` |
| 结构层 | `METRIC_MISSING_VALUE` | metric 规则缺 `value` |
| 结构层 | `METRIC_BAD_DIMENSION` | dimension 不在四选一里 |
| 结构层 | `METRIC_MISSING_SCORING` | 缺 `scoring` 子对象 |
| 结构层 | `METRIC_BAD_SCORING_KIND` | scoring.kind 不在白名单 |
| 结构层 | `METRIC_EMPTY_POINTS` / `METRIC_BAD_POINT` | points 形状错 |
| 结构层 | `METRIC_POINTS_NOT_MONOTONIC` | 第一列未严格递增 |
| 解析层 | `YAML_PARSE` | YAML 解析失败 |
| 解析层 | `TOP_NOT_LIST` / `RULE_NOT_OBJECT` | 顶层 / 规则元素形状错 |

退出码：0 = 全过；1 = 有 ERROR；空目录友好（视为未启用，返回 0 + 提示信息）。

### `backend/tests/fixtures/guide_examples/`

12 个 YAML 文档，6 正确 + 6 错误：

```
guide_examples/
├── hard_simple.yaml                    # 简单比较
├── hard_derived.yaml                   # 用派生量
├── hard_when.yaml                      # 带 when 条件
├── metric_bigger_is_better.yaml        # 越大越好
├── metric_smaller_is_better.yaml       # 越小越好
├── metric_optimal_in_middle.yaml       # 适中最好
└── _bad/
    ├── hard_tab_indent.yaml            # Tab 缩进
    ├── hard_chinese_colon.yaml         # 中文冒号
    ├── hard_unaligned.yaml             # 缩进不齐
    ├── hard_missing_field.yaml         # 缺字段
    ├── metric_points_not_monotonic.yaml # points 未递增
    └── metric_missing_dimension.yaml   # dimension 错
```

### `backend/tests/test_guide_examples.py` — 16 项测试

- 6 个正确示例 → 跑 check_rules 必须 exit 0（参数化）；
- 6 个错误示例 → 跑 check_rules 必须 exit 1 且包含期望错误码（参数化）；
- `docs/fields.generated.md` 必须存在且含派生量段；
- `gen_field_table.py --check` 必须返回 0（防漂移）；
- `scripts.check_rules` 模块可导入；
- `iter_rule_files()` 正确跳过 `weights.yaml`。

### CI / Makefile 改动

`.github/workflows/ci.yml`：在 `pytest` 之后增加两步：

```yaml
- name: check_rules
  run: uv run python ../scripts/check_rules.py
- name: gen_field_table --check
  run: uv run python ../scripts/gen_field_table.py --check
```

`Makefile`：

- `help` 新增 `make docs-check`；
- 新增 `docs-check` target：调 check_rules + gen_field_table --check + gen_metric_charts 三步。

`backend/pyproject.toml`：给 `dev` 组追加 `matplotlib>=3.8`（一次性脚本专用，不进运行时）；同步 `backend/uv.lock`。

## 如何运行

```bash
# 校验规则 YAML（默认扫 rules/）
uv run --project backend python scripts/check_rules.py

# 校验指定目录或文件
uv run --project backend python scripts/check_rules.py backend/tests/fixtures/guide_examples/
uv run --project backend python scripts/check_rules.py backend/tests/fixtures/guide_examples/hard_simple.yaml

# 重新生成字段对照表（模型改动后跑）
uv run --project backend python scripts/gen_field_table.py

# 校验文档与 JSON Schema 一致（CI 用）
uv run --project backend python scripts/gen_field_table.py --check

# 重新生成 3 张折线示意图
uv run --project backend python scripts/gen_metric_charts.py

# 一键跑文档自检
make docs-check
```

## 如何测试

```bash
make test       # = cd backend && uv run pytest（99 项）
make lint       # = cd backend && uv run ruff check .  + 前端 tsc --noEmit
```

### 实测结果（本机）

```
$ cd backend && uv run pytest
============================== test session starts ==============================
...
tests/test_db_crud.py ............                                          [ 12%]
tests/test_excel_parser.py ............                                     [ 24%]
tests/test_excel_scripts.py .......                                         [ 31%]
tests/test_excel_template.py ........                                       [ 39%]
tests/test_guide_examples.py ................                                [ 55%]   <-- 新增 16 项
tests/test_health.py .                                                      [ 56%]
tests/test_import_endpoint.py ......                                        [ 62%]
tests/test_mock_data.py ...............                                     [ 77%]
tests/test_models_params.py ..................                              [ 95%]
tests/test_schema_endpoint.py ....                                          [100%]
======================= 99 passed, 2 warnings in 5.71s ========================

$ uv run ruff check .
All checks passed!

$ uv run ruff check ../scripts/check_rules.py ../scripts/gen_field_table.py ../scripts/gen_metric_charts.py
All checks passed!

$ uv run --project backend python scripts/check_rules.py backend/tests/fixtures/guide_examples
━━ backend\tests\fixtures\guide_examples\hard_derived.yaml
  [OK] 无 ERROR / WARNING
━━ backend\tests\fixtures\guide_examples\hard_simple.yaml
  [OK] 无 ERROR / WARNING
━━ backend\tests\fixtures\guide_examples\hard_when.yaml
  [OK] 无 ERROR / WARNING
━━ backend\tests\fixtures\guide_examples\metric_bigger_is_better.yaml
  [OK] 无 ERROR / WARNING
━━ backend\tests\fixtures\guide_examples\metric_optimal_in_middle.yaml
  [OK] 无 ERROR / WARNING
━━ backend\tests\fixtures\guide_examples\metric_smaller_is_better.yaml
  [OK] 无 ERROR / WARNING

汇总：6 个文件，0 个 ERROR，0 个 WARNING

$ uv run --project backend python scripts/check_rules.py backend/tests/fixtures/guide_examples/_bad
━━ backend\tests\fixtures\guide_examples\_bad\hard_chinese_colon.yaml
  [ERROR] ...:5 · CHINESE_COLON · 检测到中文冒号「：」...
...
汇总：6 个文件，16 个 ERROR，1 个 WARNING
（exit code: 1）

$ uv run --project backend python scripts/gen_field_table.py --check
OK · docs\fields.generated.md 与 JSON Schema 同步
```

## 遗留问题

1. **`scripts/` 目录其它旧脚本有 ruff 告警**：本次只保证 `check_rules.py` / `gen_field_table.py` / `gen_metric_charts.py` 通过 ruff；`seed_mock.py` / `export_schema.py` / `export_schemes.py` / `import_schemes.py` / `make_template.py` 都有未启用的 `noqa` 告警（属 RUF100，规则 `E402` 没启用导致）。这些是已有遗留，不在本任务范围。建议下个 PR 单独清理 `pyproject.toml` 的 ruff `select` 配置，把 `E402` 打开再 `ruff check --fix`。
2. **`check_rules.py` 是最小可用版**：只校验 YAML 结构与最常见的文本错误，不求值 `check` 表达式、不验证 `value` 字段名是否在 `SchemeParams` 里。T3 任务会在此基础上扩展（表达式求值 / 字段名合法性 / 跨规则引用一致性等）；T9 不抢 T3 的活。
3. **`rules/*.yaml` 还是空的**：当前 `rules/` 只有 `.gitkeep`，专业组同学按 T3 起把规范搬进 YAML 时，`check_rules` 会接管校验；本任务已确保空目录时返回 0 + 提示，不会在 CI 上"误报"。
4. **真实规范条文号留给专业组填写**：所有示例都标 `TODO(专业组)：示例数值，正式条文号待补`，T3 任务对照规范原文补完后会自动落到各 `rules/*.yaml`。
5. **图表用 matplotlib**：作为 `dev` 依赖引入，不进运行时；图一次性生成提交进 `git`，不参与 CI。
6. **`docs/rules-guide.md` 第 7 节错误码速查表**和 `scripts/check_rules.py` 的实现耦合：后续若新增错误码（如 T3 的表达式校验），需同步更新文档第 7 节末的速查表。
7. **CI 未跑**：本机已确认所有命令通过；GitHub Actions 跑前需把 `docs/rules-guide` 推到 `origin/docs/rules-guide` 触发 workflow（`.github/workflows/ci.yml` 仅在 `feat/**` push 与 PR 时跑，`docs/**` 不直接触发；建议合并时把分支名前缀改为 `feat/` 或临时改成 `feat/` 再推）。
