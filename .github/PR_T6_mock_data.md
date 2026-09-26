# PR：T6 虚构开发数据

## 做了什么

按任务 T6 要求，给引擎 / 前端 / 演示调试生成 1 个项目 + 5 套住宅方案 + 1 个 what-if 对照，
**所有数据都是虚构的，仅用于开发调试，不得用于验证或答辩**。

### `data/schemes/mock/` —— 1 + 5 + 1 份 JSON

每个 JSON 顶层都带 `_note: "虚构数据，仅供开发调试，不得用于验证或答辩"`，并在
`params` 之外用 `_design_notes` 写明设计意图，方便后续维护。命名约定：
`{代号}_{设计意图}.json`。

| 文件 | 方案 | 定位 | 关键差异点 |
| --- | --- | --- | --- |
| `project.json` | — | 杭州钱塘 · 保障性租赁住房 · 虚构示例项目 | 用地 18,000 m²，容积率 2.5，密度 0.28，限高 54 m，夏热冬冷 |
| `A_高品质.json` | A | 高品质住宅 | 现浇剪力墙；层高 3.3 m、得房率 0.82、南向比例 0.85；标准层重复率仅 0.65、构件种类 20、装配率 0.25；带"大悬挑 / 高支模"风险特征 |
| `B_不合规.json` | B | 压低层高抢面积（**故意违规**） | 层高 **2.9 m** 触发 C-03 类硬约束失败（< 3.0 m），其余指标中等 |
| `C_MiC高标准化.json` | C | MiC 工业化路线 | MiC；标准层重复率 0.95、构件种类仅 8、装配率 0.75；几乎无风险特征 |
| `D_均衡.json` | D | 基准（中庸偏上） | 框架-剪力墙；四个维度均衡中上；和 E 配对演示帕累托筛选 |
| `E_被支配.json` | E | 构造性反例 | 框架（弱于 D 的框架-剪力墙）；得房率 / 南向比例 / 标准层重复率 / 装配率 / 电梯数均 **低于** D，构件种类 **高于** D，并带"大悬挑 + 复杂地质"风险特征 |
| `C_现浇.json` | C → what-if | 把 C 改成现浇剪力墙的对照 | 体量与户数与 C 一致；结构 / 装配率 / 标准化类指标全部下降；用于"改用 MiC 会怎样"演示 |

数值内部自洽：`footprint × floors × buildings == gfa`（允许 ±0），
所有方案满足项目容积率 2.5 / 限高 54 m（除 B 是故意违反层高下限）。

### `scripts/seed_mock.py` —— 把 JSON 写进数据库

- 每次执行都是「清空 + 导入」：若数据库里已有同名项目（`杭州钱塘 · 保障性租赁住房 · 虚构示例项目`），
  先连同其下所有方案与评估结果一起删掉，再写入新数据；**其它项目不受影响**。
- `C 现浇` 以 `is_whatif=True`、`parent_id=4`（指向 "C MiC 高标准化"）写入，
  默认列表不返回，需 `?include_whatif=true` 才能看到。
- `--dry-run` 只读 + 校验 JSON，不写数据库，便于 CI 提前发现问题。
- 每个 JSON 都会用 `SchemeParams.model_validate(...)` 重新校验，校验不过直接退出并打印定位信息。

### `Makefile` —— `make seed` 一条命令

```diff
 seed:
-	uv run python scripts/seed_mock.py
+	uv run --project backend python scripts/seed_mock.py
```

`help` 列表也同步加上 `make seed` 一行。

### `backend/tests/test_mock_data.py` —— 15 项新增测试

- 所有 JSON 文件存在且顶层带 `_note` 虚构声明（"虚构数据" 前缀 + "不得用于验证" 字样）；
- `project.json` 通过 `ProjectParams` 校验；6 套方案（含 what-if）均通过 `SchemeParams` 校验
  —— **这是任务验收标准里"必须通过 T2 模型校验"的硬约束**；
- `B` 层高 2.9 m 故意低于 3.0 m；
- `E` 在每个数值字段上都朝"更差"方向偏离 `D`（内面积比 / 南向比例 / 窗地比 / 窗墙比 /
  标准层重复率 / 装配率 / 电梯数全部更低，构件种类更多，结构更弱，风险特征非空）；
- `C 现浇` 与 `C MiC 高标准化` 的体量 / 户数 / 层数 / 楼栋数完全一致，
  仅结构 / 装配率 / 标准化类指标变化；
- `scripts/seed_mock.py` 的常量与目录对得上；`loaders` 在默认目录可用；
- `--dry-run` 不写数据库且对残缺 JSON 早失败。

## 如何运行

```bash
make seed                                       # 从 data/schemes/mock/ 导入（Makefile 推荐）
uv run --project backend python scripts/seed_mock.py --dry-run   # 只校验不写库
```

写入后再用既有接口查看：

