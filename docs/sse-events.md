# T8 报告与对话事件协议

`POST /api/projects/{id}/report` 与 `POST /api/projects/{id}/chat` 返回 `text/event-stream`，使用 UTF-8。POST 需要 `fetch` + `ReadableStream`，浏览器原生 `EventSource` 不支持带请求体的 POST。服务器约每 15 s 发送一次注释心跳，前端忽略心跳。

## 请求

报告可发送 `{}`；无角色与权重时明确采用等权演示，不代表任何专业立场。

```json
{"role":"resident","include_whatif":false}
```

对话支持 user/assistant 历史，拒绝客户端提供 system/tool 消息。比例为 0–1 小数，长度 m，面积 m²。自然语言参数由模型解析，结构化参数优先；缺失修改字段或权重时返回错误，不猜测。

```json
{
  "message": "假设降低标准层重复率，解释与原方案的差异",
  "history": [{"role":"user","content":"刚才的方案比选"}],
  "intent": "whatif",
  "change": {"scheme_id":3,"field":"std_floor_repeat","value":0.6},
  "weights": [0.25,0.25,0.25,0.25]
}
```

`intent` 可选 `new_eval / whatif / explain / reweight`。解释可提供 `rule_id`。改权重需要 `role` 或 `weights` 之一，例如 `{"intent":"reweight","weights":[0.1,0.2,0.3,0.4]}`。改权重只运行 rank；最近一次评估过期、缺失或候选集合不完整时提示重新评估，不自动重跑 evaluate。`report` 只接受 new_eval，其他意图使用 chat。

## 事件

每帧采用标准 SSE 格式：

```text
event: node_start
data: {"node":"coordinator","attempt":0}

```

| event | data | 处理方式 |
| --- | --- | --- |
| node_start | `node, attempt` | 展示正在执行的节点；四个 `evaluators_*` 可交错出现 |
| tool_call | `node, tool, arguments` | 工具名称与校验前的请求参数；随后工具会严格校验 |
| tool_result | `node, tool, result` | 确定性结果或有出处的规则；数值来源 |
| token | `node, attempt, text, replace` | `replace=true` 时清空旧正文并用 text 替换，其他情况追加 |
| citation_warning | `attempt, exhausted, unverified_numbers` | 当前草稿存在无法溯源数字；exhausted 表示两次重写已经耗尽 |
| done | `report, intent, unverified_numbers, traces, cached` | 唯一权威的最终报告；必须整体替换草稿，然后按最终位置标红 |
| error | `message` | 终止本次请求并展示中文错误；不会再发 done |

token 为未校验草稿；工具调用前的过渡文字和引用重写都可能触发替换。`attempt=0` 为初稿，之后为两次重写。不要把多次草稿拼接。引用校验失败重写成功后，最终 `unverified_numbers=[]`；重写仍失败时，done 包含最终正文及问题位置。

```json
{"attempt":2,"exhausted":true,"unverified_numbers":[{"text":"998.23","start":3,"end":9}]}
```

位置是 Python 字符索引，`start` 包含、`end` 不包含；JavaScript 按 `Array.from(report)` 切片，避免 emoji 的 UTF-16 长度差异。正文按纯文本渲染，不把模型输出作为可信 HTML。当前对话页已经实现替换、错误、取消和标红。

done 的 traces 含每个节点的 `node, elapsed_ms, tool_calls`；具体调用参数与返回值在前面的工具事件中。并行评语的完成顺序不固定。连接断开会取消图执行并关闭模型客户端；已经提交的 what-if 副本保留在数据库中。

## 缓存与离线

标准 `/report` 请求的报告缓存在 SQLite 中，进程重启后仍可读取。缓存键包含项目/正式或副本方案的实际内容、规则定义、归一化权重及其角色来源、角色模板、模型提供方/模型名称、提示词与协议版本。数据、规则、权重或提示词改变则失效。自定义消息、历史、规则解释与 `/chat` 不复用标准报告缓存。只缓存数字校验通过的报告。

缓存命中仅发送一次 `token(replace=true)` 和 `done(cached=true)`，无需构造模型客户端或联网；traces 是缓存报告生成时的历史耗时。标准报告生成期间数据变更会返回 error，避免将旧报告标记为当前结果。未命中过缓存的 openai 请求失败会返回 error；不会切换 FakeLLM。REST `/evaluate` 与 `/rank` 也同步最近一次结果，重新评估会清空旧排名。

删除项目会在同一事务中删除其全部报告缓存、智能体工具结果、评估、正式方案与 What-if 副本。
其他项目的结果与缓存保留。

## 联调

在仓库根目录统一数据库路径，避免 seed 与后端 CWD 不同而连接不同数据库：

```powershell
$env:LLM_PROVIDER='fake'
# 只对本次联调的新建数据库运行；seed 会清空该数据库
$sseDemoDb = Join-Path (Get-Location) 'backend/data/sse-demo.db'
$env:DATABASE_URL='sqlite:///' + $sseDemoDb.Replace('\', '/')
uv sync --project backend --all-extras --frozen
uv run --project backend python scripts/seed_mock.py
uv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8008
```

另开终端；id 以 seed 输出为准：

```powershell
curl.exe -N -X POST http://127.0.0.1:8008/api/projects/1/report -H "Content-Type: application/json" --data-binary '{}'
```

真实模型配置是 `LLM_PROVIDER=openai`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。OpenAI SDK 请求超时 60 s、失败重试两次；客户端配置与接口用本地 HTTP 假响应测试。不得将密钥写入报告、事件或提交。

数字校验支持结果原值、四舍五入到 0–2 位、比例/百分数换算、实际规则中的常数及编号、方案数、四维度和明确写作年份的白名单。它检查数字是否有出处，不能证明叙述因果或规则条文含义。T10 检索桩当前返回空列表；规则中的专业占位仍需 TODO(专业组) 确认。
