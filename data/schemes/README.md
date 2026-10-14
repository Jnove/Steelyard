# 演示数据与案例库

案例专用分支为 `codex/demo-cases`。现已增加下沙一期、临平东湖北路与虚构边界案例，连同原两套演示案例共 **5 套、22 个方案**。完整入口、来源边界和批量检查见 [案例库说明](CASE_BRANCH.md)。下文保留原三条数据线说明。

原三条数据线**用途不同、来源性质不同、互不依赖，不要混用**：

| 目录 | 地块来源 | 方案来源 | 用途 | 能否对外当「真实项目」 | 可独立带走 |
| --- | --- | --- | --- | --- | --- |
| [`mock/`](mock/README.md) | 虚构 | 虚构 | T6 回归测试、前端离线快照、`make seed` 默认样例 | 否 | 否（被测试与快照依赖） |
| [`demo-qiantang-fictional/`](demo-qiantang-fictional/README.md) | 虚构 | 虚构 | 需要 6 套方案 + 支配关系 + What-if 的完整演示 | 否 | 否（用仓库脚本检查） |
| [`qiantang-real/`](qiantang-real/README.md) | **真实**（钱塘区前进公租房一期，有公开出处） | 演示自拟 | 需要「真实项目」时用它；项目层来自政府公开信息 | 部分（项目层可，方案层不可） | **是**（自带数据与工具） |

**选型一句话**：三个真实背景案例均有公开来源线索，方案全部教学自拟；优先使用 `project_verified.json` 的缺失版，并标明前进部分历史记录待复核。完整超限与恢复故事优先 `demo-boundaries-fictional/`；原虚构钱塘数据另保留用于历史对照。
两套可以一起用——主案例用真实地块，录视频时用虚构案例展示更多方案。`mock/` 被测试与
前端快照依赖，**不要改动**。

## 本地对比案例：qiantang-real/（要求与其他内容相互独立）

这个目录是**自包含**的，符合「本地案例、与仓库其它内容相互独立」的要求：

- **数据自足**：项目层 2 个版本（默认 / 仅公开数据）、3 套方案、3 份证据文件都在目录内。
- **工具自带**：[`qiantang-real/tools/check_case.py`](qiantang-real/tools/check_case.py)
  与 [`tools/README.md`](qiantang-real/tools/README.md)；工具会自己向上查找后端目录，
  整包拷走后换个位置也能跑。
- **只读且无副作用**：不写数据库、不调大模型、不改规则、不碰 `mock/` 与前端快照；
  `make test` / `make docs-check` / 前端离线演示都不依赖它。
- **双向独立**：改这个目录不会影响其它内容；改仓库其它内容（除 `backend/` 与 `rules/`）
  也不影响它。

```powershell
# 在案例目录内直接跑（工具默认检查自己所在的案例）
cd data/schemes/qiantang-real
uv run --project ..\..\..\backend python tools\check_case.py
uv run --project ..\..\..\backend python tools\check_case.py --params project_verified.json
```

需要**多个真实项目横向对比**时，可直接使用 [下沙一期](xiasha-real/README.md) 与
[临平东湖北路](linping-donghu-real/README.md)。两个目录均带检查工具，方案层明确为演示自拟。
更多候选来源见 [演示案例候选清单](../../docs/demo-candidates.md)。

## 通用命令（仓库内使用）

```bash
# 只读检查任意一个案例：硬约束 + 四维得分 + 帕累托 + 角色排名
uv run --project backend python scripts/check_demo_case.py --case data/schemes/qiantang-real
make case-check CASE=data/schemes/demo-qiantang-fictional

# 导入本地 Demo 库（会先删掉同名项目再写入）
uv run --project backend python scripts/seed_mock.py --mock-dir data/schemes/qiantang-real
```

`check_demo_case.py` 与案例内的 `tools/check_case.py` 是**同一份脚本**（改一处要同步
另一处）；案例目录里的 `_check*.txt` 是它生成的**证据文件**，不要手改。
