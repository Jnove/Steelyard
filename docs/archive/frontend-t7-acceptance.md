# T7 前端验收归档

> 记录日期：2026-10-05。历史素材不会证明当前版本已验收；使用与复跑方法见 [前端指南](../frontend-mvp.md)。

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

- [项目总览](../screenshots/t7/projects-1366.png)、[方案录入](../screenshots/t7/schemes-1366.png)
- [对比看板 1366](../screenshots/t7/dashboard-1366.png)、[对比看板 1920](../screenshots/t7/dashboard-1920.png)
- [评分溯源](../screenshots/t7/trace-1366.png)、[对话](../screenshots/t7/chat-1366.png)
- [报告页面](../screenshots/t7/chat-1920.png)、[真实后端看板](../screenshots/t7/dashboard-real.png)
- [角色切换与滑杆换位录屏](../screenshots/t7/roles-and-weights.webm)、[下载的报告](../screenshots/t7/demo-report.md)
- [浏览器验收记录](../screenshots/t7/verification.json)
