"""内建增强 schema + 覆盖层的合并入口。

**一条一致性保证**：``GET /api/schema`` 与 Excel 的模板生成 / 导出 / 导入都走这里，
所以"界面上能填的字段"和"Excel 里能填的列"永远一致——包括运行期加的自定义字段与
自定义枚举选项。

``session`` 为 ``None`` 时只返回**内建基线**：CLI 脚本（``scripts/make_template.py``
等生成提交进仓库的产物）走这条路，保证构建产物永远只含内建字段，CI 的
``git diff --exit-code`` 才有意义。
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel
from sqlmodel import Session

from app.custom.fields import merge_into_schema as merge_fields
from app.custom.options import merge_into_schema as merge_options
from app.models import SchemeParams
from app.schemas.meta import enriched_schema

__all__ = ["merged_schema"]

_Model = type[BaseModel]


def merged_schema(session: Session | None, model: _Model) -> dict[str, Any]:
    """构造增强 schema：内建基线 + 覆盖层。

    Args:
        session: 数据库会话；传 ``None`` 表示只要内建基线。
        model: ``ProjectParams`` / ``SchemeParams`` 等参数模型。

    Returns:
        与 :func:`app.schemas.meta.enriched_schema` 同结构，但：
        - 开放枚举字段的候选值含使用者自定义选项（``custom_options`` 标出哪些是加的）；
        - 方案层多出运行期自定义字段（条目带 ``"custom": true``）。

    深拷贝一层再合并：``enriched_schema`` 的返回值不应该被就地改写，
    否则"内建基线"会被悄悄带上使用者加的值。
    """
    schema = copy.deepcopy(enriched_schema(model))
    if session is None:
        return schema
    schema = merge_options(session, schema)
    if model is SchemeParams:
        # 自定义字段只加在方案层：值存在 SchemeParams.custom 里。
        schema = merge_fields(session, schema)
    return schema
