# T7 离线数据层

业务入口为 `api/projects.ts`、`schemes.ts`、`evaluation.ts`、`ranking.ts`、`rules.ts`、`schema.ts` 的同名对象。只有 `VITE_USE_MOCK=true` 才动态加载本目录；真实接口使用 `/api`，可通过 `VITE_API_BASE` 修改。接口不管理 TanStack Query 缓存，页面在写入后应失效对应项目的方案、评估、排序查询。

`api/types.ts` 仅引用生成文件的顶层类型。`Project = ProjectRead`、`Scheme = SchemeRead`；排名类型对齐 T4 草案，并为离线缺失分析提供可空字段。`ApiError` 为带 `status`、`body` 的类，后端错误响应体完整保留。

## 快照来源与导出

原始方案来自 `data/schemes/mock`。当前目录包含真实规则引擎生成的评估、四个角色的排序及 286 个 10% 网格权重的完整排序分析。没有人工修改维度得分或角色矩阵。

在仓库根目录运行，使用已安装后端依赖的 Python：

```powershell
python -B scripts/export_frontend_fixtures.py --mcdm-root D:/大学/海之子 --grid-step 10
```

`--mcdm-root` 只为当前工作树尚缺的 T4 模块提供只读搜索路径，不复制后端代码。公共模型、字段元数据和评估来自当前工作树。计算使用内存 SQLite，不访问应用数据库；禁止生成 Python 字节码。输出只写入 `frontend/src/mocks/fixtures`。`data.json` 记录源码及数据哈希；Excel 时间戳固定，便于稳定识别文件。

`--grid-step 0` 可关闭网格；其他值必须整除 100 且不小于 5。浏览器只匹配当前归一化权重，不选择邻近网格或插值，浮点比较容差为 `1e-12`。

## 界面状态

`evaluation`、`ranking`、`rules` 和导入结果可附带 `demo`：

- `mode`：`engine-fixture`、`custom-topsis`、`unsupported`、`offline-crud`。
- `disclaimer`：虚构数据与离线引擎来源说明。
- `fixture_id`：快照版本标识。
- `unavailable`：当前未提供的分析字段名。
- `warnings`：本次操作需要显示的中文提示。

自定义权重未精确命中快照时，仅使用原始引擎维度分重算 TOPSIS，`sensitivity`、`rank_acceptability`、所有 `first_place_probability` 都为 `null`。帕累托结果与权重无关，可以保留。不能把空概率显示成 0，不能把角色快照的敏感性或概率显示为当前自定义权重的结果。

`participant_ids` 是 TOPSIS、敏感性、概率和帕累托下标对应的方案顺序，不是排序后的 `ranking` 顺序。复制或导入到其他项目时所有方案编号、名称与支配关系都会重新映射。

当前真实数据下四角色的名次均为 C、D、E、A，贴近度不同；这是当前引擎的实际输出。权重 `[1,0,0,0]` 的真实网格快照会把 E 排到第一，可以用于验证自定义权重翻转。

## 独立项目流程与限制

新建空项目 → 导入 `demo-import.xlsx` → 评估 → 排序可独立完成。也可以使用原项目参数，在新项目逐条创建五个与原样例参数相同的方案后运行。名称可修改，编号不必与原样例相同。

项目与方案保存到 `localStorage`，键为 `zhuheng:t7:mock:v1`。每次方案写入、导入都会清除所属项目的评估，其他项目不受影响。未评估或已失效时 `evaluation.get` 返回空 `results`；有参数变化、缺少或多出方案时，`evaluation.run` 抛出 409，错误码 `MOCK_EVALUATION_UNSUPPORTED`，不会用旧分数冒充新结果。必须连接后端才能评估任意输入。

Excel 离线导入按内容 SHA-256 识别已知文件，使用导出时真实解析器的结果；文件可改名，不能修改内容。`demo-invalid.xlsx` 包含层高与层数错误，返回完整错误列表并拒绝整次导入。未知工作簿返回 `MOCK_IMPORT_UNSUPPORTED`；真实模式通过 multipart 的 `file` 字段上传到 `/projects/{id}/schemes/import`。

`components/MockControls.tsx` 默认导出离线工具栏，提供正确／错误 Excel 下载和恢复样例按钮。恢复会重建本地样例、清空评估并刷新页面；刷新同时移除内存查询缓存。组件由 App 接入，仅在 mock 模式显示。

## 验证

在 `frontend` 目录运行：

```powershell
node --test src/mocks/data-layer.test.mjs
npm run typecheck
```

测试涵盖独立新项目流程、CRUD 持久化及隔离、完整导入错误、评估失效、角色／网格精确匹配、自定义分析空值、真实请求契约，以及浏览器 TOPSIS 与全部 286 个引擎网格快照的一致性。另验证缩放、置换、支配、并列、全零与单方案性质。

导出器检查在仓库根目录运行：

```powershell
ruff check --config backend/pyproject.toml scripts/export_frontend_fixtures.py
ruff format --check --config backend/pyproject.toml scripts/export_frontend_fixtures.py
```
