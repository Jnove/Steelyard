"""规则条目的结构校验（**引擎侧唯一一份**）。

`scripts/check_rules.py` 与运行期自定义规则都调用这里，所以"check_rules 说通过"
与"引擎能加载"永远是一回事——这是项目的不变式之一，见 ``docs/design-custom-add.md``。

分工：

- **本模块**：一条规则的结构与表达式校验，产出带中文说明与"怎么改"的问题清单；
- **``scripts/check_rules.py``**：文件级的事——Tab / 全角冒号等文本扫描、YAML 解析、
  跨文件 ID 重复、``weights.yaml``、以及把问题渲染成 ``文件名:行号 规则ID — 说明 — 怎么改``。

行号：``yaml.compose()`` 得到的 node 树只在校验文件时才拿得到，所以 node 是**可选参数**——
界面里新加规则没有 YAML 文件，行号为空，其余报错完全一致。
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from app.engine.rules import (
    DIMENSION_KEYS,
    RuleDef,
    analyze_expression,
    known_field_names,
)
from app.engine.scoring import SCORE_MAX, SCORE_MIN

__all__ = [
    "GENERIC_FIX",
    "Issue",
    "VALID_DIMENSIONS",
    "VALID_SCORING_KINDS",
    "check_rule_problems",
    "display_path",
]

Severity = Literal["error", "warning"]

#: 仓库根：``app/engine/rule_check.py`` → engine → app → backend → 仓库根。
REPO_ROOT = Path(__file__).resolve().parents[3]


def display_path(path: Path) -> str:
    """尽量显示相对仓库根的路径，读起来短一些；不在仓库里就原样返回。"""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()

#: 硬约束 / 评分指标共用的枚举维度，取自引擎，避免两处各写一份。
VALID_DIMENSIONS: tuple[str, ...] = tuple(DIMENSION_KEYS)
#: 评分指标支持的 ``scoring.kind``。
VALID_SCORING_KINDS: tuple[str, ...] = ("piecewise",)

#: 通用的兜底建议。
GENERIC_FIX = "照 rules/_template.yaml 里的骨架逐字段对一遍这条规则"


@dataclass
class Issue:
    """单条校验问题。

    ``message`` 说"错在哪"，``fix`` 说"怎么改"，两段都要让非程序员看懂。
    ``code`` 不打印，只给测试和其它脚本做稳定的程序化判别用。
    """

    severity: Severity
    code: str
    message: str
    fix: str
    line: int | None = None
    rule_id: str | None = None

    def render(self, source: str | Path) -> str:
        """渲染成一行给人看的报错。

        ``source`` 可以是文件路径（会缩成仓库相对路径）或"（界面新增）"这样的来源描述。
        """
        label = display_path(source) if isinstance(source, Path) else source
        kind = "错误" if self.severity == "error" else "警告"
        loc = f"{label}:{self.line}" if self.line is not None else label
        rule_id = self.rule_id or "（未知 ID）"
        return f"{kind}  {loc}  {rule_id} — {self.message} — 怎么改：{self.fix}"


#: 必填字段 → "怎么改"。缺字段的提示要具体到"写什么"，不能只说"补上"。
_MISSING_FIELD_FIX: dict[str, str] = {
    "id": "补一行 `id: C-01`（前缀字母 C/Q/S/K/G + 短横线 + 两位数字，全局唯一）",
    "name": "补一行 `name: 规则的中文名`，这个名字会出现在前端和报告里",
    "type": "补一行 `type: hard`（硬约束）或 `type: metric`（评分指标）",
    "source": '补一行 `source: "TODO(专业组)：待补"`，定稿后换成规范编号 + 条文号',
    "check": '补一行 `check: "字段名 >= 阈值"`，这是判定用的布尔表达式',
    "dimension": f"补一行 `dimension: quality`，从 {' / '.join(VALID_DIMENSIONS)} 里选一个",
    "value": '补一行 `value: "字段名"`，写指标取哪个字段（也可以是表达式）',
    "scoring": "补上 `scoring:` 子块，里面写 `kind: piecewise` 和 `points:` 控制点列表",
    "kind": f"补一行 `kind: piecewise`，现阶段只支持 {' / '.join(VALID_SCORING_KINDS)}",
    "points": "补上 `points:` 控制点列表，至少两项，每项形如 `- [0.50, 0]`",
}

#: 取值不合法 → 中文说明与"怎么改"。键是 Pydantic 的错误路径。
_LITERAL_FIX: dict[str, tuple[str, str]] = {
    "type": (
        "type 只能是 hard 或 metric",
        "硬约束（违反就踢出排名）写 hard，评分指标（打 0–100 分）写 metric",
    ),
    "dimension": (
        f"dimension 只能是 {' / '.join(VALID_DIMENSIONS)} 之一",
        "从这四个里选一个；确实需要新维度请先找队长改 app/models/eval.py，不要直接在 YAML 里造新值",
    ),
    "severity": (
        "severity 只能是 error 或 warning",
        "error（默认）会标红并踢出排名，warning 只提示不影响排名",
    ),
    "scoring.kind": (
        f"scoring.kind 只能是 {' / '.join(VALID_SCORING_KINDS)}",
        "写 `kind: piecewise`（分段线性）",
    ),
}


def _line_of(node: yaml.Node | None, loc: Iterable[Any]) -> int | None:
    """沿 Pydantic 的错误路径 ``loc`` 在 YAML node 树里下钻，返回能定位到的最深行号。

    例如 ``loc = ("scoring", "points", 2, 0)`` 会一路走到第 3 个控制点的第 1 个数字；
    走不下去就返回走到的最后一个节点的行号（比回退到整条规则的起始行精确得多）。
    """
    if node is None:
        return None
    current = node
    for part in loc:
        nxt: yaml.Node | None = None
        if isinstance(current, yaml.MappingNode) and isinstance(part, str):
            for key_node, value_node in current.value:
                if getattr(key_node, "value", None) == part:
                    nxt = value_node
                    break
        elif isinstance(current, yaml.SequenceNode) and isinstance(part, int):
            if 0 <= part < len(current.value):
                nxt = current.value[part]
        if nxt is None:
            break
        current = nxt
    return current.start_mark.line + 1


def _key_line(node: yaml.MappingNode | None, key: str) -> int | None:
    """某个 key **本身**所在的行（而不是它的值）。缺字段报错时指到这行更自然。"""
    if node is None or not isinstance(node, yaml.MappingNode):
        return None
    for key_node, _ in node.value:
        if getattr(key_node, "value", None) == key:
            return key_node.start_mark.line + 1
    return None


def _translate_pydantic_error(
    err: dict[str, Any],
    rule_node: yaml.MappingNode | None,
) -> Issue:
    """把一条 Pydantic 报错翻译成中文 Issue，并（有 node 时）定位到真实行号。"""
    loc = tuple(err["loc"])
    loc_text = ".".join(str(p) for p in loc)
    err_type = err["type"]
    raw_input = err.get("input")

    # 缺必填字段：指到整条规则的起始行（字段本来就不存在，没有行可指）。
    if err_type == "missing":
        name = str(loc[-1])
        return Issue(
            severity="error",
            code="MISSING_FIELD",
            message=f"缺少必填字段「{loc_text}」",
            fix=_MISSING_FIELD_FIX.get(name, GENERIC_FIX),
            line=rule_node.start_mark.line + 1 if rule_node else None,
        )

    # 未知字段：大概率是拼错了，给出最接近的候选。
    if err_type == "extra_forbidden":
        name = str(loc[-1])
        known = sorted(RuleDef.model_fields)
        close = difflib.get_close_matches(name, known, n=3, cutoff=0.5)
        hint = (
            "是不是想写 " + "、".join(f"`{c}`" for c in close) + "？"
            if close
            else "规则支持的字段见 rules/_template.yaml。"
        )
        return Issue(
            severity="error",
            code="UNKNOWN_FIELD",
            message=f"出现了无法识别的字段「{loc_text}」",
            fix=hint + "多余的字段会被当成错误而不是忽略，免得一条规则看起来生效其实没生效",
            line=_key_line(rule_node, name) or _line_of(rule_node, loc),
        )

    # ID 格式
    if err_type == "string_pattern_mismatch" and loc == ("id",):
        return Issue(
            severity="error",
            code="BAD_RULE_ID",
            message=f"规则 ID「{raw_input}」格式不对",
            fix=(
                "必须是一个大写字母 + 短横线 + 两位数字，例如 C-03、Q-01、K-12。"
                "文件里的规则前缀按维度选：合规用 C，品质用 Q，结构用 S，施工用 K，绿色用 G；"
                "同一维度可分多个主题文件。**运行期在界面上新增的规则用 X**（如 X-01），"
                "它们不来自文件、不进 git、不参与 CI 校验"
            ),
            line=_line_of(rule_node, loc),
        )

    # 枚举取值
    if err_type == "literal_error" and loc_text in _LITERAL_FIX:
        message, fix = _LITERAL_FIX[loc_text]
        if loc_text == "dimension" and isinstance(raw_input, str):
            close = difflib.get_close_matches(raw_input, list(VALID_DIMENSIONS), n=2, cutoff=0.4)
            if close:
                fix = "是不是想写 " + "、".join(f"`{c}`" for c in close) + f"？{fix}"
        return Issue(
            severity="error",
            code="BAD_ENUM_" + loc_text.replace(".", "_").upper(),
            message=f"{message}，当前写的是 {raw_input!r}",
            fix=fix,
            line=_line_of(rule_node, loc),
        )

    # 空字符串
    if err_type == "string_too_short":
        return Issue(
            severity="error",
            code="EMPTY_FIELD",
            message=f"「{loc_text}」不能留空",
            fix=_MISSING_FIELD_FIX.get(str(loc[-1]), GENERIC_FIX),
            line=_line_of(rule_node, loc),
        )

    # 权重必须为正数
    if err_type in ("greater_than", "greater_than_equal") and loc == ("weight_in_dimension",):
        return Issue(
            severity="error",
            code="BAD_WEIGHT",
            message=f"weight_in_dimension 必须是正数，当前是 {raw_input!r}",
            fix="权重是同维度内的相对值，写 1、2、0.5 这样的正数；不需要加起来等于 100",
            line=_line_of(rule_node, loc),
        )

    # 控制点形状不对
    if loc[:2] == ("scoring", "points"):
        if err_type in ("too_short", "too_long"):
            return Issue(
                severity="error",
                code="BAD_POINT_SHAPE",
                message=f"控制点「{loc_text}」必须正好是两个数字 [指标值, 分数]",
                fix="每一项写成 `- [0.50, 0]` 这样：第一个数是指标取值，第二个数是 0–100 的分数",
                line=_line_of(rule_node, loc),
            )
        if err_type in ("float_parsing", "float_type", "int_parsing"):
            return Issue(
                severity="error",
                code="POINT_NOT_NUMBER",
                message=f"控制点「{loc_text}」里出现了不是数字的值 {raw_input!r}",
                fix="控制点里只能写数字，不要加引号、单位或百分号；比例类写 0.82 而不是 82%",
                line=_line_of(rule_node, loc),
            )
        if err_type in ("less_than_equal", "greater_than_equal"):
            return Issue(
                severity="error",
                code="POINT_SCORE_OUT_OF_RANGE",
                message=(
                    f"控制点「{loc_text}」的分数 {raw_input!r} 超出了 {SCORE_MIN:g}–{SCORE_MAX:g}"
                ),
                fix=(
                    f"每个控制点的第二个数字是分数，必须在 {SCORE_MIN:g}–{SCORE_MAX:g} 之间；"
                    "比例类指标别把 0.82 写成 82 放到分数位上"
                ),
                line=_line_of(rule_node, loc),
            )
        if err_type in ("list_type", "tuple_type"):
            return Issue(
                severity="error",
                code="POINTS_NOT_LIST",
                message="scoring.points 必须是一个列表",
                fix="在 `points:` 下面另起一行，每个控制点写成 `- [0.50, 0]`",
                line=_line_of(rule_node, loc),
            )

    if err_type in ("model_type", "dict_type") and loc == ("scoring",):
        return Issue(
            severity="error",
            code="SCORING_NOT_OBJECT",
            message="scoring 必须是一个子对象",
            fix="`scoring:` 单独一行，下面缩进 2 空格写 `kind: piecewise` 和 `points:`",
            line=_line_of(rule_node, loc),
        )

    # 自定义校验器抛出的 ValueError：消息本身已经是中文，直接用。
    if err_type == "value_error":
        message = err["msg"].removeprefix("Value error, ")
        code = "RULE_SHAPE"
        fix = GENERIC_FIX
        if "严格递增" in message:
            code = "POINTS_NOT_MONOTONIC"
            fix = (
                "把控制点按第一个数字从小到大重排；"
                "「越小越好」靠分数递减表达，「适中最好」靠分数先升后降表达"
            )
        elif "分数" in message:
            code = "POINT_SCORE_OUT_OF_RANGE"
            fix = f"每个控制点的第二个数字改到 {SCORE_MIN:g}–{SCORE_MAX:g} 之间"
        elif "控制点" in message:
            code = "TOO_FEW_POINTS"
            fix = "至少写两个控制点，例如 `- [0.50, 0]` 和 `- [0.95, 100]`"
        elif "hard" in message or "metric" in message:
            code = "TYPE_FIELD_MISMATCH"
            fix = "对照 rules/_template.yaml：hard 用 check/message，metric 用 dimension/value/scoring"
        return Issue(
            severity="error",
            code=code,
            message=message,
            fix=fix,
            line=_line_of(rule_node, loc) or (rule_node.start_mark.line + 1 if rule_node else None),
        )

    # 兜底：照搬 Pydantic 的英文说明，但仍然给出位置和通用建议。
    return Issue(
        severity="error",
        code="INVALID_FIELD",
        message=f"字段「{loc_text}」取值不合法（{err['msg']}）",
        fix=GENERIC_FIX,
        line=_line_of(rule_node, loc),
    )


def _check_expressions(
    rule: RuleDef,
    rule_node: yaml.MappingNode | None,
    known: frozenset[str],
) -> list[Issue]:
    """静态检查规则里的表达式：语法 + 字段名是否存在。"""
    issues: list[Issue] = []
    for field_name, expression in rule.expressions():
        analyzed = analyze_expression(expression, field_name, known)
        for problem in analyzed.problems:
            issues.append(
                Issue(
                    severity="error",
                    code="BAD_EXPRESSION",
                    message=problem.message,
                    fix=problem.fix,
                    line=_line_of(rule_node, (field_name,)),
                    rule_id=rule.id,
                )
            )
    return issues


def _check_source_todo(rule: RuleDef, rule_node: yaml.MappingNode | None) -> list[Issue]:
    """``source`` 里还挂着 TODO：允许加载，但提醒出处没落实。"""
    if "TODO" not in rule.source:
        return []
    return [
        Issue(
            severity="warning",
            code="SOURCE_TODO",
            message="source 里还挂着 TODO，这条规则的出处尚未落实",
            fix=(
                "核对规范原文后把 source 换成「规范编号 第 X 条」，"
                "或写成「经验规则（XX组）：理由」。示例规则请一并去掉 name 的「【示例】」前缀"
            ),
            line=_line_of(rule_node, ("source",)),
            rule_id=rule.id,
        )
    ]


def check_rule_problems(
    raw: Any,
    *,
    node: yaml.MappingNode | None = None,
    known: frozenset[str] | None = None,
) -> list[Issue]:
    """校验一条规则（已解析成 dict），返回问题清单；空清单表示这条规则可用。

    Args:
        raw: 规则字典（来自 YAML，或界面提交的 JSON）。
        node: ``yaml.compose()`` 得到的 node，用于定位行号；界面提交时为 ``None``。
        known: 可在表达式里引用的字段名集合；默认取 :func:`known_field_names`。
            自定义字段（覆盖层）通过这里传进来。

    Returns:
        ``Issue`` 列表。``severity="error"`` 的必须改完才能加载。
    """
    known = known if known is not None else known_field_names()

    if not isinstance(raw, dict):
        return [
            Issue(
                severity="error",
                code="RULE_NOT_OBJECT",
                message="这一项不是一条规则",
                fix="每条规则写成 `id: C-01` 开头的对象，下面缩进 2 空格写其它字段",
                line=node.start_mark.line + 1 if node else None,
            )
        ]

    rule_id = raw.get("id") if isinstance(raw.get("id"), str) else None

    try:
        rule = RuleDef.model_validate(raw)
    except ValidationError as exc:
        issues: list[Issue] = []
        for err in exc.errors():
            issue = _translate_pydantic_error(err, node)
            issue.rule_id = rule_id
            if issue.line is None and node is not None:
                issue.line = node.start_mark.line + 1
            issues.append(issue)
        return issues

    issues = _check_expressions(rule, node, known)
    issues.extend(_check_source_todo(rule, node))
    return issues
