"""HTTP 路由模块。

按 AGENTS.md 的接口设计，按职责拆为独立子路由：
- projects    项目级 CRUD
- schemes     方案录入 / 导入
- evaluate    规则 + 指标 + 评分（T4 启用）
- rank        AHP / TOPSIS / 敏感性 / 帕累托（T5 启用）
- chat        智能体对话追问（SSE，T6 启用）
- report      比选报告生成（SSE，T6 启用）
- schema      字段元信息查询（T2 启用）
- rules       规则与指标定义查询（T3 启用）

T2 阶段启用：projects / schemes / schema。其余占位。
"""

from app.api import projects, schema, schemes

__all__ = ["projects", "schema", "schemes"]