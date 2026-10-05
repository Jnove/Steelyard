# T7 前端 MVP 使用与联调

T7 最初在 `feat/frontend-mvp` 上基于规则引擎开发。2026-10-05 的 T1–T9 集成已接入 T4 排序与 T8 智能体；原分支截图保留为历史素材，当前联调结果见 [集成记录](integration-t1-t9.md)。

## 启动

需要 Node.js 与 npm；依赖版本以 `frontend/package-lock.json` 为准。

```powershell
cd frontend
npm ci
npm run dev:mock -- --host 127.0.0.1 --port 5177
```

访问 `http://127.0.0.1:5177/projects`。`dev:mock` 通过 `.env.mock` 设置 `VITE_USE_MOCK=true`；默认 `npm run dev` 使用真实接口。离线数据保存在当前浏览器源的 localStorage 中，页尾的“恢复样例并刷新”会清除该演示存储并恢复初始项目。

接真实后端时，在仓库根 `.env` 中设置 `VITE_BACKEND_URL=http://127.0.0.1:8000`，启动后端，再运行 `npm run dev`。请求默认使用 `/api`，由 Vite 转发；部署时由 Nginx 代理。若需要直接指定 API 前缀，可设置前端环境变量 `VITE_API_BASE`。更改模式或环境变量后需重启开发服务器。

## 演示流程

1. 在项目总览选择样例项目，进入方案管理；表单按字段元数据分组，支持单位、说明和缺项对照。
2. 页尾下载错误 Excel，上传后查看全部错误；下载正确 Excel 可在新项目中导入五个方案。
3. 点击“开始评估”，进入看板。默认排除存在错误级硬约束失败的方案，并单列原因。
4. 切换角色，观察权重与贴近度；将居住品质滑杆调到 100%，观察 E 方案升到第一，再切回政府观察 C 方案恢复第一。
5. 点击维度分数，查看原始输入、计算式、分段折线、当前点、规则编号及出处；查看敏感性与名次概率。
6. 进入对话，点击快捷问题，展开工具卡，点击规则编号打开同一溯源抽屉；生成报告并下载 `.md`。
7. 真实模式下，选择方案并填写“假设的标准层重复率”，点击“创建副本并推演”。后端保存带 `parent_id` 的 What-if 副本，原方案参数保持不变；默认方案列表隐藏副本。

**现有四角色在原始样例上的名次相同。** 录屏展示了角色切换后的权重、贴近度变化，以及自定义权重引发的名次换位。未为了动画修改评分或角色结果。“角色切换直接产生名次变化”仍需另行确定可用的演示数据。

## 离线数据的边界

- 方案来源为 `data/schemes/mock/`，均为虚构开发数据。评分与排序快照由 Python 引擎生成，保留源文件哈希；不作为建筑专业结论。
- 支持项目与方案的本地保存、修改，以及提供的两份 Excel 的确定性导入回放。离线模式不解析任意 Excel；真实模式上传到后端解析。
- 评估仅接受已导出的完整样例参数组合。可在新项目导入正确 Excel 再评估；任意改变参数或增删方案后，旧评估会失效，不支持的组合明确返回 409。应连接后端计算任意输入。
- 角色模板及 286 组精确网格权重使用真实引擎快照。非网格自定义权重仅在离线模式运行 TOPSIS；敏感性、翻转点、名次概率不推算，返回空值并显示提示。真实模式所有业务计算均由后端完成。
- 对话使用已经返回的结果生成确定性文本与模拟事件流；未调用大模型。What-if 只说明流程，不修改方案或预测新结果。
- 规则与权重中的 `TODO(专业组)` 保留，未补造规范条文、阈值或行业数据。

## 类型与快照更新

字段元数据文件继续用于动态表单；新增的标准 JSON Schema 位于 `data/schema/jsonschema/`。生成器处理 Pydantic 的元组表示，输出 TypeScript 严格类型，禁止手改生成文件。

```powershell
# 在仓库根目录运行
uv run --project backend python scripts/export_schema.py
npm --prefix frontend run gen:types
npm --prefix frontend run sync:mock

# 从当前已集成的后端重新导出确定性快照
uv run --project backend python scripts/export_frontend_fixtures.py --grid-step 10
```

导出器使用当前工作树的公共模型与规则 / 排序引擎，数据库为隔离内存数据库。`--mcdm-root` 保留供历史分支只读加载缺失模块，当前无需指定。生成类型、同步数据与快照均已提交；正常启动不需要重新导出。CI 会校验 JSON Schema 和 TypeScript 生成产物是否与代码一致。

