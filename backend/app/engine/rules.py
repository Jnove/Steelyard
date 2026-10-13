"""规则加载、校验与判定。

这是确定性引擎的核心：**完全不调用大模型**，同样的输入必然得到同样的输出。

三段职责
--------
1. **定义**：:class:`RuleDef` 用 Pydantic 正式描述 ``rules/*.yaml`` 里一条规则的形状，
   ``rules/`` 里写错什么都会在这里被拦下来。
2. **表达式**：``check`` / ``when`` / ``value`` 都是表达式，用 ``simpleeval`` 求值
   （**不用 ``eval``**）。加载时先做静态检查：解析 AST，确认每个名字都是已知字段、
   派生量或允许的函数，拼错了就用 ``difflib`` 给出最接近的候选。
3. **判定**：:func:`evaluate` 对每个方案跑一遍全部规则，产出合规清单、指标结果与维度得分。
   每条结果都带 ``rule_id`` / ``source`` / ``formula``，这是报告可溯源的基础。

缺数据的处理原则
----------------
表达式用到的字段为空时 **不抛异常**：hard 规则记 ``insufficient_data``，
metric 规则不计分，并记下缺哪些字段。判断依据是"表达式**引用**到的字段有没有值"，
而不是"求值时有没有真的用到"——``floors > 10 and elevators_per_unit >= 2`` 在
``floors == 5`` 时按 Python 短路语义其实不需要电梯数，但我们仍然判为数据不足。
这样做的理由是结果可解释：告诉规则作者"你没填 elevators_per_unit 所以这条判不了"
比"这条有时判得了有时判不了"更容易接受，也与求值顺序无关。
"""

from __future__ import annotations

import ast
import difflib
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from simpleeval import InvalidExpression, SimpleEval

from app.engine.metrics import (
    DERIVED_BY_NAME,
    DerivedValue,
    compute_derived,
    derived_names,
)
from app.engine.regions import GB_PACK, is_region_code
from app.engine.scoring import (
    MIN_POINTS,
    SCORE_MAX,
    SCORE_MIN,
    describe_piecewise,
    piecewise_score,
)
from app.models.eval import (
    ComplianceItem,
    DimensionCoverage,
    DimensionKey,
    DimensionScores,
    EvalResult,
    MetricResult,
)
from app.models.params import ProjectParams, SchemeParams

__all__ = [
    "ALLOWED_FUNCTIONS",
    "DIMENSION_KEYS",
    "RULE_ID_PATTERN",
    "ExpressionProblem",
    "RuleDef",
    "RuleLoadError",
    "RuleSet",
    "SchemeInput",
    "ScorePoint",
    "ScoringDef",
    "analyze_expression",
    "build_namespace",
    "evaluate",
    "get_ruleset",
    "known_field_names",
    "load_rules_from_dir",
    "reload_ruleset",
    "rewrite_contains",
    "set_ruleset_for_testing",
]

# —— 常量 —— #

#: 规则 ID 的形态：
#:
#: * **国家层面标准**（默认册 ``GB``）：一个大写前缀字母 + 短横线 + 两位数字。
#:   前缀 C=compliance、Q=quality、S=structure、K=construction、G=green。
#: * **地方标准**（省级册）：两字母地区码 + 短横线 + 同一个维度字母 + 短横线 + 两位数字，
#:   例如 ``ZJ-S-01``（浙江省册的结构规则）。地区码见 ``app/engine/regions.py``。
#: * **X** 是运行期自定义规则的保留前缀（见 ``app/custom/rules.py``）：模式里允许它，
#:   但 ``scripts/check_rules.py`` 会禁止它出现在 ``rules/*.yaml`` 里——X- 只能来自
#:   界面上临时加的规则，不能落进 git。
#:
#: 为什么地方规则要带地区码：多省的同类规则会撞号（两位数只有 99 个），
#: 而报告里每条结论都要能顺着编号回查来源——``ZJ-S-01`` 一眼就知道出自浙江册。
RULE_ID_PATTERN = r"^(?:[CQSKGX]|[A-Z]{2}-[CQSKG])-\d{2}$"

#: 表达式里允许调用的函数。**只有这五个**，其余一律报错。
#: 不放 ``sum`` / ``sorted`` 之类是因为规则里用不到，而每多一个就多一份出错与滥用的可能。
ALLOWED_FUNCTIONS: dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "len": len,
}

#: 只有这两个明确的字典字段允许用固定字符串键取值；其他对象不开放下标。
DICTIONARY_FIELDS = frozenset({"window_wall_ratio", "unit_mix"})

#: 四个评估维度，与 ``app/models/eval.py`` 的 ``DimensionKey`` 保持一致。
DIMENSION_KEYS: tuple[DimensionKey, ...] = ("quality", "structure", "construction", "green")

#: ``rules/`` 下不作为规则列表处理的文件：``weights.yaml`` 是 AHP 角色权重模板（T4 用）。
NON_RULE_FILENAMES = frozenset({"weights.yaml", "weights.yml"})


# —— 表达式：``contains`` 语法糖 —— #

# 规则编写指南（docs/rules-guide.md §3.1）向非程序员承诺了 ``contains`` 运算符，
# 因为 "risk_features contains '深基坑'" 比 Python 原生的 "'深基坑' in risk_features"
# 更接近中文语序。但 ``contains`` 不是 Python 语法，ast.parse 会直接 SyntaxError，
# 所以在解析之前先把它改写成 ``in``。改写对用户完全透明。
_TOKEN_RE = re.compile(
    r"""
      (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    | (?P<name>[^\W\d]\w*)
    | (?P<number>\d+\.?\d*(?:[eE][+-]?\d+)?)
    | (?P<lparen>[(\[])
    | (?P<rparen>[)\]])
    | (?P<ws>\s+)
    | (?P<other>.)
    """,
    re.VERBOSE | re.UNICODE,
)

