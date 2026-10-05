# T4：多准则决策算法与排序接口

分支：`feat/mcdm`，基于 `feat/rules-engine` 的 T3 交付。

## 做了什么

评估完成后，`POST /api/projects/{id}/rank` 使用最近的维度得分，输出 TOPSIS 名次、
敏感性表、翻转点、帕累托支配关系和名次概率。维度顺序固定为
`[quality, structure, construction, green]`。例如方案违反一条 `error` 级硬约束时，
默认从排名中排除，响应的 `excluded` 会给出规则 ID 和中文原因；
显式传 `include_noncompliant: true` 可以让它参与排名。

- `backend/app/engine/mcdm.py`：AHP、TOPSIS、敏感性、Dirichlet 名次概率、帕累托，均为纯函数。
  输入支持 NumPy 数组，结果为 Pydantic 模型；不修改输入或全局随机状态。
  各算法 docstring 写出公式、步骤和边界口径。
- `backend/app/engine/weights.py`：YAML 角色模板的读取、分数解析、矩阵校验与缓存。
  文件读取单独放在此模块，保持算法模块无 I/O。
- `rules/weights.yaml`：四角色占位矩阵，出处均为 `【示例】TODO(专业组)`。
  专业组需要核定矩阵与角色说明。直接给 `weights` 的模板也可加载，此时没有 AHP 的 CR。
- `scripts/check_rules.py`：原有 CI 步骤现在会同时校验角色模板。
  默认目录、显式目录、显式文件、`--rules-dir` 都会检查 `weights.yaml`。
  矩阵不互反属于错误，退出码 1；CR ≥ 0.1 属于警告，只有警告时退出码 0。
- `backend/app/api/rank.py`：三种权重来源必须且只能提供一项。
  没有评估结果返回 409 并提示先评估；项目不存在返回 404；
  全部方案被排除时返回 200 和空排名，并保留排除原因。
  额外提供 `GET /api/projects/{id}/rank/roles` 查询角色模板。
- 响应的 `scheme_order` 给出分析数组的方案 ID 顺序。
  `ranking` 按名次展示，敏感性、帕累托、概率矩阵的下标均对应 `scheme_order`。

## 算法口径与选择理由

1. **零权重保持 0**：Dirichlet 不能接收为 0 的参数，故只在正权重维度上以
   `alpha = weights × concentration` 抽样，再补回零维度；只有一个正权重时固定为 1。
   避免给原本不参与决策的维度添加微小权重。
2. **翻转点从 0 到 1 扫描**：按规格以 0.01 为步长，返回第一处第一名与基准不同的权重。
   因此可能返回 0；它不是距当前权重最近的切换边界。响应同时给出基准权重和翻转后的方案下标。
3. **并列名次**：采用竞赛名次，例如 `[1, 2, 2, 4]`，贴近度的并列容差为 `1e-9`。
   敏感性需要单个第一名时，取并列第一中输入下标最小者。
   名次概率统计相同口径：每行和为 1，但有并列时每列不一定和为 1。
4. **扰动边界**：目标权重超过 `[0, 1]` 时截断到端点；其余维度按原比例补足。
   当其他权重全为 0 时无原比例可循，将剩余份额均分；单准则权重始终为 1。
5. **AHP 只支持 1–10 阶**：RI 表只定义这些阶数，超过范围明确报错，不借用 10 阶 RI。
   对角线和互反检查均使用绝对误差 `1e-6`，不叠加 NumPy 默认的相对误差。
6. **帕累托按精确支配关系判断**：所有维度不低于且至少一项严格更高。
   相同方案互不支配，不用 TOPSIS 的贴近度容差放宽支配条件。
7. **排序不改写评估记录**：读取 T3 结果并返回当前权重下的排名。
   权重滑杆重复调用不会改变评估结果；`EvalResult.topsis` 仍保留原值。
8. **数据不足沿用 T3 得分**：本次没有引入缺失值填补或额外剔除规则。
   `insufficient_data` 不等于 `failed`；只有 `failed` 且 `severity=error` 默认拦排名。

名次概率是指定基准权重与集中度下的抽样频率，不表示方案客观最优的置信度。

## 如何运行

依赖使用项目技术栈中的 NumPy，显式增加 `numpy>=2.0` 并同步锁文件。
实际验证版本：Python 3.14、NumPy 2.5.3、Pydantic 2.13.5、FastAPI 0.141.1、PyYAML 6.0.3。
后端要求仍为 Python 3.11+。

```bash
cd backend
uv sync --all-extras
uv run python ../scripts/seed_mock.py
uv run uvicorn app.main:app --reload
```

在 `http://127.0.0.1:8000/docs` 中使用 seed 返回的项目 ID：

1. `POST /api/projects/{id}/evaluate`，先计算并存储维度得分。
2. `POST /api/projects/{id}/rank`，请求体选下面一种。

```json
{"role": "resident"}
```

```json
{"weights": [0.4, 0.3, 0.2, 0.1], "include_noncompliant": false}
```

```json
{"pairwise_matrix": [[1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]]}
```

