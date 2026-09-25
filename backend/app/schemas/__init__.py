"""Schema 与元数据工具：

- ``meta``：从 Pydantic 模型生成带 ``unit`` / ``group`` / ``label`` 的增强 JSON Schema，
  供前端表单与 Excel 模板共用。
"""

from app.schemas.meta import enriched_schema

__all__ = ["enriched_schema"]