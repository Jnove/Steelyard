# 文档入口

当前文档按用途维护，运行命令先看 [仓库 README](../README.md)。

项目已通过初审，当前按 2026-10-22 晚彩排、10-23 路演准备；见 [路演准备](roadshow-readiness.md)与[项目交接记录](../memory/README.md)。初筛材料与历史分工见 [交付计划](submission-plan.md)。

| 文档 | 用途 |
| --- | --- |
| [路演准备](roadshow-readiness.md) | 当前日程、交互改进、验收命令、专业边界与现场备份 |
| [线上初筛交付计划](submission-plan.md) | 上一阶段的四项材料、逐日安排、团队分工与验收 |
| [技术说明文档模板](说明文档模版.docx) | 填写项目背景、技术实现、使用方法与实际完成范围 |
| [人机协同履历表模板](人机协同履历表模板.docx) | 按实际经历填写 AI 工具使用、承担工作与人工检查 |
| [规则编写指南](rules-guide.md) | 专业组编写、校验和提交 hard / metric 规则 |
| [第二轮规则与自定义集成评审](rules-round2-custom-integration.md) | PR #10 / #12 的接口修复、适用边界与验证记录 |
| [案例与地区规则集成](demo-regional-integration.md) | 案例来源、严格字段版、只追加发布、PR #13 的项目范围与缓存修复 |
| [字段对照表](fields.generated.md) | 从元数据生成的输入字段、单位与派生量参考；不要手改 |
| [活跃待办](open-items.md) | 路演阶段提示与专业规则、角色权重、T10、模型验收的未决事项 |
| [专业 YAML 与 PR 合并评审](main-yaml-merge-review.md) | 建筑四个 YAML、土木 PR #8 的 CI 修复、补充修复与专业边界 |
| [前端使用与联调](frontend-mvp.md) | 真实 / 离线模式、数据边界、类型生成与浏览器验证 |
| [界面改造简案](ui-redesign.md) | 面向初次访问与评审的页面调整、优先级和仍待完成的体验验收 |
| [青绿与紫粉玻璃界面方案](liquid-glass-plan.md) | 漂浮展台、玻璃材质、Three.js 场景、参考素材与 Skill、实施分工与验收 |
| [工业设计对比图接入](design-comparison-integration.md) | 取舍图、双方案差值、动态指标矩阵、真实结果关联与 SVG 导出 |
| [SSE 协议](sse-events.md) | 报告与对话请求、工具事件、替换、缓存、取消和数字校验 |
| [部署指南](deployment.md) | 服务器配置、发布、验收、回滚与运维 |
| [历史归档](archive/README.md) | 2026-10-05 集成、前端验收与 T8 PR 描述 |

`img/` 是规则指南图片；`screenshots/t7/` 是历史前端交付素材。
`evidence/` 保留历史日志与事件流，前端回归测试直接读取其中的 SSE 样本。新集成浏览器验收输出到忽略的 `backend/data/integration-ui/`，离线截图默认输出到 `backend/data/t7-ui/`；`T7_OUTPUT` 可指定独立目录。
这些资源保留原路径，归档中的测试数量、截图和结果只能说明记录当时的状态。

所有 `TODO(专业组)` 都必须由专业组核对后替换。引擎能计算分数，不代表示例规则具有工程依据。
