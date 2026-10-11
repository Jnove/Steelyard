# T1–T9 集成记录

> 2026-10-05 历史验收记录。当前使用说明见 [文档入口](../README.md)。

2026-10-05。任务范围为合并已经完成的 T1–T9，协调接口与运行问题；T10 尚未开始。

## 分支关系与合并方式

远端 `main` 已包含 T1、T2、T5、T6、T9（含历史 PR #1 / #2）。T3 的规则引擎是 T4、T7、T8 的共同基础；T8 基于 T4，T7 从规则引擎分出。

集成分支 `codex/integrate-t1-t9` 从最新 `origin/main` 建立，先合入 `feat/agents`，保留 T3 / T4 / T8 的提交，再合入 `feat/frontend-mvp`。原 T8 PR [#3](https://github.com/Jnove/Steelyard/pull/3) 的目标为 `feat/mcdm`，先完成该 PR，再让集成分支包含它的合并记录。最后将完整集成 PR 合入 `main`，不改写原分支历史。

原来的主工作树、前端工作树、智能体工作树及各自数据库保留；本次所有安装、播种和联调在独立 Codex 工作树中完成。

## 接口与运行修复

- 保留 T7 页面与离线模式，接入 T8 实际 SSE 协议。两个流入口共享增量解析器；处理工具事件、草稿替换、最终正文、缓存与数字校验。
- 最终数字标红只使用 `done` 的位置，按 Unicode 码点对应 Python 偏移。未核实文本转义显示，避免把草稿偏移或 HTML 当成最终内容。
- 真实流直接更新内容，移除模拟逐字延迟造成的长时间页面阻塞。离线演示继续保留动画。
- 对话携带已完成的历史消息；What-if 由用户填写标准层重复率，通过后端创建副本，原方案不变。工具计算结果失效相关查询缓存；副本或其他权重的工具排序不写入政府正式方案的缓存。
- 排序、敏感性、概率与帕累托统一按后端 `scheme_order` 映射。前端类型从排序和智能体 Pydantic 模型生成，移除临时排序协议。
- 默认数据库定位到本工作树 `backend/data/zhuheng.db` 的绝对路径，根目录与后端目录启动使用同一配置；显式 `DATABASE_URL` 仍可覆盖。
- 容器保留 `/app/backend/app` 目录层级，使规则加载器读取 `/app/rules`；Compose 数据库显式指向持久化卷 `/app/data/zhuheng.db`。前后端依赖安装遵循锁文件。
- Makefile / CI 纳入前端测试、脚本 Ruff 与生成文件一致性检查。README 与前端文档对齐实际任务编号、启动方法及接口。

没有修改规则阈值、角色矩阵、专业出处或数值算法。示例数据与 `TODO(专业组)` 保留。

## 验证与证据

| 检查 | 结果 |
| --- | --- |
| 后端完整 pytest | 443 通过，1 条 HTTP 状态常量弃用警告；[日志](../evidence/integration-pytest.txt) |
| 前端单元、离线数据与流协议测试 | 49 通过，0 失败 |
| TypeScript / 真实模式与离线模式构建 | 通过；已有的大包体积提示保留 |
| 后端与 scripts/ Ruff；修改的 Python 文件格式 | 通过 |
| 规则与字段对照表 | 0 错误、16 条专业 TODO 提醒；字段表无漂移 |
| T7 完整离线浏览器流程 | 通过：CRUD、Excel 成功 / 错误、评估、角色、权重、溯源、对话、下载、响应式布局 |
| 真实 REST / SSE + FakeLLM 浏览器流程 | 通过；[验收记录](../evidence/integration-ui.json)、[完整报告事件流](../evidence/integration-report.sse.txt) |

真实浏览器流程使用新建的虚构数据库：五个正式方案评估后四个进入排名，不合规方案单列；核对敏感性索引、权重翻转、报告下载与缓存、历史追问、What-if 副本。取消和校验耗尽通过受控延迟 / SSE 响应验证，另有后端生命周期测试。浏览器没有页面运行时异常。

本次未配置真实模型 Key，也没有可用的 Docker 命令；因此未验证真实模型输出与容器启动。条文搜索仍为 T10 的空结果桩。当前专业示例不能作为工程或答辩验证依据。

## 复跑

在仓库根目录准备依赖后运行：

```powershell
uv sync --project backend --all-extras --frozen
npm --prefix frontend ci
uv run --project backend pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run build:mock
uv run --project backend ruff check --config backend/pyproject.toml backend scripts
uv run --project backend python scripts/check_rules.py
uv run --project backend python scripts/gen_field_table.py --check
uv run --project backend python scripts/export_schema.py
npm --prefix frontend run gen:types
```

浏览器验收会创建副本，应只对新建虚构数据库运行。在根目录新终端中：

```powershell
# 先确认这个数据库是本次测试专用；seed 会清空其中的数据
$integrationDb = Join-Path (Get-Location) 'backend/data/integration-demo.db'
$env:DATABASE_URL = 'sqlite:///' + $integrationDb.Replace('\', '/')
$env:LLM_PROVIDER = 'fake'
uv run --project backend python scripts/seed_mock.py
uv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011
```

另一个终端设置 `$env:VITE_BACKEND_URL='http://127.0.0.1:8011'`，运行 `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5178`。第三个终端运行 `npm --prefix frontend run test:integration`。该脚本使用独立 Chrome 上下文，截图和下载位于忽略的 `backend/data/integration-ui/`，文本证据写入 `docs/evidence/`。

离线验收运行 `npm --prefix frontend run dev:mock -- --host 127.0.0.1 --port 5179`，另设 `$env:T7_URL='http://127.0.0.1:5179'`、`$env:T7_OUTPUT=(Join-Path (Get-Location) 'backend/data/mock-ui')`，执行 `npm --prefix frontend run test:ui`，避免覆盖历史交付截图。
