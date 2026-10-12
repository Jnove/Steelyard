"""自定义枚举选项：读写，以及并入增强 schema。

**只允许挂在开放枚举上**。判据是模型里的 ``extensible=True``（见
``app/models/params.py`` 的 ``risk_features`` / ``irregularity_items``），
而不是"这个字段有没有 options"——因为像 ``structure_type`` 这种字段虽然也有候选值，
但规则会按它的取值分支，多一个规则不认识的取值会让那些规则**静默失效**（判成不适用），
比报错更危险。
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.custom.errors import CustomAddError, CustomProblem
from app.custom.models import CustomOption
from app.models.params import ProjectParams, SchemeParams

__all__ = [
    "MAX_OPTION_LENGTH",
    "add_option",
    "delete_option",
    "extensible_fields",
    "list_options",
    "merge_into_schema",
]

#: 选项文本长度上限：下拉框里的一项，不该塞进一整段说明。
MAX_OPTION_LENGTH = 40


def extensible_fields() -> dict[str, dict[str, Any]]:
    """列出允许追加候选值的字段。

    Returns:
        ``{字段名: {"label":…, "group":…, "builtin": [内建候选值…]}}``。
    """
    out: dict[str, dict[str, Any]] = {}
    for model in (ProjectParams, SchemeParams):
        properties: dict[str, Any] = model.model_json_schema().get("properties", {})
        for name, prop in properties.items():
            if not prop.get("extensible"):
                continue
            out[name] = {
                "label": prop.get("label", name),
                "group": prop.get("group", ""),
                "builtin": list(prop.get("options") or prop.get("enum") or []),
            }
    return out


def _clean_value(value: str) -> str:
    """去掉首尾空白并做基本校验。"""
    text = (value or "").strip()
    if not text:
        raise CustomAddError(
            [
                CustomProblem(
                    code="OPTION_EMPTY",
                    message="选项内容不能为空",
                    fix="填一个有意义的名称，例如「临近地铁振动」",
                )
            ]
        )
    if len(text) > MAX_OPTION_LENGTH:
        raise CustomAddError(
            [
                CustomProblem(
                    code="OPTION_TOO_LONG",
                    message=f"选项内容 {len(text)} 字，超过 {MAX_OPTION_LENGTH} 字上限",
                    fix="下拉框里放短名称；详细说明写到方案的备注里",
                )
            ]
        )
    return text


def list_options(session: Session, field: str | None = None) -> list[CustomOption]:
    """按字段筛选自定义选项（``field=None`` 表示全部）。"""
    statement = select(CustomOption)
    if field is not None:
        statement = statement.where(CustomOption.field == field)
    statement = statement.order_by(CustomOption.field, CustomOption.sort, CustomOption.id)
    return list(session.exec(statement).all())


def add_option(
    session: Session, *, field: str, value: str, created_by: str | None = None
) -> CustomOption:
    """给开放枚举字段追加一个候选值。

    Raises:
        CustomAddError: 字段不允许扩展、内容为空/过长、与内建值或已有自定义值重复。
    """
    fields = extensible_fields()
    if field not in fields:
        known = "、".join(sorted(fields)) or "（无）"
        raise CustomAddError(
            [
                CustomProblem(
                    code="FIELD_NOT_EXTENSIBLE",
                    message=f"字段 {field} 不支持自定义选项",
                    fix=(
                        f"只有开放枚举可以扩展，当前是：{known}。"
                        "像 structure_type 这样的封闭枚举不能加值——规则会按它的取值分支，"
                        "多一个规则不认识的取值会让那些规则静默失效"
                    ),
                )
            ]
        )

    text = _clean_value(value)
    if text in fields[field]["builtin"]:
        raise CustomAddError(
            [
                CustomProblem(
                    code="OPTION_IS_BUILTIN",
                    message=f"「{text}」已经是 {field} 的内建选项",
                    fix="直接在表单里选它，不需要重复添加",
                )
            ]
        )

    existing = session.exec(
        select(CustomOption).where(CustomOption.field == field, CustomOption.value == text)
    ).first()
    if existing is not None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="OPTION_DUPLICATE",
                    message=f"「{text}」已经添加过了",
                    fix="在列表里找到它；要改顺序请删掉重新添加",
                )
            ]
        )

    same_field = list(
        session.exec(select(CustomOption).where(CustomOption.field == field)).all()
    )
    next_sort = max((row.sort for row in same_field), default=0) + 10

    option = CustomOption(field=field, value=text, sort=next_sort, created_by=created_by)
    session.add(option)
    session.commit()
    session.refresh(option)
    return option


def delete_option(session: Session, option_id: int) -> None:
    """删除一个自定义选项。

    Raises:
        CustomAddError: 该 id 不存在。
    """
    row = session.get(CustomOption, option_id)
    if row is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="OPTION_NOT_FOUND",
                    message=f"自定义选项 {option_id} 不存在",
                    fix="刷新列表后重试",
                )
            ]
        )
    session.delete(row)
    session.commit()


def merge_into_schema(session: Session, schema: dict[str, Any]) -> dict[str, Any]:
    """把自定义选项追加进增强 schema 的 ``enum`` / ``options``（就地修改并返回）。

    注意语义：**内建候选值永远在前且不会被替换**，自定义值只是追加在后面。
    因此提交进仓库的 ``data/schema/*.json`` 始终是"纯内建"的基线，
    运行期的 ``GET /api/schema`` 是"基线 + 覆盖层"。
    """
    rows = list_options(session)
    if not rows:
        return schema

    by_field: dict[str, list[str]] = {}
    for row in rows:
        by_field.setdefault(row.field, []).append(row.value)

    for field_info in schema.get("fields", []):
        extra = by_field.get(str(field_info.get("name")))
        if not extra:
            continue
        builtin = list(field_info.get("options") or field_info.get("enum") or [])
        combined = builtin + [value for value in extra if value not in builtin]
        if "enum" in field_info:
            field_info["enum"] = combined
        else:
            field_info["options"] = combined
        # 让前端能区分"哪些是使用者自己加的"，据此加提示或允许删除。
        field_info["custom_options"] = [value for value in extra if value not in builtin]
    return schema