#: 走到这些词就认为一个操作数结束了（它们的优先级低于 ``contains``）。
_OPERAND_STOP_WORDS = frozenset({"and", "or", "not", "if", "else"})


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str


def _tokenize(expr: str) -> list[_Token]:
    return [_Token(kind=m.lastgroup or "other", text=m.group()) for m in _TOKEN_RE.finditer(expr)]


def _operand_bounds(tokens: Sequence[_Token], pivot: int, direction: int) -> tuple[int, int]:
    """从 ``contains``（下标 ``pivot``）向一侧扫出一个完整操作数的 token 下标区间。

    Args:
        tokens: 全部 token。
        pivot: ``contains`` 所在下标。
        direction: ``-1`` 向左扫，``+1`` 向右扫。

    Returns:
        ``(start, end)``，半开区间 ``tokens[start:end]`` 即该操作数。

    扫描在下面三种情况停下：碰到括号深度变负（说明操作数被外层括号包住了）、
    碰到 ``and`` / ``or`` 这类低优先级关键字、或者到达表达式边界。
    """
    depth = 0
    index = pivot + direction
    last = pivot
    while 0 <= index < len(tokens):
        token = tokens[index]
        if token.kind == "lparen":
            depth += 1 if direction > 0 else -1
        elif token.kind == "rparen":
            depth -= 1 if direction > 0 else -1
        if depth < 0:
            break
        if depth == 0 and token.kind == "name" and token.text in _OPERAND_STOP_WORDS:
            break
        # 顶层的比较 / 布尔运算符也终止操作数，避免把 "a contains 'x' == True" 吞掉。
        if depth == 0 and token.kind == "other" and token.text in {",", "=", "<", ">", "!"}:
            break
        if token.kind != "ws":
            last = index
        index += direction

    if direction > 0:
        return pivot + 1, last + 1
    return last, pivot


def rewrite_contains(expr: str) -> str:
    """把 ``A contains B`` 改写成 ``(B) in (A)``，其余部分原样保留。

    支持与 ``and`` / ``or`` 组合，也支持一个表达式里出现多次。

    示例：
        >>> rewrite_contains("risk_features contains '深基坑'")
        "('深基坑') in (risk_features)"
        >>> rewrite_contains("floors > 3 and risk_features contains '高支模'")
        "floors > 3 and ('高支模') in (risk_features)"
    """
    result = expr
    # 每轮只改写最左边的一个 ``contains``，改完重新 tokenize，避免下标失效。
    for _ in range(result.count("contains") + 1):
        tokens = _tokenize(result)
        pivot = next(
            (i for i, t in enumerate(tokens) if t.kind == "name" and t.text == "contains"),
            None,
        )
        if pivot is None:
            break
        left_start, left_end = _operand_bounds(tokens, pivot, -1)
        right_start, right_end = _operand_bounds(tokens, pivot, +1)
        if left_end <= left_start or right_end <= right_start:
            # 一侧没有操作数（例如以 contains 开头），交给 ast.parse 去报语法错误。
            break
        head = "".join(t.text for t in tokens[:left_start])
        left = "".join(t.text for t in tokens[left_start:left_end]).strip()
        right = "".join(t.text for t in tokens[right_start:right_end]).strip()
        tail = "".join(t.text for t in tokens[right_end:])
        result = f"{head}({right}) in ({left}){tail}"
    return result


# —— 表达式：静态检查 —— #

#: 表达式里允许出现的 AST 节点。白名单而不是黑名单，新语法默认禁止。
_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.IfExp,
    ast.Call,
    ast.List,
    ast.Tuple,
    ast.Subscript,
)

#: AST 节点 → 中文说明，用于"不允许的写法"报错。
_NODE_LABELS: dict[str, str] = {
    "Attribute": "属性访问（形如 a.b）",
    "Subscript": "下标取值（形如 a[b]）",
    "Lambda": "匿名函数（lambda）",
    "ListComp": "列表推导式",
    "SetComp": "集合推导式",
    "DictComp": "字典推导式",
    "GeneratorExp": "生成器表达式",
    "Dict": "字典字面量（形如 {a: b}）",
    "Set": "集合字面量",
    "JoinedStr": "f-字符串",
    "Starred": "星号展开（形如 *a）",
    "NamedExpr": "海象赋值（形如 a := b）",
    "Await": "await",
}


@dataclass(frozen=True)
class ExpressionProblem:
    """表达式静态检查发现的一个问题。

    ``message`` 是"错在哪"，``fix`` 是"怎么改"——两段都要能让非程序员看懂。
    """

    field: str
    expression: str
    message: str
    fix: str


@dataclass(frozen=True)
class AnalyzedExpression:
    """一次静态检查的结果。"""

    names: frozenset[str]
    problems: tuple[ExpressionProblem, ...]
    dictionary_keys: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems


def known_field_names(extra: Iterable[str] = ()) -> frozenset[str]:
    """全部可在表达式里引用的名字：项目层 + 方案层 + 派生量（+ 调用方补充的名字）。

    Args:
        extra: 额外允许引用的名字。**运行期自定义字段**从这里传进来
            （见 ``app/custom/fields.py`` 的 ``known_names``）：内建规则不该引用它们
            ——``check_rules`` 是纯文件校验、看不到覆盖层——但自定义规则可以。

    Raises:
        RuntimeError: 项目层与方案层出现同名字段。命名空间是直接合并的，
            重名会让规则作者说不清自己引用的是哪一个，属于必须立刻修掉的设计错误。
    """
    project = set(ProjectParams.model_fields)
    scheme = set(SchemeParams.model_fields)
    overlap = project & scheme
    if overlap:
        raise RuntimeError(
            f"项目层与方案层存在同名字段 {sorted(overlap)}，命名空间无法直接合并；"
            "请在 app/models/params.py 里给其中一个改名"
        )
    return frozenset(project | scheme | derived_names() | set(extra))


