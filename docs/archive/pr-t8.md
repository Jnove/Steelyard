# T8：智能体图、报告对话与引用校验

> 2026-10-05 PR 描述归档，含当时的环境路径与验收结果。当前协议见 [SSE 协议](../sse-events.md)，运行方法见 [仓库 README](../../README.md)。

基于 `feat/mcdm` 的 `a958830`，分支为 `feat/agents`。根目录实际指引是 `Agent.md`，已完整阅读并按其技术栈、目录与智能体图实现。本 PR 不修改规则、专业阈值、行业因子或 T3/T4 算法。

## 做了什么

- 通过 LangGraph 串起协调、解析、合规、四维并行评语、决策、报告与引用校验。Pydantic 定义状态，记录每个节点耗时及工具调用，支持 new_eval / whatif / explain / reweight。
- 实现统一异步 chat/stream 客户端。OpenAI 兼容接口从配置读取 base_url/model，SDK 超时 60 s、重试两次；FakeLLM 支持预设文本/工具调用和离线脚本。网络故障返回 error，不自动切换假模型。
- 工具复用 T3 evaluate 与 T4 rank，不交给模型计算专业数值。What-if 校验字段、比例、嵌套值和项目归属后创建副本，保留原方案；报告对比指标原值/新值、评分、修改前排名和加入副本后的排名，区分候选集合变化与指标变化。
- reweight 仅重新 rank 后进入 reporter，不重跑 evaluate；解释读取最新结果与真实规则定义。普通 REST `/evaluate`、`/rank` 也同步最新证据，避免追问读取旧权重；T4 的原有完整请求耗时测试仍通过。
- 数字校验覆盖整数、小数、负数、千位分隔、科学记数与百分数；支持原值及 0–2 位舍入、比例转换、实际规则常数/编号和任务规定白名单。失败重写最多两次，仍失败返回 unverified_numbers 的最终位置。
- 新增 POST report/chat 的 sse-starlette 流，事件为 node_start / tool_call / tool_result / token / citation_warning / done / error。报告重写会替换草稿，断流会取消图并关闭模型客户端。协议见 [docs/sse-events.md](../sse-events.md)。
- 标准报告缓存持久化到 SQLite，键覆盖项目数据、候选集合、规则、归一化权重及角色来源、角色模板、模型标识、提示词与版本；缓存命中无需构造模型客户端。失败报告不入缓存。
- 基线对话页接入 POST SSE、历史消息、错误与取消；最终未核实数字标红。前端继续使用 TypeScript 严格模式，模型正文按纯文本渲染。

新增直接依赖只有 `langgraph`、`openai`、`sse-starlette`：前两项属于 Agent.md 技术栈，后一项是 T8 指定的 SSE 实现。前端测试使用现有 TypeScript 与 Node 内置测试，没有新增测试依赖。

## 如何运行

Windows / PowerShell，从仓库根目录执行；DATABASE_URL 请按实际 checkout 的绝对路径调整，seed 与服务必须使用同一数据库。

```powershell
$env:PYTHONUTF8='1'
$env:LLM_PROVIDER='fake'
$env:DATABASE_URL='sqlite:///D:/大学/海之子/.worktrees/agents/backend/data/t8-demo.db'
uv sync --project backend --all-extras
uv run --project backend python scripts/seed_mock.py
Set-Location backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8008
```

seed 实际输出项目 id=1，正式方案 id=1–5，已有 what-if id=6（parent_id=3）。数据均来自 T6，并明确标注虚构；不得用作工程验证。另开终端调用：

```powershell
curl.exe -N -X POST http://127.0.0.1:8008/api/projects/1/report -H 'Content-Type: application/json' --data-binary '{}'
```

前端：在 `frontend` 执行 `npm ci`、`npm run dev`，打开项目对话页。默认后端 Vite 代理端口为 8000，若使用本次验收端口 8008，请将服务改用 8000 或按实际环境配置代理；前端接口始终使用 `/api`。

真实模型需要 `LLM_PROVIDER=openai`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。本次环境实际为 fake，密钥与模型配置均未设置，因此没有真实模型报告样例；SDK 兼容性通过本地 HTTP 假响应验证。

## 如何测试

```powershell
Set-Location backend
uv run pytest
uv run ruff check .
uv run ruff format --check app/agents app/api/agents.py app/api/evaluate.py app/api/rank.py app/main.py app/db.py tests/agents
Set-Location ../frontend
npm test
npm run typecheck
npm run build
```

