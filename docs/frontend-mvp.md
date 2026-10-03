# T7 前端 MVP 使用与联调

本任务位于 `feat/frontend-mvp`，基于 `feat/rules-engine` 开发。使用独立工作树，未修改 `feat/mcdm` 的代码和数据库。

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

# T4 未合并时，以只读目录指定可用的 T4 实现
uv run --project backend python scripts/export_frontend_fixtures.py --mcdm-root <T4仓库路径> --grid-step 10
```

导出排序快照的 Python 环境需包含 T4 所需 NumPy。T4 尚未合并时可使用其已安装依赖的 Python 来执行导出脚本；脚本使用本工作树公共模型，并从指定目录只读加载缺失的 T4 模块，数据库为隔离内存数据库。生成的类型、同步数据及快照已提交，正常运行前端不需要重新导出。

## 真实接口联调约定

- 项目、方案、导入、评估、规则和字段元数据使用当前后端接口；排序与角色读取依赖 T4 合并。
- 排序类型暂按 T4 草案定义于 `src/api/types.ts`。数组索引优先依据 `participant_ids`；草案未返回此字段时，按评估中参与方案的数字 ID 升序还原输入顺序。T4 应明确并固定顺序契约，随后生成排序类型。
- T8 尚未提供接口。`src/api/sse.ts` 集中适配暂定协议：`POST /api/projects/{id}/chat` 请求体 `{message}`，`POST /api/projects/{id}/report` 请求体 `{}`，响应类型 `text/event-stream`。
- 暂定事件：`token {text}`、`tool_start {id,name}`、`tool_end {id,name,result?}`、`done {message?}`、`error {message}`。支持命名事件和默认 `message` 事件内的 `{type,...payload}`。T8 定稿后在适配器核对，不猜测别名。
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
```

`T7_URL` 可覆盖浏览器测试地址，`T7_BROWSER` 可覆盖 Playwright 浏览器通道。测试使用独立浏览器上下文，不操作个人 Chrome 标签。输出截图、Markdown 示例与录屏到 `docs/screenshots/t7/`。

2026-10-03 验证结果：

| 项目 | 结果 |
| --- | --- |
| 前端单元与数据层测试 | 43 通过，0 失败、0 跳过 |
| TypeScript 严格检查 / lint | 通过 |
| 真实模式与离线模式构建 | 均通过；Vite 提示部分包超过 500 kB |
| 后端完整 pytest | 295 通过，2 条依赖弃用警告 |
| 后端与本次 Python 脚本 Ruff 检查、修改文件格式检查 | 通过 |
| 浏览器完整离线流程 | 通过；页面运行时异常为 0 |
| 布局 | 1366×768、1920×1080 截图；看板在 320/375/414/768 宽度无页面横向溢出 |
| 真实后端评估、排序 | 独立数据库联调通过：5 个评估、4 个参与排名 |
| 真实对话、报告 | T8 未实现，实际 404 能正确显示；成功流尚待联调 |

后端测试运行于工作树的虚拟环境，使用 `python -m pytest --basetemp=./data/pytest-t7-resume-3 -q` 指定可写临时目录；设置 `PYTHONIOENCODING=utf-8` 与 `PYTHONUTF8=1`。未跳过或删除失败测试。

## 交付素材

- [项目总览](screenshots/t7/projects-1366.png)、[方案录入](screenshots/t7/schemes-1366.png)
- [对比看板 1366](screenshots/t7/dashboard-1366.png)、[对比看板 1920](screenshots/t7/dashboard-1920.png)
- [评分溯源](screenshots/t7/trace-1366.png)、[对话](screenshots/t7/chat-1366.png)
- [报告页面](screenshots/t7/chat-1920.png)、[真实后端看板](screenshots/t7/dashboard-real.png)
- [角色切换与滑杆换位录屏](screenshots/t7/roles-and-weights.webm)、[下载的报告](screenshots/t7/demo-report.md)
- [浏览器验收记录](screenshots/t7/verification.json)
