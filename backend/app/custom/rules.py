"""自定义规则：校验、读写、与内建规则合并。

**校验同源**：这里不另写一套校验，直接交给 :func:`app.engine.rule_check.check_rule_problems`
——``scripts/check_rules.py`` 用的就是同一份，所以"check_rules 说通过"与"引擎能加载"
对运行期的自定义规则同样成立。

比文件里的规则**更严**的一条：``source`` 必须写明出处、且不允许挂 TODO。
自定义规则没有 CI 把关，出处是唯一能让人复核的依据；专业组的约定是"没有条文依据就别加"，
这里把它变成保存时的硬闸门，而不是靠自觉。
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlmodel import Session, select

from app.custom import fields as fields_service
from app.custom.errors import CustomAddError, CustomProblem
from app.custom.models import CustomRule
from app.engine.rule_check import Issue, check_rule_problems
from app.engine.rules import RuleDef, RuleSet, get_ruleset

__all__ = [
    "CUSTOM_ORIGIN",
    "add_rule",
    "custom_rule_ids",
    "delete_rule",
    "list_rules",
    "merge_ruleset",
    "row_to_rule",
    "ruleset_with_custom",
    "validate_payload",
]

#: 自定义规则在 ``GET /api/rules`` 里的"来源"标识（内建规则显示的是文件名）。
CUSTOM_ORIGIN = "（界面自定义）"


def _source_problems(payload: dict) -> list[CustomProblem]:
    """出处闸门：必填，且不允许挂 TODO。"""
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        return [
            CustomProblem(
                code="SOURCE_REQUIRED",
                message="规则必须写明 source（出处）",
                fix=(
                    "写「规范编号 第 X 条」，或「经验规则（XX组）：理由」。"
                    "自定义规则不经过 git 与 CI，出处是唯一能让人复核的依据"
                ),
            )
        ]
    if "TODO" in source:
        return [
            CustomProblem(
                code="SOURCE_TODO",
                message="source 里还挂着 TODO，出处尚未落实",
                fix="核对规范原文后换成真实出处再保存（内建规则允许挂 TODO，自定义规则不允许）",
            )
        ]
    return []


def validate_payload(
    payload: object, *, known: frozenset[str] | None = None
) -> tuple[RuleDef | None, list[Issue]]:
    """校验一份规则定义。

    Args:
        payload: 规则字典，字段见 ``rules/_template.yaml``。
        known: 可在表达式里引用的字段名；默认取内建字段 + 派生量。
            自定义字段接进来后由调用方传入。

    Returns:
        ``(解析好的规则 或 None, 全部问题)``。有 error 级问题时第一个元素为 ``None``。
    """
    issues = check_rule_problems(payload, known=known)
    if any(issue.severity == "error" for issue in issues):
        return None, issues
    assert isinstance(payload, dict)  # 不是字典时 check_rule_problems 已经报了错
    return RuleDef.model_validate(payload), issues


def list_rules(session: Session) -> list[CustomRule]:
    """全部自定义规则，按 ID 排序。"""
    return list(session.exec(select(CustomRule).order_by(CustomRule.rule_id)).all())


def custom_rule_ids(session: Session) -> set[str]:
    """全部自定义规则的 ID，供接口标注"哪些是运行期加的"。"""
    return {row.rule_id for row in list_rules(session)}


def row_to_rule(row: CustomRule, *, known: frozenset[str] | None = None) -> RuleDef:
    """把库里的一行还原成引擎用的规则。

    每次都重新过校验器：校验器日后收紧时，存量规则不会"看起来能用、实际已经不合格"
    ——不合格会在读取时明确报出来，而不是悄悄参与评估。

    Args:
        known: 可引用的字段名。传 :func:`app.custom.fields.known_names` 的结果，
            自定义规则就能引用**自定义字段**。

    Raises:
        CustomAddError: 该行现在校验不过（例如规则模型加了新的必填项）。
    """
    rule, issues = validate_payload(row.payload, known=known)
    if rule is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code=issue.code,
                    message=f"自定义规则 {row.rule_id} 现在校验不过：{issue.message}",
                    fix=issue.fix,
                )
                for issue in issues
                if issue.severity == "error"
            ]
        )
    return rule


def add_rule(session: Session, *, payload: object, created_by: str | None = None) -> CustomRule:
    """新增一条自定义规则。

    Raises:
        CustomAddError: 不是对象、出处没写、校验不过，或 ID 与内建/已有自定义规则冲突。
    """
    if not isinstance(payload, dict):
        raise CustomAddError(
            [
                CustomProblem(
                    code="RULE_NOT_OBJECT",
                    message="规则必须是一个对象",
                    fix="对照 rules/_template.yaml 逐字段写：id / name / type / source …",
                )
            ]
        )

    problems = _source_problems(payload)
    # 自定义规则可以把**自定义字段**写进表达式，所以已知字段集要带上覆盖层注册的名字。
    known = fields_service.known_names(session)
    if not problems:
        rule, issues = validate_payload(payload, known=known)
        problems = [
            CustomProblem(code=issue.code, message=issue.message, fix=issue.fix)
            for issue in issues
            if issue.severity == "error"
        ]
    if problems:
        raise CustomAddError(problems)

    parsed, _ = validate_payload(payload, known=known)
    assert parsed is not None

    if get_ruleset().by_id(parsed.id) is not None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="RULE_ID_RESERVED",
                    message=f"规则 ID「{parsed.id}」已被内建规则占用",
                    fix="换一个没用过的编号；内建规则在 rules/*.yaml 里，ID 必须全局唯一",
                )
            ]
        )

    existing = session.exec(select(CustomRule).where(CustomRule.rule_id == parsed.id)).first()
    if existing is not None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="RULE_ID_DUPLICATE",
                    message=f"已经有一条自定义规则用了 ID「{parsed.id}」",
                    fix="在列表里找到它并删除，或换一个编号",
                )
            ]
        )

    row = CustomRule(rule_id=parsed.id, payload=dict(payload), created_by=created_by)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def delete_rule(session: Session, row_id: int) -> None:
    """删除一条自定义规则。

    Raises:
        CustomAddError: 该 id 不存在。
    """
    row = session.get(CustomRule, row_id)
    if row is None:
        raise CustomAddError(
            [
                CustomProblem(
                    code="RULE_NOT_FOUND",
                    message=f"自定义规则 {row_id} 不存在",
                    fix="刷新列表后重试",
                )
            ]
        )
    session.delete(row)
    session.commit()


def merge_ruleset(
    builtin: RuleSet,
    rows: Iterable[CustomRule],
    *,
    known: frozenset[str] | None = None,
) -> RuleSet:
    """把覆盖层的自定义规则接到内建规则**后面**。

    内建规则永远在前、不因覆盖层而改变；ID 冲突由 :class:`RuleSet` 自己再兜一层
    （``__post_init__`` 会查重复 ID），所以即使有人绕过 :func:`add_rule` 写库也不会静默生效。
    """
    defs = [row_to_rule(row, known=known) for row in rows]
    if not defs:
        return builtin
    origins = dict(builtin.origins)
    for rule in defs:
        origins[rule.id] = CUSTOM_ORIGIN
    todo = tuple(sorted({*builtin.todo_source_ids, *(r.id for r in defs if "TODO" in r.source)}))
    return RuleSet(rules=(*builtin.rules, *defs), origins=origins, todo_source_ids=todo)


def ruleset_with_custom(session: Session | None, builtin: RuleSet | None = None) -> RuleSet:
    """当前生效的规则集 = 内建规则 + 覆盖层的自定义规则。

    没有自定义规则时原样返回内建集合（对象相同），所以清空覆盖层后行为与纯内建完全一致。
    校验时把**自定义字段**也算作已知字段，因此自定义规则可以引用它们。

    ``session=None`` 表示**只要内建规则集**：提交进 git 的前端产物
    （``scripts/export_frontend_fixtures.py``）走这条路——自定义规则是运行期草稿，
    混进构建产物就会让 CI 的 ``git diff --exit-code`` 失去意义。
    """
    if session is None:
        return builtin if builtin is not None else get_ruleset()
    base = builtin if builtin is not None else get_ruleset()
    return merge_ruleset(base, list_rules(session), known=fields_service.known_names(session))
