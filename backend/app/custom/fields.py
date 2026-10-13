"""自定义字段：注册表校验、读写、并入 schema、摊平进规则命名空间。

**不动态造 Pydantic 模型**：值统一存在保留字段 ``SchemeParams.custom`` 这个字典里，
这里只维护"字段长什么样"的注册表（见 ``docs/design-custom-add.md`` 第八节）。
引擎构造命名空间时把 ``custom`` 的键摊平到顶层，于是自定义规则可以像引用内建字段那样
引用自定义字段（见 :func:`app.engine.rules.build_namespace`）。

⚠️ 一条硬约束：**内建规则（``rules/*.yaml``）不能引用自定义字段**——
``scripts/check_rules.py`` 是纯文件校验、看不到运行期的覆盖层。自定义字段只能被
自定义规则引用；定稿后应走"导出成内建字段"的路径（design 文档第一节第二条决策）。
"""

from __future__ import annotations

import keyword
import math
import re
from typing import Any

from sqlmodel import Session, select

from app.custom import audit
from app.custom.errors import CustomAddError, CustomProblem
from app.custom.models import CustomField, CustomRule
from app.custom.state import invalidate_results
from app.engine.metrics import derived_names
from app.engine.rules import ALLOWED_FUNCTIONS, analyze_expression, known_field_names
from app.models.params import GROUP_ORDER, ProjectParams, SchemeParams

__all__ = [
    "CUSTOM_CONTAINER",
    "FIELD_KINDS",
    "FIELD_KEY_PATTERN",
    "add_field",
    "delete_field",
    "field_keys",
    "known_names",
    "list_fields",
    "merge_into_schema",
    "reserved_names",
    "validate_values",
]

#: 值存放的保留字段名。自定义字段的值都在 ``SchemeParams.custom`` 里。
CUSTOM_CONTAINER = "custom"

#: 支持的自定义字段类型。``ratio`` 是 0–1 的小数（与内建比例字段口径一致）。
FIELD_KINDS: tuple[str, ...] = ("number", "integer", "ratio", "text", "list")

#: 字段名（英文小写下划线，2–30 位）。规则里直接用它引用，所以要像变量名。
FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,29}$")


def reserved_names() -> set[str]:
    """不能用作自定义字段名的名字：内建字段 + 派生量 + 保留字段本身。

    内部用 ``model_fields`` 而不是 ``model_json_schema()``：前者更轻，且足够判断重名。
    """
    return {
        *ProjectParams.model_fields,
        *SchemeParams.model_fields,
        *derived_names(),
        CUSTOM_CONTAINER,
        *ALLOWED_FUNCTIONS,
    }


def list_fields(session: Session) -> list[CustomField]:
    """全部自定义字段，按字段名排序。"""
    return list(session.exec(select(CustomField).order_by(CustomField.key)).all())


def field_keys(session: Session) -> set[str]:
    """全部自定义字段名，供规则校验器把"已知字段"放大。"""
    return {row.key for row in list_fields(session)}


def known_names(session: Session) -> frozenset[str]:
    """规则表达式里可引用的名字 = 内建字段 + 派生量 + 自定义字段。"""
    return known_field_names(extra=field_keys(session))