```bash
make dev-backend                                # 端口 8000
curl http://127.0.0.1:8000/api/projects        # 找到 mock 项目 id
curl http://127.0.0.1:8000/api/projects/<id>/schemes
# 返回 5 套方案（默认不含 what-if）
curl 'http://127.0.0.1:8000/api/projects/<id>/schemes?include_whatif=true'
# 返回 6 条（含 C 现浇，is_whatif=true，parent_id 指向 C）
```

打开 http://127.0.0.1:8000/docs 可以直接点开看每个字段的中文 description / unit / group。

## 如何测试

```bash
make test         # = cd backend && uv run pytest
make lint         # ruff check . + scripts/seed_mock.py
```

### 实测结果（本机）

```
$ uv run ruff check .
All checks passed!

$ uv run ruff check ../scripts/seed_mock.py
All checks passed!

$ uv run pytest
tests/test_db_crud.py ............                                       [ 14%]
tests/test_excel_parser.py ............                                  [ 28%]
tests/test_excel_scripts.py .......                                      [ 37%]
tests/test_excel_template.py ........                                    [ 46%]
tests/test_health.py .                                                   [ 48%]
tests/test_import_endpoint.py ......                                     [ 55%]
tests/test_mock_data.py ...............                                  [ 73%]   <-- 新增 15 项
tests/test_models_params.py ..................                           [ 95%]
tests/test_schema_endpoint.py ....                                       [100%]
======================= 83 passed, 2 warnings in 2.32s ========================
```

### API 验证（uvicorn :8765 临时起进程）

```
$ curl http://127.0.0.1:8765/api/projects
[{"id":1,"name":"test",...},
 {"id":2,"name":"杭州钱塘 · 保障性租赁住房 · 虚构示例项目",
  "params":{"site_area":18000,"far_max":2.5,"density_max":0.28,
            "height_max":54,"climate_zone":"夏热冬冷"}}]

$ curl http://127.0.0.1:8765/api/projects/2/schemes
# 5 条方案（A / B / C / D / E），全部 is_whatif=false

$ curl 'http://127.0.0.1:8765/api/projects/2/schemes?include_whatif=true'
# 6 条，末尾追加 {"id":7,"name":"C 现浇","is_whatif":true,"parent_id":4,...}
```

## 字段取值说明

`A_高品质.json` 等具体数值的依据：

- 项目用地 1.8 ha、保障房常见容积率 2.5 / 密度 0.28 / 限高 54 m，留出 0.2~0.3 余量；
- `footprint × floors × buildings = gfa`：5 套方案都用 4 栋 × 600 m² 基底 × 不同层数，
  把 gfa 与体量锁住；
- 层高 × 层数 ≤ 54 m；`A` 因层高 3.3 m 降到 16 层（总高 52.8 m）；
- B 故意 `floor_height: 2.9` 触发硬约束违规（验收要演示的"硬约束标红"）；
- C 用 MiC 路线，所有指标向"高标准化"集中；
- D 取中位数水平；E 在每个数值字段都朝"更差"方向微调 D（构造性反例）。

## 遗留问题

1. **没跑 evaluate / rank 验证**：任务说"如果 T3/T4 已合并：跑一遍 evaluate 和 rank，
   确认 B 被标红、E 被 D 支配"。当前仓库 `feat/excel-import` 分支未合入 T3/T4，
   本分支也无法本地验证这两条。本次仅在 `tests/test_mock_data.py` 里写了
   静态约束（B 层高 < 3.0；E 各维度字段均劣于 D；C 现浇 vs C MiC 的差异仅在指定字段），
   引擎跑通后请按 PR 描述里的"如何测试"再补一遍 evaluate / rank 的输出。
2. **`C 现浇` 的 what-if 元信息由 `seed_mock.py` 写入**：JSON 里没有 `is_whatif` /
   `parent_id` 字段，因为这两个是 SQLModel 表顶层列，不在 `SchemeParams` 内。
   `seed_mock.py` 硬编码 `WHATIF_PARENT_NAME = "C MiC 高标准化"`，新增 what-if 时
   记得同步修改这个常量，并在 `README.md` 的表格里追加一行。
3. **5 套方案都按 4 栋 / 600 m² 基底构造**，体量差异主要来自层数和层高；如果后续
   想做"基底形态（塔楼 vs 板楼）"的演示，需要加新方案。
4. **Mock 项目名硬编码在 `scripts/seed_mock.py` 的 `DEFAULT_PROJECT_NAME`**：
   `seed` 命令会清空与之同名的项目，所以**不要把真实项目也起这个名字**。
   重命名 mock 项目名时记得同步改这个常量。
5. **`scripts/seed_mock.py` 在仓库根目录跑需要 `uv run --project backend`**：
   Makefile 已经处理，但脚本 docstring 里的手工调用样例也写明了，避免在
   根目录默认 venv（无 backend 依赖）下 `ModuleNotFoundError`。
6. **CI 未跑**：本机已确认 `uv run ruff check .` 与 `uv run pytest` 都通过；
   GitHub Actions 跑前还需把 `feat/mock-data` 推到 `origin/feat/mock-data` 才能
   触发 workflow（`.github/workflows/*.yml` 只在 `feat/**` push 时跑）。