## 真实接口联调约定

- 所有真实请求使用已集成的当前后端。排序与智能体请求 / 响应类型从 Pydantic 模型生成；离线分析缺失字段仍可为空。
- TOPSIS、敏感性、概率和帕累托的数组下标以 `/rank` 返回的 `scheme_order` 映射，不能拿排序后的 `ranking` 或数字 ID 升序代替。
- `POST /api/projects/{id}/chat` 发送 `message`、`role`、已完成消息的 `history`；What-if 另带 `intent: whatif` 和 `change`。报告请求发送 `role`，响应为 `text/event-stream`。当前对话页与其右侧概览使用 government 角色。
- 协议以 [sse-events.md](sse-events.md) 为准。两处流消费共用 `src/api/sse.ts`；T8 的 `tool_call` / `tool_result` 显示为工具卡，`token.replace` 替换旧草稿，`done.report` 为最终正文，`done.cached` 显示缓存状态。
- `citation_warning` 只提示校验过程；最终数字标红使用 `done.unverified_numbers`，按 Unicode 码点映射 Python 偏移。含未核实数字的正文以转义的纯文本显示。真实响应直接按块更新，离线模拟保留逐字动画。
- 工具排序可能包含推演副本或其他权重，仅在正文展示；不会写入政府正式方案的排序缓存。右侧概览始终使用其自身的政府视角查询。
- 非 SSE、HTTP 错误、格式错误、未收到 `done` 的断流均显示错误；停止生成或切换项目会取消旧请求。真实接口失败不会回退到演示数据。

## 验证

```powershell
cd frontend
npm test
npm run lint
npm run build
npm run build:mock
# 先在另一个终端启动上面的 5177 离线服务器；默认使用本机 Chrome
npx playwright install ffmpeg
npm run test:ui
# 另启动真实后端（FakeLLM + 新建虚构数据库）和 5178 前端，再运行
npm run test:integration
```

`T7_URL` 可覆盖离线浏览器测试地址，`T7_BROWSER` 可覆盖浏览器通道，`T7_OUTPUT` 可将本次素材写到指定目录。真实集成地址由 `INTEGRATION_URL` 覆盖，默认 `http://127.0.0.1:5178`；脚本只应对新建虚构数据库运行，使用样例项目 1 / 方案 3 并创建推演副本。测试使用独立浏览器上下文，不操作个人 Chrome 标签。

2026-10-05 集成验证结果：

| 项目 | 结果 |
| --- | --- |
| 前端单元与数据层测试 | 49 通过，0 失败、0 跳过 |
| TypeScript 严格检查 / lint | 通过 |
| 真实模式与离线模式构建 | 均通过；Vite 提示部分包超过 500 kB |
| 后端完整 pytest | 443 通过，1 条依赖弃用警告 |
| 后端与本次 Python 脚本 Ruff 检查、修改文件格式检查 | 通过 |
| 浏览器完整离线流程 | 通过；页面运行时异常为 0 |
| 布局 | 1366×768、1920×1080 截图；看板在 320/375/414/768 宽度无页面横向溢出 |
| 真实后端评估、排序 | 独立数据库联调通过：5 个评估、4 个参与排名 |
| 真实对话、报告 | FakeLLM + 实际 REST / SSE 联调：报告下载、缓存、历史追问、What-if；取消和校验耗尽通过受控响应验证 |

后端测试运行于工作树虚拟环境，在 `backend` 目录使用 `python -m pytest --basetemp=data/pytest-integration -q` 指定可写临时目录；设置 `PYTHONUTF8=1`。证据与复跑方法见 [集成记录](integration-t1-t9.md)。

## 交付素材

- [项目总览](screenshots/t7/projects-1366.png)、[方案录入](screenshots/t7/schemes-1366.png)
- [对比看板 1366](screenshots/t7/dashboard-1366.png)、[对比看板 1920](screenshots/t7/dashboard-1920.png)
- [评分溯源](screenshots/t7/trace-1366.png)、[对话](screenshots/t7/chat-1366.png)
- [报告页面](screenshots/t7/chat-1920.png)、[真实后端看板](screenshots/t7/dashboard-real.png)
- [角色切换与滑杆换位录屏](screenshots/t7/roles-and-weights.webm)、[下载的报告](screenshots/t7/demo-report.md)
- [浏览器验收记录](screenshots/t7/verification.json)
