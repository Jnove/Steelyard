"""自定义角色权重模板：校验、读写、解析。

**校验同源**是这里的关键：界面里新增的模板**不另写一套校验**，而是交给
``app.engine.weights.check_one_role``——引擎加载 ``rules/weights.yaml`` 时走的同一个函数。
这样"``check_rules`` 说通过 ⟺ 引擎能加载"这条不变式对覆盖层同样成立。

比文件路径更严的一点：矩阵的一致性比率（CR）在文件里只是**警告**（专业组填的东西
不该让服务起不来），但界面里新加的模板 **CR ≥ 0.1 直接拒绝**，避免把自相矛盾的判断
固化进模板库。
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.custom.errors import CustomAddError, CustomProblem
from app.custom.models import CustomWeightTemplate
from app.engine.mcdm import CRITERION_ORDER
from app.engine.weights import ROLE_KEYS, RoleWeightTemplate, check_one_role

__all__ = [
    "CUSTOM_KEY_PREFIX",
    "add_template",
    "delete_template",
    "list_templates",
    "resolve_template",
    "to_engine_template",
    "validate_draft",
]

#: 自定义模板在引擎侧的键前缀，如 ``custom:3``；也接受直接用模板名引用。
CUSTOM_KEY_PREFIX = "custom:"


def validate_draft(
    *,
    name: str,
    note: str = "",
    source: str = "",
    weights: list[Any] | None = None,
    matrix: list[list[Any]] | None = None,
) -> RoleWeightTemplate:
    """用引擎的校验器校验一份模板草稿。

    Raises:
        CustomAddError: 给了两个来源 / 一个都没给 / 引擎校验不通过 / 矩阵一致性不合格。
    """
    if weights is not None and matrix is not None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="BOTH_SOURCES",
                    message="weights 与 matrix 只能给一个",
                    fix="用两两比较矩阵就填 matrix；权重由上级直接规定就填 weights",
                )
            ]
        )
    if weights is None and matrix is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="NO_SOURCE",
                    message="必须给 weights 或 matrix",
                    fix=(
                        f"按 {' / '.join(CRITERION_ORDER)} 的顺序填四个数（会自动归一化），"
                        "或填一个 4×4 的两两比较矩阵"
                    ),
                )
            ]
        )

    raw: dict[str, Any] = {"name": name, "note": note, "source": source}
    if weights is not None:
        raw["weights"] = weights
    if matrix is not None:
        raw["matrix"] = matrix

    # 借用一个内建角色键跑引擎自己的单角色校验；键名只影响返回值里的 key，随后会被覆盖。
    template, problems = check_one_role(ROLE_KEYS[0], raw)

    fatal = [p for p in problems if p.severity == "error"]
    if fatal:
        raise CustomAddError(
            [CustomProblem(code=p.code, message=p.message, fix=p.fix) for p in fatal]
        )

    inconsistent = [p for p in problems if p.code == "MATRIX_INCONSISTENT"]
    if inconsistent:
        raise CustomAddError(
            [CustomProblem(code=p.code, message=p.message, fix=p.fix) for p in inconsistent]
        )

    assert template is not None  # 没有 error 时必然解析出模板
    return template


def to_engine_template(row: CustomWeightTemplate) -> RoleWeightTemplate:
    """把库里的一行还原成引擎用的模板。

    每次都重跑一遍校验（含 AHP 解与一致性检验），好处是：即使校验器日后收紧，
    存量数据也不会"看起来能用、实际已经不合格"——不合格会在读取时明确报出来。
    """
    template = validate_draft(
        name=row.name,
        note=row.note,
        source=row.source,
        weights=None if row.matrix else list(row.weights or []),
        matrix=row.matrix,
    )
    return template.model_copy(update={"key": f"{CUSTOM_KEY_PREFIX}{row.id}", "name": row.name})


def list_templates(session: Session) -> list[CustomWeightTemplate]:
    """全部自定义模板，按名排序。"""
    return list(
        session.exec(select(CustomWeightTemplate).order_by(CustomWeightTemplate.name)).all()
    )


def add_template(
    session: Session,
    *,
    name: str,
    note: str = "",
    source: str = "",
    weights: list[Any] | None = None,
    matrix: list[list[Any]] | None = None,
    created_by: str | None = None,
) -> CustomWeightTemplate:
    """新增一个自定义权重模板。

    Raises:
        CustomAddError: 名字与内建角色键或已有模板冲突，或草稿校验不过。
    """
    clean = (name or "").strip()
    if clean in ROLE_KEYS:
        raise CustomAddError(
            [
                CustomProblem(
                    code="NAME_RESERVED",
                    message=f"「{clean}」是内建角色键，不能用作自定义模板名",
                    fix=f"换一个名字；内建角色是 {' / '.join(ROLE_KEYS)}",
                )
            ]
        )
    if not clean:
        raise CustomAddError(
            [
                CustomProblem(
                    code="NAME_EMPTY",
                    message="模板名不能为空",
                    fix="填一个能看出立场的名字，例如「代建单位（重工期）」",
                )
            ]
        )

    template = validate_draft(
        name=clean, note=note, source=source, weights=weights, matrix=matrix
    )

    existing = session.exec(
        select(CustomWeightTemplate).where(CustomWeightTemplate.name == clean)
    ).first()
    if existing is not None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="NAME_DUPLICATE",
                    message=f"已经有一个叫「{clean}」的自定义模板",
                    fix="在列表里找到它并删除，或换一个名字",
                )
            ]
        )

    row = CustomWeightTemplate(
        name=clean,
        note=note,
        source=source,
        weights=list(template.weights),
        matrix=template.matrix,
        created_by=created_by,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_template(session: Session, template_id: int) -> None:
    """删除一个自定义模板。

    Raises:
        CustomAddError: 该 id 不存在。
    """
    row = session.get(CustomWeightTemplate, template_id)
    if row is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="TEMPLATE_NOT_FOUND",
                    message=f"自定义权重模板 {template_id} 不存在",
                    fix="刷新列表后重试",
                )
            ]
        )
    session.delete(row)
    session.commit()


def resolve_template(session: Session, key: str) -> RoleWeightTemplate | None:
    """按 ``custom:<id>`` 或模板名解析自定义模板；找不到返回 ``None``。"""
    if key.startswith(CUSTOM_KEY_PREFIX):
        raw_id = key[len(CUSTOM_KEY_PREFIX) :]
        if not raw_id.isdigit():
            return None
        row = session.get(CustomWeightTemplate, int(raw_id))
    else:
        row = session.exec(
            select(CustomWeightTemplate).where(CustomWeightTemplate.name == key)
        ).first()
    if row is None:
        return None
    return to_engine_template(row)
