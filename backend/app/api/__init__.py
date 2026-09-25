"""HTTP 路由模块。

按 AGENTS.md 的接口设计，按职责拆为独立子路由：
- projects    项目级 CRUD
- schemes     方案录入 / 导入
- evaluate    规则 + 指标 + 评分
- rank        AHP / TOPSIS / 敏感性 / 帕累托
- chat        智能体对话追问（SSE）
- report      比选报告生成（SSE）
- rules       规则与指标定义查询
"""