def _suggest(name: str, candidates: Iterable[str]) -> str:
    """给拼错的字段名找最接近的候选，拼成"怎么改"的话术。"""
    matches = difflib.get_close_matches(name, sorted(candidates), n=3, cutoff=0.5)
    if matches:
        quoted = "、".join(f"`{m}`" for m in matches)
        return f"是不是想写 {quoted}？完整字段表见 docs/fields.generated.md"
    return "请对照 docs/fields.generated.md 的字段对照表确认字段名"


def _dictionary_access(node: ast.AST) -> tuple[str, str] | None:
    """识别 ``已知字典字段['固定键']``，不接受变量、嵌套或其他对象。"""
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in DICTIONARY_FIELDS
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    ):
        return node.value.id, node.slice.value
    return None


def analyze_expression(
    expression: str,
    field_name: str,
    known: frozenset[str] | None = None,
) -> AnalyzedExpression:
    """静态检查一个表达式：语法、允许的写法、名字是否已知。

    Args:
        expression: 原始表达式（未改写 ``contains`` 的版本，报错时照原文显示）。
        field_name: 该表达式所在的字段名（``check`` / ``when`` / ``value``），用于报错定位。
        known: 已知名字集合；默认取 :func:`known_field_names`。

    Returns:
        :class:`AnalyzedExpression`，含表达式引用到的字段名集合与问题清单。
    """
    allowed = known if known is not None else known_field_names()
    rewritten = rewrite_contains(expression)

    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError as exc:
        return AnalyzedExpression(
            names=frozenset(),
            problems=(
                ExpressionProblem(
                    field=field_name,
                    expression=expression,
                    message=f"{field_name} 表达式写法不合语法：{exc.msg}",
                    fix=(
                        "检查括号是否成对、引号是否成对、比较符是否写全"
                        "（要写 >= 不能写 =>）；判断相等要写两个等号 =="
                    ),
                ),
            ),
        )

    problems: list[ExpressionProblem] = []
    names: set[str] = set()
    dictionary_keys: set[tuple[str, str]] = set()
    # 被当成函数调用的名字。先收一遍，免得 ``sum(...)`` 既报"函数不允许"
    # 又报"不是已知字段"——同一处失误报两遍只是噪音。
    called: set[str] = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            label = _NODE_LABELS.get(type(node).__name__, type(node).__name__)
            problems.append(
                ExpressionProblem(
                    field=field_name,
                    expression=expression,
                    message=f"{field_name} 表达式里用了不允许的写法：{label}",
                    fix=(
                        "规则表达式只支持四则运算、比较、and/or/not、contains，"
                        f"以及 {'、'.join(sorted(ALLOWED_FUNCTIONS))} 这几个函数；"
                        "更复杂的计算请提给开发组加成派生量"
                    ),
                )
            )
            continue

        if isinstance(node, ast.Subscript):
            access = _dictionary_access(node)
            if access is None:
                problems.append(
                    ExpressionProblem(
                        field=field_name,
                        expression=expression,
                        message=f"{field_name} 表达式里用了不允许的下标取值",
                        fix=(
                            "只支持 window_wall_ratio['南']、unit_mix['两室'] 这样的"
                            "已知字典字段与固定字符串键；不能用变量键、数字、切片、"
                            "嵌套下标、属性或函数返回值取下标"
                        ),
                    )
                )
            else:
                dictionary_keys.add(access)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                problems.append(
                    ExpressionProblem(
                        field=field_name,
                        expression=expression,
                        message=f"{field_name} 表达式里出现了无法识别的函数调用",
                        fix=f"只能调用 {'、'.join(sorted(ALLOWED_FUNCTIONS))}",
                    )
                )
            elif node.func.id not in ALLOWED_FUNCTIONS:
                close = difflib.get_close_matches(
                    node.func.id, sorted(ALLOWED_FUNCTIONS), n=2, cutoff=0.5
                )
                hint = (
                    "是不是想写 " + "、".join(f"`{c}`" for c in close) + "？"
                    if close
                    else "需要更复杂的计算请提给开发组加成派生量。"
                )
                problems.append(
                    ExpressionProblem(
                        field=field_name,
                        expression=expression,
                        message=f"{field_name} 表达式调用了不允许的函数 `{node.func.id}`",
                        fix=f"{hint}只能调用 {'、'.join(sorted(ALLOWED_FUNCTIONS))}",
                    )
                )
        elif isinstance(node, ast.Name):
            # 函数名已在 Call 分支里单独校验过，不再当字段名处理。
            if node.id in called:
                continue
            if node.id in allowed:
                names.add(node.id)
            else:
                problems.append(
                    ExpressionProblem(
                        field=field_name,
                        expression=expression,
                        message=f"{field_name} 表达式里的 `{node.id}` 不是已知字段或派生量",
                        fix=_suggest(node.id, allowed),
                    )
                )

    return AnalyzedExpression(
        names=frozenset(names),
        problems=tuple(problems),
        dictionary_keys=tuple(sorted(dictionary_keys)),
    )


def _make_evaluator(namespace: Mapping[str, Any]) -> SimpleEval:
    """构造一个只认识指定命名空间与五个允许函数的求值器。

    用 ``simpleeval`` 而不是内置 ``eval``：它只实现了一个受限的表达式子集，
    拿不到 ``__builtins__``，也无法 import 或访问属性。
    """
    return SimpleEval(functions=dict(ALLOWED_FUNCTIONS), names=dict(namespace), allowed_attrs={})