2026-10-05 本地实际结果，Python 3.14.4（满足 3.11+）：

| 检查 | 结果 |
| --- | --- |
| 全部 pytest（未跳过、未删除测试） | **427 passed, 1 warning in 31.26s** |
| T8 后端新增用例 | 57 项，覆盖五项验收场景及并行、项目隔离、字段值、历史、工具调用、缓存、断流、REST 最新结果 |
| 后端全目录 Ruff check | **All checks passed!** |
| 本 PR 改动 Python 文件 format --check | **29 files already formatted** |
| 前端 SSE 单字节 UTF-8/CRLF 分块、提前断流、错误/HTTP 测试 | **3 passed** |
| TypeScript 严格类型检查 | **通过** |
| Vite 生产构建 | **通过**（现有包体积告警，见遗留问题） |
| Git diff --check | **通过** |

所有智能体验收使用 FakeLLM，包括新评估全链路、What-if 原方案内容不变、改权重跳过评估、引用失败重写成功、连续失败后标记。API 缓存测试会将模型工厂替换为不可用状态，验证断网时仍返回已验证的缓存。SDK 测试使用 httpx.MockTransport，不调用真实模型。[完整 pytest 输出](../evidence/t8-pytest.txt)。

### curl 实际输出

首次 `/report` 得到 **80 帧**：11 个 node_start、3 个 tool_call、3 个 tool_result、62 个 token、1 个 done；最终 cached=false、unverified_numbers=[]。四维评语完成顺序可交错。

以下帧摘自原始输出，省略中间的完整工具 JSON 与 token；[完整事件流](../evidence/t8-report.sse.txt)已保存。

```text
event: node_start
data: {"node": "coordinator", "attempt": 0}

event: node_start
data: {"node": "parser", "attempt": 0}

event: node_start
data: {"node": "compliance", "attempt": 0}

event: tool_call
data: {"node": "compliance", "tool": "evaluate", "arguments": {"project_id": 1, "include_whatif": false}}

event: tool_call
data: {"node": "compliance", "tool": "search_clause", "arguments": {"query": "生成方案比选报告", "k": 5}}

event: tool_result
data: {"node": "compliance", "tool": "search_clause", "result": []}

event: token
data: {"node": "reporter", "attempt": 0, "text": "", "replace": true}
```

最终报告摘录（仅复述 T3/T4 示例结果，不代表真实工程结论）：

```text
## 结论
离线脚本演示；虚构样例不能用作工程依据。
C MiC 高标准化：名次 1，贴近度 0.98。
D 均衡：名次 2，贴近度 0.71。
E 被支配：名次 3，贴近度 0.34。
A 高品质：名次 4，贴近度 0.00。

## 合规问题
B 不合规：C-01，层高 2.9 m 低于示例阈值 3.0 m；source：TODO(专业组)：示例数值，正式条文号待补。
```

[完整 FakeLLM 报告](../evidence/t8-fake-report.md)含全部固定章节与规则 source。再次调用得到 token + done，cached=true，且正文与首次报告一致：[缓存命中事件流](../evidence/t8-report-cache.sse.txt)。

## 遗留问题

- **TODO(专业组)**：现有规则的正式条文、编号、阈值与评分依据仍为示例占位；角色权重也需专业组确认。本 PR 沿用原规则，不补造工程数据。
- **T10**：search_clause 仍为空列表桩，不能宣称已检索到真实规范条文。
- 数字校验证明数值出现在工具证据中，不能证明叙述因果或条文含义；专业结论仍需结合完整规则 source 复核。
- 数据库缓存目前没有自动淘汰策略；高并发、多进程部署时还需独立设计评估版本与一致性。本次验证是 SQLite 演示规模。
- 基线前端依赖安装报告 **5 项审计告警（4 moderate、1 high）**；Vite 现有大包仍超过 500 kB 告警。本 PR 不升级无关依赖或进行打包重构。
- 现有导入接口使用已弃用的 HTTP_422_UNPROCESSABLE_ENTITY，导致 pytest 的 1 条 warning；未在 T8 中改动。
- 基线部分未改动 Python 文件存在 Ruff 格式差异；全部 lint 检查与本 PR 改动文件的格式检查通过，未对无关文件作全仓重排。
- 根指引名为 Agent.md，尚未统一为 AGENTS.md；另一个 T7 前端分支未在本 PR 中合并，其页面应按本 PR 的 SSE 协议对接。