默认蒙特卡洛参数：1000 次、集中度 50、种子 0。
可指定 `monte_carlo_samples`、`monte_carlo_concentration`、`seed`。
`include_whatif: true` 可纳入已评估的 what-if 副本；评估时也须使用 `?include_whatif=true`。
修改角色模板后重启后端；当前 `/api/rules/reload` 只重载规则，不重载角色模板。

## 如何测试

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff check --config pyproject.toml ../scripts/check_rules.py
uv run python ../scripts/check_rules.py
uv run python ../scripts/gen_field_table.py --check
```

前端：在 `frontend/` 下运行 `npm run typecheck` 和 `npm run build`。

2026-10-05 实测结果：

| 检查 | 结果 |
| --- | --- |
| 全部 pytest | **370 passed，2 warnings，25.79 s** |
| 新增测试 | **89 项**：数学算法、角色模板、排序接口 |
| 后端 ruff | **All checks passed!** |
| 修改的校验脚本 ruff | **All checks passed!** |
| T4 文件 ruff format --check | **8 files already formatted** |
| check_rules | **6 个文件，0 个错误，16 个警告，退出码 0** |
| 字段对照表检查 | **与 JSON Schema 同步** |
| 前端 TypeScript | **通过** |
| 前端生产构建 | **通过**，有现存包体积提醒，见遗留问题 |

测试使用数学性质，包含：

- 由已知权重构造一致矩阵，1–10 阶均还原权重且 CR ≈ 0；非法和非互反矩阵拒绝。
- TOPSIS 全面占优、方案置换、常数列、全零列、并列、效益型和成本型。
  手算 `[[3,4],[4,3]]` 配权重 `[0.75,0.25]`：列范数均为 5，
  加权后 `[[0.45,0.20],[0.60,0.15]]`，贴近度 `[0.25,0.75]`；过程写在测试注释中。
- 敏感性 delta=0 保持基准，扰动权重和为 1，其他权重保持比例，扫描返回约定的翻转点。
- 批量抽样与独立标量 TOPSIS 公式逐组结果一致；同 seed 完全复现；每行概率和为 1；
  全面占优方案第一名概率为 1；零权重、并列概率均有覆盖。
- 相同方案互不支配，列出每个被支配方案的全部支配者。
- 全部方案排除、尚未评估、三种权重输入、最新结果、what-if、响应下标映射、评估记录不被修改。

### 性能验收

`test_five_schemes_full_request_under_100ms` 对五个方案、1000 次抽样，
分别以角色、直接权重、矩阵发送完整 TestClient 请求；
计时包含数据库读取、计算、响应序列化和客户端往返，三次均断言 `< 100 ms`。

独立实测：**53.03 ms / 13.26 ms / 12.17 ms**。
首个请求也纳入断言，无预热后挑选最快值。此为当前机器测量，不构成所有部署环境的时延保证。
算法将 16 次扰动、每维 101 个扫描点、1000 次抽样分别批量计算，避免逐组调用开销。

### 权重检查输出

四个占位角色的 CR 均低于 0.1。当前 16 条警告为 12 条规则 TODO 和 4 个角色 TODO。
测试另外构造正互反但自相矛盾的矩阵，验证只警告、不报错；再破坏互反性，验证退出码 1。
输出形如：

```text
警告 weights.yaml:1 government — 角色 government 的判断自相矛盾：一致性比率 CR = 2.381，超过了 0.1 的上限 — 怎么改：回头检查倍数判断中的矛盾
错误 weights.yaml:1 government — 角色 government 的 matrix 不合法：两两比较矩阵必须互反 — 怎么改：对角线必须全是 1；如果 a[i][j] 写了 3，a[j][i] 必须写 1/3
```

## 遗留问题

- **TODO(专业组)**：四个角色矩阵和偏好说明尚待核定；CR 合格只说明内部一致，不证明专业依据充分。
  12 条规则的阈值与分段点也仍待核定。已同步到 [未决事项清单](../docs/open-items.md)。
- **评估时效与数据覆盖率**：排序使用上一次评估的得分；修改方案后应重新评估。
  T3 在维度数据不足时仍可能给出默认得分或低覆盖率得分，本任务不新增筛选阈值。
  报告应结合原评估的覆盖率说明证据范围。
- **数据库相对路径**：`make seed` 与 `make dev-backend` 的工作目录不同，可能读写两个库。
  运行示例在 `backend/` 下执行 seed，与服务工作目录一致。未在 T4 修此 T1/T6 遗留。
- **现存 lint 范围**：CI 仍只检查后端；本次额外检查修改的 `check_rules.py`。
  其他脚本的历史 lint 问题留在未决事项清单，未扩大修改范围。
- **现存警告**：pytest 有 Starlette/httpx 和 HTTP 422 常量的弃用提醒；前端构建提示
  JS 块 628.42 kB，超过默认 500 kB 提醒阈值。T4 未改前端或更换依赖。
- **角色模板重载**：角色模板在启动时缓存，修改后需重启；规则热重载接口暂不覆盖角色模板。