def validate_values(
    session: Session,
    values: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    allow_inactive: bool = False,
) -> dict[str, Any]:
    """Validate registered values; preserve unchanged historical inactive keys only.

    Registration supplies types, never the submitted dictionary. Retained inactive
    keys are excluded from the expression whitelist and cannot affect rules.
    """
    registered = {row.key: row for row in list_fields(session)}
    reserved = reserved_names()
    problems: list[CustomProblem] = []
    for key, value in values.items():
        if key in reserved:
            problems.append(CustomProblem("CUSTOM_KEY_RESERVED", f"自定义字段 {key} 与内建字段或派生量重名", "删除该自定义键，使用内建参数输入"))
            continue
        row = registered.get(key)
        if row is None:
            unchanged = previous is not None and key in previous and type(value) is type(previous[key]) and value == previous[key]
            if not allow_inactive and not unchanged:
                problems.append(CustomProblem("CUSTOM_KEY_UNKNOWN", f"自定义字段 {key} 尚未注册或已删除", "先注册字段；已删除字段的历史值只能原样保留"))
            continue
        if value is None:
            continue
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if row.kind in ("number", "ratio"):
            try:
                valid = numeric and math.isfinite(value)
            except OverflowError:
                valid = False
            if row.kind == "ratio":
                valid = valid and 0 <= value <= 1
        elif row.kind == "integer":
            try:
                valid = isinstance(value, int) and not isinstance(value, bool) and math.isfinite(value)
            except OverflowError:
                valid = False
        elif row.kind == "text":
            valid = isinstance(value, str)
        elif row.kind == "list":
            valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
            if valid and row.options:
                valid = set(value).issubset(row.options)
        else:
            valid = False
        if not valid:
            problems.append(CustomProblem("CUSTOM_VALUE_INVALID", f"自定义字段 {key}（{row.label}）取值不符合 {row.kind} 类型或约束", "数值须有限且不能用布尔值；比例须在0–1；整数须为整数；列表须为合法字符串选项"))
    if problems:
        raise CustomAddError(problems)
    return dict(values)


def _problems_for(
    *,
    key: str,
    label: str,
    kind: str,
    group: str,
    options: list[str] | None,
) -> list[CustomProblem]:
    problems: list[CustomProblem] = []

    if not FIELD_KEY_PATTERN.fullmatch(key) or keyword.iskeyword(key):
        problems.append(
            CustomProblem(
                code="FIELD_KEY_SHAPE",
                message=f"字段名「{key}」不合规",
                fix="用小写字母开头、只含小写字母/数字/下划线，长度 2–30，例如 bearing_wall_ratio",
            )
        )
    elif key in reserved_names():
        problems.append(
            CustomProblem(
                code="FIELD_KEY_RESERVED",
                message=f"字段名「{key}」与内建字段或派生量重名",
                fix="换一个名字。自定义字段只能**追加**，不能覆盖内建字段——"
                "否则引用它的规则会突然算到另一个值",
            )
        )

    if not label.strip():
        problems.append(
            CustomProblem(code="FIELD_LABEL_EMPTY", message="中文名不能为空", fix="填一个表单里能看懂的短名称")
        )

    if kind not in FIELD_KINDS:
        problems.append(
            CustomProblem(
                code="FIELD_KIND_UNKNOWN",
                message=f"类型「{kind}」不支持",
                fix=f"从这些里选：{' / '.join(FIELD_KINDS)}",
            )
        )

    if group not in GROUP_ORDER:
        problems.append(
            CustomProblem(
                code="FIELD_GROUP_UNKNOWN",
                message=f"分组「{group}」不在表单分组里",
                fix=f"从这些里选：{' / '.join(GROUP_ORDER)}",
            )
        )

    if options is not None and kind != "list":
        problems.append(
            CustomProblem(
                code="FIELD_OPTIONS_UNSUPPORTED",
                message="只有列表类型才能给候选值",
                fix="把类型改成 list，或去掉候选值",
            )
        )
    if options is not None and len({o.strip() for o in options if o.strip()}) != len(options):
        problems.append(
            CustomProblem(
                code="FIELD_OPTIONS_DUPLICATE",
                message="候选值里有空白项或重复项",
                fix="每个候选值都要非空且互不相同",
            )
        )
    return problems