# —— 规则定义 —— #


#: 控制点的分数分量。用 ``Annotated`` 约束而不是在校验器里手写循环，
#: 是为了让 Pydantic 的错误路径带上**具体是第几个控制点**（形如
#: ``scoring.points.1.1``），check_rules 就能把行号指到出错的那一行。
ScorePoint = Annotated[float, Field(ge=SCORE_MIN, le=SCORE_MAX)]


class ScoringDef(BaseModel):
    """metric 规则的评分定义。目前只有分段线性一种。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["piecewise"] = Field(description="评分方式；现阶段只支持 piecewise（分段线性）")
    points: list[tuple[float, ScorePoint]] = Field(
        description="控制点列表，每项 [指标值, 分数]；指标值严格递增，分数在 0–100 之间"
    )

    @field_validator("points")
    @classmethod
    def _check_points(cls, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """校验控制点的数量与横坐标严格递增（分数范围由 :data:`ScorePoint` 负责）。

        注意这里 **不要求纵坐标单调**：先升后降正是"适中最好"型指标的写法。
        """
        if len(points) < MIN_POINTS:
            raise ValueError(
                f"scoring.points 至少要有 {MIN_POINTS} 个控制点，当前只有 {len(points)} 个"
                "——两个点才能连成一条线"
            )
        xs = [x for x, _ in points]
        for i in range(1, len(xs)):
            if xs[i] <= xs[i - 1]:
                raise ValueError(
                    f"scoring.points 的指标值（每项第一个数）必须严格递增，当前是 {xs}；"
                    "「越小越好」的指标也要按指标值从小到大排，靠分数递减来表达"
                )
        return points


def _region_prefix(rule_id: str) -> str | None:
    """取出地方规则 ID 里的地区码；国家层面与运行期规则返回 ``None``。

    ``ZJ-S-01`` → ``"ZJ"``；``S-08`` → ``None``；``X-01`` → ``None``。
    """
    parts = rule_id.split("-")
    return parts[0] if len(parts) == 3 else None


class RuleDef(BaseModel):
    """``rules/*.yaml`` 里一条规则的正式定义。

    两类规则共用 ``id`` / ``name`` / ``type`` / ``source``，其余字段按 ``type`` 分：

    - ``hard``（硬约束）：``check`` 必填，可选 ``message`` / ``severity``；
    - ``metric``（评分指标）：``dimension`` / ``value`` / ``scoring`` 必填，
      ``weight_in_dimension`` 默认 1。

    ``extra="forbid"`` 是刻意的：规则由非程序员编写，字段名打错时宁可直接报错，
    也不要静默忽略——静默忽略会让一条规则看起来生效了其实没生效。
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        pattern=RULE_ID_PATTERN,
        description=(
            "规则编号：国家层面标准形如 C-03（全局唯一），地方标准形如 ZJ-S-01"
            "（地区码 + 维度字母 + 两位数字）"
        ),
    )
    pack: str = Field(
        GB_PACK,
        description=(
            "规则所属的「册」：GB 是国家标准册（永远生效），其余是省级册"
            "（默认关闭，由项目选择）。地方规则的 ID 地区码必须与本字段一致"
        ),
    )
    name: str = Field(min_length=1, description="规则中文名，给前端与报告看")
    type: Literal["hard", "metric"] = Field(description="hard 硬约束 / metric 评分指标")
    source: str = Field(min_length=1, description="条文或经验出处，报告里会原样引用")
    when: str | None = Field(
        None,
        description="可选守卫表达式；为假时该规则不适用，状态记为 not_applicable",
    )

    # —— hard 专属 —— #
    check: str | None = Field(None, description="hard 规则的布尔表达式，为假即不通过")
    message: str | None = Field(
        None,
        description="不通过时的说明，可用 {字段名} 占位实际取值",
    )
    severity: Literal["error", "warning"] = Field(
        "error", description="hard 规则的严重程度；error 标红并踢出排名，warning 仅提示"
    )

    # —— metric 专属 —— #
    dimension: DimensionKey | None = Field(None, description="metric 所属维度")
    value: str | None = Field(None, description="metric 的取值：字段名或表达式")
    scoring: ScoringDef | None = Field(None, description="metric 的评分定义")
    weight_in_dimension: float = Field(1.0, gt=0, description="同维度内的相对权重，正数，默认 1")

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> RuleDef:
        """按 ``type`` 校验必填项，并挡住"写串了"的组合。"""
        if self.type == "hard":
            if not (self.check or "").strip():
                raise ValueError(
                    "hard 规则必须写 check 表达式（违反即不通过），"
                    '例如 check: "floor_height >= 3.0"'
                )
            wrong = [
                key for key in ("dimension", "value", "scoring") if getattr(self, key) is not None
            ]
            if wrong:
                raise ValueError(
                    f"hard 规则不应该有 {'、'.join(wrong)} 字段（那是 metric 规则的）；"
                    "如果这条本来想写成评分指标，请把 type 改成 metric"
                )
        else:  # metric
            missing = [
                key for key in ("dimension", "value", "scoring") if getattr(self, key) is None
            ]
            if missing:
                raise ValueError(
                    f"metric 规则缺少必填字段 {'、'.join(missing)}；"
                    "dimension 从 quality / structure / construction / green 里选，"
                    "value 写字段名或表达式，scoring 写 kind: piecewise 与 points"
                )
            if not (self.value or "").strip():
                raise ValueError(
                    'metric 规则的 value 不能是空字符串，例如 value: "std_floor_repeat"'
                )
            if self.check is not None or self.message is not None:
                raise ValueError(
                    "metric 规则不应该有 check / message 字段（那是 hard 规则的）；"
                    "如果这条本来想写成硬约束，请把 type 改成 hard"
                )
        return self

    @model_validator(mode="after")
    def _check_pack_matches_id(self) -> RuleDef:
        """``pack``（册）与 ID 里的地区码必须一致，且册代码必须真实存在。

        地方规则的编号形如 ``ZJ-S-01``，册就是它出自哪一省。两者不一致时，
        报告会把结论归错来源；册代码不在注册表里时，项目永远选不中它
        （规则等于白写）。所以这两种情况都直接拒绝加载。
        """
        if not is_region_code(self.pack):
            raise ValueError(
                f"未知的册代码 {self.pack!r}；可用 GB 或省级地区码"
                "（见 app/engine/regions.py 的 MAINLAND_PROVINCES）"
            )
        region = _region_prefix(self.id)
        if region is None:
            if self.pack != GB_PACK:
                raise ValueError(
                    f"规则 ID {self.id} 没有地区码，但 pack 是 {self.pack}；"
                    f"地方规则的 ID 应形如 {self.pack}-S-01"
                )
        elif region != self.pack:
            raise ValueError(
                f"规则 ID {self.id} 的地区码是 {region}，与 pack={self.pack} 不一致；"
                "两者必须相同，否则报告会把来源归错"
            )
        return self

    def expressions(self) -> Iterator[tuple[str, str]]:
        """遍历本条规则里的全部表达式，产出 ``(字段名, 表达式)``。"""
        if self.when is not None:
            yield "when", self.when
        if self.check is not None:
            yield "check", self.check
        if self.type == "metric" and self.value is not None:
            yield "value", self.value


# —— 规则集 —— #


class RuleLoadError(Exception):
    """加载 ``rules/`` 失败。``problems`` 是给人看的中文说明列表。"""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("规则加载失败：\n" + "\n".join(f"  - {p}" for p in self.problems))


@dataclass(frozen=True)
class RuleSet:
    """一次加载得到的全部规则。"""

    rules: tuple[RuleDef, ...]
    #: 规则 ID → 来源文件名（不含目录），供 ``GET /api/rules`` 展示。
    origins: Mapping[str, str]
    #: ``source`` 里含 TODO 的规则 ID；这些规则能加载，但出处还没落实。
    todo_source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        duplicates = [r.id for r in self.rules if [x.id for x in self.rules].count(r.id) > 1]
        if duplicates:
            raise RuleLoadError([f"规则 ID 重复：{sorted(set(duplicates))}"])

    @property
    def hard_rules(self) -> tuple[RuleDef, ...]:
        return tuple(r for r in self.rules if r.type == "hard")

    @property
    def metric_rules(self) -> tuple[RuleDef, ...]:
        return tuple(r for r in self.rules if r.type == "metric")

    def by_id(self, rule_id: str) -> RuleDef | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    @property
    def packs(self) -> tuple[str, ...]:
        """当前规则集里出现过的册（排序后），供册清单接口使用。"""
        return tuple(sorted({r.pack for r in self.rules}))

    def select_packs(self, codes: Iterable[str]) -> RuleSet:
        """按册筛选出一个**新的**规则集。

        ``GB`` 是底线，调用方应保证它总在 ``codes`` 里（``ProjectParams`` 的校验器
        已经强制这一点）。返回新对象而不改动自身：全局缓存的那份永远包含全部册，
        切换册不该改变它——否则一个项目开了地方册，会顺手影响另一个项目。
        """
        wanted = set(codes)
        rules = tuple(r for r in self.rules if r.pack in wanted)
        if len(rules) == len(self.rules):
            return self
        keep = {r.id for r in rules}
        return RuleSet(
            rules=rules,
            origins={k: v for k, v in self.origins.items() if k in keep},
            todo_source_ids=tuple(i for i in self.todo_source_ids if i in keep),
        )


def iter_rule_files(rules_dir: Path) -> list[Path]:
    """列出 ``rules_dir`` 下需要当作规则列表处理的 YAML 文件。

    跳过两类文件：下划线开头的（``_template.yaml`` 这类模板与草稿），
    以及 ``weights.yaml``（AHP 角色权重模板，不是规则列表）。
    """
    if not rules_dir.is_dir():
        return []
    files = [
        p
        for p in sorted(rules_dir.iterdir())
        if p.is_file()
        and p.suffix in (".yaml", ".yml")
        and not p.name.startswith("_")
        and p.name not in NON_RULE_FILENAMES
    ]
    return files


#: Pydantic 内置约束的报错是英文的，这里给规则作者可能碰到的几种补上中文。
#: 自定义校验器抛的 ``value_error`` 本身就是中文，不在这张表里。
_CONSTRAINT_MESSAGES_ZH: dict[str, str] = {
    "less_than_equal": f"取值超出上限（分数必须在 {SCORE_MIN:g}–{SCORE_MAX:g} 之间）",
    "greater_than_equal": f"取值超出下限（分数必须在 {SCORE_MIN:g}–{SCORE_MAX:g} 之间）",
    "greater_than": "取值必须是正数",
    "string_pattern_mismatch": "格式不对（规则 ID 形如 C-03：一个大写字母 C/Q/S/K/G + 短横线 + 两位数字）",
    "string_too_short": "不能留空",
    "extra_forbidden": "不是规则支持的字段（拼错了，或者写到了不该写的地方）",
    "missing": "缺少这个必填字段",
    "literal_error": "取值不在允许的枚举里",
}


def _format_validation_error(exc: ValidationError, rule_id: str, filename: str) -> list[str]:
    """把 Pydantic 的报错翻译成一句中文说明。

    这里只做简版翻译：``scripts/check_rules.py`` 有完整的翻译表（带真实行号与"怎么改"），
    引擎侧只需要在加载失败时给出足够定位的信息，并保证话是中文的。
    """
    out: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "(整条规则)"
        zh = _CONSTRAINT_MESSAGES_ZH.get(err["type"])
        detail = zh or err["msg"].removeprefix("Value error, ")
        out.append(f"{filename} 规则 {rule_id} 的 {loc}：{detail}")
    return out


def load_rules_from_dir(rules_dir: Path) -> RuleSet:
    """加载并校验一个目录下的全部规则。

    Args:
        rules_dir: ``rules/`` 目录。

    Returns:
        校验通过的 :class:`RuleSet`。

    Raises:
        RuleLoadError: 任一文件有语法错误、字段错误、ID 重复或表达式引用了未知字段。
            报错信息是中文的，但**定位不含行号**——需要行号请跑
            ``scripts/check_rules.py``，它是专门给规则作者用的。
    """
    known = known_field_names()
    problems: list[str] = []
    rules: list[RuleDef] = []
    origins: dict[str, str] = {}
    todo_ids: list[str] = []
    seen: dict[str, str] = {}  # rule_id → 首次出现的文件名

    for path in iter_rule_files(rules_dir):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            problems.append(f"{path.name} YAML 解析失败：{str(exc).splitlines()[0]}")
            continue

        if raw is None:
            continue
        if not isinstance(raw, list):
            problems.append(
                f"{path.name} 顶层必须是规则列表（每条以 `- id:` 开头），"
                f"实际是 {type(raw).__name__}"
            )
            continue

        for index, item in enumerate(raw, start=1):
            label = f"第 {index} 条"
            if not isinstance(item, dict):
                problems.append(
                    f"{path.name} {label} 不是一条规则（应当是 `- id: ...` 这样的对象）"
                )
                continue
            rule_id = str(item.get("id", label))
            try:
                rule = RuleDef.model_validate(item)
            except ValidationError as exc:
                problems.extend(_format_validation_error(exc, rule_id, path.name))
                continue

            if rule.id in seen:
                problems.append(
                    f"规则 ID {rule.id} 重复：{seen[rule.id]} 与 {path.name} 里各有一条"
                )
                continue
            seen[rule.id] = path.name

            for field_name, expression in rule.expressions():
                analyzed = analyze_expression(expression, field_name, known)
                problems.extend(
                    f"{path.name} 规则 {rule.id}：{p.message}（{p.fix}）" for p in analyzed.problems
                )

            rules.append(rule)
            origins[rule.id] = path.name
            if "TODO" in rule.source:
                todo_ids.append(rule.id)

    if problems:
        raise RuleLoadError(problems)

    return RuleSet(rules=tuple(rules), origins=origins, todo_source_ids=tuple(todo_ids))


# —— 全局规则集（启动时加载，开发环境可热重载） —— #

_RULESET: RuleSet | None = None


def default_rules_dir() -> Path:
    """默认规则目录：仓库根下的 ``rules/``。

    ``app/engine/rules.py`` → parents: engine → app → backend → 仓库根。
    """
    return Path(__file__).resolve().parents[3] / "rules"


def get_ruleset() -> RuleSet:
    """取全局规则集；首次调用时从默认目录加载。"""
    global _RULESET
    if _RULESET is None:
        _RULESET = load_rules_from_dir(default_rules_dir())
    return _RULESET


def reload_ruleset(rules_dir: Path | None = None) -> RuleSet:
    """重新加载规则集（``POST /api/rules/reload`` 用）。加载失败时保留原有规则集。"""
    global _RULESET
    fresh = load_rules_from_dir(rules_dir or default_rules_dir())
    _RULESET = fresh
    return fresh


def set_ruleset_for_testing(ruleset: RuleSet | None) -> None:
    """测试用：直接注入（或用 ``None`` 清空）全局规则集。"""
    global _RULESET
    _RULESET = ruleset


# —— 判定 —— #


@dataclass(frozen=True)
class SchemeInput:
    """参与评估的一个方案。"""

    scheme_id: str
    name: str
    params: SchemeParams


@dataclass(frozen=True)
class Namespace:
    """一个方案的求值命名空间。"""

    values: Mapping[str, Any]
    derived: Mapping[str, DerivedValue]

    def missing_for(
        self, names: Iterable[str], dictionary_keys: Iterable[tuple[str, str]] = ()
    ) -> tuple[str, ...]:
        """给定表达式引用到的名字，返回"缺哪些原始字段"。

        派生量会被展开成它依赖的原始字段——对规则作者来说，"缺 volume"
        比"缺 shape_coef"更可操作（后者本来就不是他填的）。
        """
        missing: list[str] = []
        for name in sorted(names):
            derived = self.derived.get(name)
            if derived is not None:
                if not derived.is_available:
                    missing.extend(d for d in derived.missing_fields if d not in missing)
                continue
            if self.values.get(name) is None and name not in missing:
                missing.append(name)
        # 与普通字段一样，检查所有引用的键，即使它位于不会执行的短路分支。
        for name, key in sorted(dictionary_keys):
            if name in missing:
                continue
            container = self.values.get(name)
            if not isinstance(container, dict) or container.get(key) is None:
                missing.append(f"{name}[{key!r}]")
        return tuple(missing)


def build_namespace(
    project: ProjectParams, scheme: SchemeParams, *, custom_names: Iterable[str] | None = None
) -> Namespace:
    """合并项目层字段、方案层字段、派生量与自定义字段，构成表达式命名空间。

    字段名不重复（由 :func:`known_field_names` 在加载阶段保证），所以直接合并。

    ``SchemeParams.custom`` 里的**自定义字段**（运行期覆盖层，见 ``app/custom/``）
    在这里摊平到顶层：规则作者不必写 ``custom['my_field']``，直接写 ``my_field``。
    用 ``setdefault`` 合并，所以**内建字段永远优先**，自定义字段不可能把它顶掉
    （注册表写入时也已拒绝与内建重名，这里是第二道保险）。
    """
    values: dict[str, Any] = {**project.model_dump(), **scheme.model_dump()}
    custom = values.get("custom")
    if isinstance(custom, dict):
        for key, value in custom.items():
            if custom_names is None or key in custom_names:
                values.setdefault(str(key), value)
    derived = compute_derived(values)
    values.update({name: dv.value for name, dv in derived.items()})
    return Namespace(values=values, derived=derived)


def _eval_expression(
    expression: str, namespace: Namespace, known: frozenset[str] | None = None
) -> Any:
    """求值一个表达式。调用方负责先判缺数据，所以这里不处理 ``None`` 参与运算的情况。"""
    # 求值入口也检查白名单，防止直接构造 RuleSet 绕过文件加载时的静态检查。
    analyzed = analyze_expression(expression, "expression", known)
    if not analyzed.ok:
        raise InvalidExpression("；".join(problem.message for problem in analyzed.problems))
    evaluator = _make_evaluator(namespace.values)
    return evaluator.eval(rewrite_contains(expression))


_COMPARE_SYMBOLS: dict[type[ast.cmpop], str] = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}


def _extract_limit(check: str) -> tuple[str | None, str | None]:
    """从形如 ``floor_height >= 3.0`` 的 check 里抽出"限值"与"被比较的字段"。

    这是尽力而为的：抽不出来就返回 ``(None, None)``，只影响结果里 ``limit`` / ``value``
    两个展示字段，不影响判定。报告里有 ``limit`` 时读起来像"层高 2.9 m，要求 >= 3.0"。
    """
    try:
        tree = ast.parse(rewrite_contains(check), mode="eval")
    except SyntaxError:
        return None, None
    node = tree.body
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return None, None
    symbol = _COMPARE_SYMBOLS.get(type(node.ops[0]))
    if symbol is None:
        return None, None
    left, right = node.left, node.comparators[0]
    if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
        return f"{symbol} {right.value}", left.id
    if isinstance(left, ast.Constant) and isinstance(right, ast.Name):
        # 反向写法 ``3.0 <= floor_height``：把限值也反过来表述，避免读者误解方向。
        flipped = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}[symbol]
        return f"{flipped} {left.value}", right.id
    return None, None


_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]\w*)\}")


def _format_message(template: str, namespace: Namespace) -> str:
    """把 ``message`` 里的 ``{字段名}`` 换成实际取值。

    未知字段或空值保持花括号原样，这样规则作者一眼能看出"这里没取到值"，
    而不是收到一条 KeyError 堆栈。
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in namespace.values:
            return match.group(0)
        value = namespace.values[name]
        if value is None:
            return match.group(0)
        if isinstance(value, float):
            return f"{round(value, 4):g}"
        return str(value)

    return _PLACEHOLDER_RE.sub(replace, template)


def _applicability(
    rule: RuleDef, namespace: Namespace, known: frozenset[str]
) -> tuple[Literal["yes", "no", "unknown"], tuple[str, ...]]:
    """判断一条带 ``when`` 的规则是否适用。

    Returns:
        ``("yes", ())`` 适用；``("no", ())`` 不适用；
        ``("unknown", 缺失字段)`` 因为 ``when`` 用到的字段没填而判不了。
    """
    if rule.when is None:
        return "yes", ()
    analyzed = analyze_expression(rule.when, "when", known)
    missing = namespace.missing_for(analyzed.names, analyzed.dictionary_keys)
    if missing:
        return "unknown", missing
    try:
        return ("yes" if _eval_expression(rule.when, namespace, known) else "no"), ()
    except (InvalidExpression, TypeError, ValueError, ZeroDivisionError):
        # when 求值出错按"判不了"处理，而不是让整次评估失败。
        return "unknown", ()


def _evaluate_hard(rule: RuleDef, namespace: Namespace, known: frozenset[str]) -> ComplianceItem:
    """判定一条硬约束。"""
    limit, value_field = _extract_limit(rule.check or "")
    raw_value = namespace.values.get(value_field) if value_field else None
    numeric_value = (
        float(raw_value)
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool)
        else None
    )
    common = {
        "rule_id": rule.id,
        "name": rule.name,
        "limit": limit,
        "source": rule.source,
        "severity": rule.severity,
        "formula": rule.check or "",
    }

    applicable, when_missing = _applicability(rule, namespace, known)
    if applicable == "no":
        return ComplianceItem(
            **common,
            status="not_applicable",
            value=numeric_value,
            message=f"本方案不适用该规则（适用条件：{rule.when}）",
        )
    if applicable == "unknown":
        return ComplianceItem(
            **common,
            status="insufficient_data",
            value=numeric_value,
            missing_fields=list(when_missing),
            message=_insufficient_message(when_missing, suffix="，无法判断本规则是否适用"),
        )

    analyzed = analyze_expression(rule.check or "", "check", known)
    missing = namespace.missing_for(analyzed.names, analyzed.dictionary_keys)
    if missing:
        return ComplianceItem(
            **common,
            status="insufficient_data",
            value=numeric_value,
            missing_fields=list(missing),
            message=_insufficient_message(missing),
        )

    try:
        passed = bool(_eval_expression(rule.check or "", namespace, known))
    except ZeroDivisionError:
        return ComplianceItem(
            **common,
            status="insufficient_data",
            value=numeric_value,
            message="判定时出现除以 0，通常是某个面积或体积字段填了 0，请核对输入",
        )
    except (InvalidExpression, TypeError, ValueError) as exc:
        return ComplianceItem(
            **common,
            status="insufficient_data",
            value=numeric_value,
            message=f"判定失败：{exc}。请检查该规则的 check 表达式与字段取值",
        )

    if passed:
        return ComplianceItem(
            **common, status="passed", value=numeric_value, message=f"{rule.name} 通过"
        )
    message = (
        _format_message(rule.message, namespace)
        if rule.message
        else f"{rule.name} 不通过（要求：{rule.check}）"
    )
    return ComplianceItem(**common, status="failed", value=numeric_value, message=message)


def _insufficient_message(missing: Sequence[str], suffix: str = "，无法判定") -> str:
    """缺数据时的统一话术。"""
    if not missing:
        return f"数据不足{suffix}"
    return f"缺少字段 {'、'.join(missing)}{suffix}"


def _evaluate_metric(rule: RuleDef, namespace: Namespace, known: frozenset[str]) -> MetricResult:
    """计算一条评分指标。"""
    assert rule.dimension is not None and rule.scoring is not None and rule.value is not None

    formula = _metric_formula(rule)
    common: dict[str, Any] = {
        "rule_id": rule.id,
        "name": rule.name,
        "dimension": rule.dimension,
        "formula": formula,
        "source": rule.source,
        "weight_in_dimension": rule.weight_in_dimension,
    }

    applicable, when_missing = _applicability(rule, namespace, known)
    if applicable == "no":
        return MetricResult(**common, status="not_applicable", value=None, score=None)
    if applicable == "unknown":
        return MetricResult(
            **common,
            status="insufficient_data",
            value=None,
            score=None,
            missing_fields=list(when_missing),
        )

    analyzed = analyze_expression(rule.value, "value", known)
    missing = namespace.missing_for(analyzed.names, analyzed.dictionary_keys)
    if missing:
        return MetricResult(
            **common,
            status="insufficient_data",
            value=None,
            score=None,
            missing_fields=list(missing),
        )

    try:
        raw = _eval_expression(rule.value, namespace, known)
    except (InvalidExpression, TypeError, ValueError, ZeroDivisionError):
        return MetricResult(**common, status="insufficient_data", value=None, score=None)

    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        # 指标必须是数字才能落到分段折线上；布尔值按"算不出来"处理。
        return MetricResult(**common, status="insufficient_data", value=None, score=None)

    value = float(raw)
    score = piecewise_score(value, rule.scoring.points)
    return MetricResult(**common, status="scored", value=value, score=score)


def _metric_formula(rule: RuleDef) -> str:
    """指标的公式字符串：取值怎么来的 + 分数怎么算的。

    形如 ``std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100``；
    若 ``value`` 引用的是派生量，还会带上派生量自己的公式，方便一路追到原始字段。
    """
    assert rule.scoring is not None and rule.value is not None
    value_part = rule.value.strip()
    derived = DERIVED_BY_NAME.get(value_part)
    if derived is not None:
        value_part = f"{value_part} = {derived.formula}"
    return f"{value_part}；{describe_piecewise(rule.scoring.points)}"


def _aggregate_dimensions(
    metrics: Mapping[str, MetricResult],
) -> tuple[DimensionScores, DimensionCoverage]:
    """按维度把指标分数加权平均，同时算出数据覆盖率。

    - 维度得分 = 该维度内 **有分数** 的指标按 ``weight_in_dimension`` 加权平均；
    - ``coverage`` = 有分数的权重 / 适用指标的总权重。
      ``not_applicable`` 的指标不计入分母——它本来就不该参与这个方案的评估，
      算进去会让覆盖率无谓地变低。
    """
    scores: dict[str, float] = {}
    coverages: dict[str, float] = {}

    for dimension in DIMENSION_KEYS:
        in_dim = [m for m in metrics.values() if m.dimension == dimension]
        applicable = [m for m in in_dim if m.status != "not_applicable"]
        scored = [m for m in applicable if m.score is not None]

        total_weight = sum(m.weight_in_dimension for m in applicable)
        scored_weight = sum(m.weight_in_dimension for m in scored)

        if scored_weight > 0:
            weighted = sum((m.score or 0.0) * m.weight_in_dimension for m in scored)
            scores[dimension] = round(weighted / scored_weight, 4)
        else:
            scores[dimension] = 0.0
        coverages[dimension] = round(scored_weight / total_weight, 4) if total_weight > 0 else 0.0

    return DimensionScores(**scores), DimensionCoverage(**coverages)


def evaluate(
    project: ProjectParams,
    schemes: Sequence[SchemeInput],
    rules: RuleSet,
    *,
    known: frozenset[str] | None = None,
) -> list[EvalResult]:
    """对每个方案跑一遍全部规则。

    Args:
        project: 项目层参数（地块条件），对所有方案相同。
        schemes: 参与评估的方案。
        rules: 已加载校验过的规则集。

    Returns:
        与 ``schemes`` 顺序一致的评估结果列表。每条合规结果与指标结果都带
        ``rule_id`` / ``source`` / ``formula``，供报告溯源。

    本函数是纯函数：不读数据库、不调大模型、不依赖时间或随机数。
    """
    known = known if known is not None else known_field_names()
    custom_names = known - known_field_names()
    results: list[EvalResult] = []

    for scheme in schemes:
        namespace = build_namespace(project, scheme.params, custom_names=custom_names)

        compliance = [_evaluate_hard(rule, namespace, known) for rule in rules.hard_rules]
        metrics = {rule.id: _evaluate_metric(rule, namespace, known) for rule in rules.metric_rules}
        dimension_scores, dimension_coverage = _aggregate_dimensions(metrics)

        results.append(
            EvalResult(
                scheme_id=scheme.scheme_id,
                scheme_name=scheme.name,
                compliance=compliance,
                metrics=metrics,
                dimension_scores=dimension_scores,
                dimension_coverage=dimension_coverage,
            )
        )

    return results
