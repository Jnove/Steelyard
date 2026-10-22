# 案例专用分支与案例库

2026-10-22：以下保留案例分支历史。当前路演选用[下沙主案例](xiasha-real/README.md)，施工重复计权已合并，G-05/Q-05/Q-06 在下沙暂不计分；本次 `_check*.txt` 已由新口径重算。下文“G-05 均计分约为1”及“未调整规则”仅描述原始版本。

分支：`codex/demo-cases`。2026-10-14 从 `feat/regional-packs` 的 `0546bd0` 分出，保留现有规则引擎和地区册作为运行基础；此分支负责案例与只读检查工具。原分支历史和案例没有删除，两个分支可分别继续开发。

原案例提交 `dd26b71`、`75863a4`、`0546bd0` 均保留。本分支不是可脱离后端单独运行的项目：每个案例目录自带数据和检查工具，外部仍依赖 `backend/` 与 `rules/`。

| 案例 | 方案数 | 来源性质与用途 |
| --- | ---: | --- |
| [前进一期](qiantang-real/README.md) | 3 | 原真实地块案例；方案演示自拟，默认版含暂定规划条件 |
| [虚构钱塘](demo-qiantang-fictional/README.md) | 6 | 原完整虚构案例，含 What-if |
| [下沙一期](xiasha-real/README.md) | 3 | 新增；公开规模参考、规划条件缺失、同区规模对照 |
| [东湖北路](linping-donghu-real/README.md) | 3 | 新增；真实项目规模有公开披露，规划条件历史记录待复核 |
| [虚构边界](demo-boundaries-fictional/README.md) | 7 | 新增；超限排除、施工论证提示和降层恢复 |

合计 5 套、22 个方案。`mock/` 是原有回归与离线数据，不计入本案例库，未修改。

## 检查

```powershell
# 只读检查全部案例，不写数据库、不调大模型
uv run --project backend python scripts/check_case_library.py

# 保存当前引擎生成的各案例 _check*.txt 证据
uv run --project backend python scripts/check_case_library.py --write-evidence

# 单独检查或验证导入格式
uv run --project backend python scripts/check_demo_case.py --case data/schemes/xiasha-real
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/xiasha-real --dry-run
```

2026-10-14：13 次案例检查通过，覆盖默认参数、只用国标及真实地块的严格字段变体。新增三个案例的导入格式经 `--dry-run` 检查。案例内工具与仓库单案例检查工具同步；在 `<case>/tools/check_case.py` 中不传 `--case` 时会检查自己的案例目录。

程序行为断言验证下沙规划上限缺失、临平严格版缺失条件提示、边界 D 限高失败、E 容积率失败、F 施工 warning 不阻断及 D改恢复。新案例的等高体量假设下 G-05 值约为 1，无旧案例的基底异常。检查并不证明规则的专业正确性、工程合规或真实模型可用。

## 来源纪律

2026-10-14集成核对：前进严格版的容积率上限和项目设防烈度也置空。批准面积比值不能代替规划上限，区级新闻不能代替项目设防文件。下沙公开规模可在2025债券PDF第43页项目53读取；临平规模可在2024债券PDF第38页项目169读取。三地块均保留，但方案全部教学自拟，不作真实工程质量评级。线上应新增有明确来源说明的独立案例，不能用seed同名覆盖用户项目。完整操作链路优先虚构边界案例；旧前进体量与围护面积注释待专业核对。

实际建筑面积不是容积率上限。临平历史公示本次无法访问，默认版明确标为待复核；严格版不填未复核字段。新增真实项目的设防烈度没有本项目设防文件，默认版作为演示假设、严格版留空。公开债券披露只支撑记录的建设规模，方案参数全部演示自拟。

Q-05/Q-06 的保障房评分偏差、S-29 提示噪音及 MiC 覆盖缺口仍按现有边界说明；本分支不调整专业规则或凑排名。