def add_field(
    session: Session,
    *,
    key: str,
    label: str,
    kind: str,
    unit: str = "—",
    group: str = "基本信息",
    options: list[str] | None = None,
    description: str = "",
    created_by: str | None = None,
) -> CustomField:
    """新增一个自定义字段。

    Raises:
        CustomAddError: 字段名不合规/与内建重名、类型或分组不认识、候选值不合法、重名。
    """
    clean_key = key.strip()
    clean_label = label.strip()
    problems = _problems_for(
        key=clean_key, label=clean_label, kind=kind, group=group, options=options
    )
    if not problems:
        existing = session.exec(select(CustomField).where(CustomField.key == clean_key)).first()
        if existing is not None:
            problems.append(
                CustomProblem(
                    code="FIELD_KEY_DUPLICATE",
                    message=f"已经有一个叫「{clean_key}」的自定义字段",
                    fix="在列表里找到它并删除，或换一个字段名",
                )
            )
    if problems:
        raise CustomAddError(problems)

    row = CustomField(
        key=clean_key,
        label=clean_label,
        kind=kind,
        unit=unit or "—",
        group=group,
        options=options,
        description=description,
        created_by=created_by,
    )
    session.add(row)
    invalidate_results(session)
    # 留痕与业务写操作同一个事务（见 app/custom/audit.py 的三条纪律）。
    audit.record(
        session,
        operator=created_by,
        action="create",
        kind="field",
        target=clean_key,
        summary=f"新增自定义字段「{clean_label}」（{clean_key}）",
        detail={"key": clean_key, "label": clean_label, "kind": kind, "group": group},
    )
    session.commit()
    session.refresh(row)
    return row


def delete_field(
    session: Session, field_row_id: int, *, operator: str | None = None
) -> None:
    """删除一个自定义字段。

    注意：值仍留在各方案的 ``custom`` 字典里（不主动清理）——那些值可能已被
    导出的 Excel 或报告引用过；需要清理时另行处理。

    Raises:
        CustomAddError: 该 id 不存在。
    """
    row = session.get(CustomField, field_row_id)
    if row is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="FIELD_NOT_FOUND",
                    message=f"自定义字段 {field_row_id} 不存在",
                    fix="刷新列表后重试",
                )
            ]
        )
    known = known_names(session)
    references = []
    for rule in session.exec(select(CustomRule)).all():
        for expression_key in ("when", "check", "value"):
            expression = rule.payload.get(expression_key)
            if isinstance(expression, str) and row.key in analyze_expression(expression, expression_key, known).names:
                references.append(rule.rule_id)
                break
    if references:
        raise CustomAddError([CustomProblem("FIELD_IN_USE", f"字段 {row.key} 仍被规则 {'、'.join(references)} 引用", "先删除引用该字段的自定义规则，再删除字段")])
    audit.record(
        session,
        operator=operator,
        action="delete",
        kind="field",
        target=row.key,
        summary=f"删除自定义字段「{row.label}」（{row.key}）",
        detail={"key": row.key, "label": row.label, "kind": row.kind},
    )
    session.delete(row)
    invalidate_results(session)
    session.commit()


def _field_entry(row: CustomField) -> dict[str, Any]:
    """把一行注册表转成增强 schema 里的一个字段条目。

    ``type`` 与 ``constraints`` 沿用内建字段的口径，因此前端的 schema 驱动表单
    与 Excel 生成器都能直接吃：比例类给 0–1 约束，列表类给 ``options``。
    """
    type_map = {"number": "number", "integer": "integer", "ratio": "number", "text": "string", "list": "array<string>"}
    entry: dict[str, Any] = {
        "name": row.key,
        "label": row.label,
        "description": row.description,
        "unit": row.unit,
        "group": row.group,
        "type": type_map.get(row.kind, "string"),
        "required": False,
        "constraints": {},
        "kind": row.kind,
        # 前端据此给"运行期加的字段"打标：未进入 git、不参与 CI 校验。
        "custom": True,
    }
    if row.kind == "ratio":
        entry["constraints"] = {"minimum": 0, "maximum": 1}
    if row.options:
        entry["options"] = list(row.options)
    return entry


def merge_into_schema(session: Session, schema: dict[str, Any]) -> dict[str, Any]:
    """把自定义字段追加进增强 schema 的 ``fields``（就地修改并返回）。

    **内建字段永远在前**，自定义字段按字段名排序追加在后面；重名不可能发生
    （注册表在写入时就拒绝了与内建重名）。
    """
    rows = list_fields(session)
    if not rows:
        return schema
    fields = schema.setdefault("fields", [])
    existing = {str(item.get("name")) for item in fields}
    for row in rows:
        if row.key in existing:
            continue
        fields.append(_field_entry(row))
    return schema
