"""``rules/*.yaml`` 规则文件校验脚本。

**这个脚本是给土木、建筑同学用的**，所以每条报错都由三段组成：

    文件名:行号  规则ID — 中文说明 — 怎么改

行号来自 PyYAML 的 node mark（真实行号，不是"第几条规则"），照着行号打开文件就能改。

覆盖的错误
----------
- YAML 语法错误（含 Tab 缩进、中文全角冒号、缩进不齐）；
- 缺必填项、未知字段、字段取值不合法（ID 格式、type、dimension、severity……）；
- 规则 ID 重复（跨文件也查，并同时报出两处位置）；
- ``scoring.points`` 的指标值不严格递增、分数超出 0–100；
- 表达式语法错误，以及引用了不存在的字段（用 ``difflib`` 给出拼写最接近的候选）；
- ``weights.yaml``（角色权重模板）：四个角色齐不齐、矩阵是否互反、一致性比率 CR 是否超过 0.1（超了报警告）。

退出码：有 ERROR 时为 1，只有 WARNING 时为 0（``source`` 还挂着 TODO 属于 WARNING）。

用法::

    uv run --project backend python scripts/check_rules.py                    # 校验 rules/
    uv run --project backend python scripts/check_rules.py rules/quality.yaml  # 单个文件
    uv run --project backend python scripts/check_rules.py path/to/dir/        # 指定目录

实现分三步，刻意分开：先扫文本（Tab / 全角冒号），再解析 YAML 拿 node mark，
最后用引擎的 ``RuleDef`` 做结构校验。第一步单独做是因为文本里就有非法字符时，
YAML 解析器的报错会掩盖真正的问题；第三步复用引擎模型是为了保证
"check_rules 说通过"和"引擎能加载"永远是一回事。
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.engine.rules import (  # noqa: E402
    DIMENSION_KEYS,
    NON_RULE_FILENAMES,
    RuleDef,
    analyze_expression,
    known_field_names,
)
from app.engine.scoring import SCORE_MAX, SCORE_MIN  # noqa: E402
from app.engine.weights import (  # noqa: E402
    WEIGHTS_FILENAME as _WEIGHTS_FILENAME,
)
from app.engine.weights import check_weights_file  # noqa: E402
from pydantic import ValidationError  # noqa: E402

#: 硬约束 / 评分指标共用的枚举维度，取自引擎，避免两处各写一份。
VALID_DIMENSIONS: tuple[str, ...] = tuple(DIMENSION_KEYS)
#: 评分指标支持的 ``scoring.kind``。
VALID_SCORING_KINDS: tuple[str, ...] = ("piecewise",)
#: ``weights.yaml`` 是 AHP 角色权重模板，不按规则列表校验，走 :func:`check_weights` 那套。
WEIGHTS_FILENAME = _WEIGHTS_FILENAME
#: 中文全角冒号，在 YAML key/value 分隔位置出现就报错。
CHINESE_COLON = "："

Severity = Literal["error", "warning"]

#: 规则 ID 未知时的占位符（例如整条规则连 id 都没写）。
UNKNOWN_RULE_ID = "（未知 ID）"

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

    def render(self, path: Path) -> str:
        label = "错误" if self.severity == "error" else "警告"
        loc = f"{_display_path(path)}:{self.line}" if self.line is not None else _display_path(path)
        rule_id = self.rule_id or UNKNOWN_RULE_ID
        return f"{label}  {loc}  {rule_id} — {self.message} — 怎么改：{self.fix}"


def _display_path(path: Path) -> str:
    """尽量显示相对仓库根的路径，读起来短一些。"""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass
class FileReport:
    """单个文件的校验汇总。"""

    path: Path
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def dedupe(self) -> None:
        """去掉重复的问题。

        同一处失误常常被两道检查同时抓到——例如 Tab 缩进先被文本扫描发现，
        随后 YAML 解析器也会在同一行报一次。对规则作者来说看到两遍只是噪音。
        """
        seen: set[tuple[str, int | None, str]] = set()
        kept: list[Issue] = []
        for issue in self.issues:
            marker = (issue.code, issue.line, issue.message)
            if marker in seen:
                continue
            seen.add(marker)
            kept.append(issue)
        self.issues = kept

    def render(self) -> str:
        lines = [f"━━ {_display_path(self.path)}"]
        if not self.issues:
            lines.append("  通过：没有发现错误或警告")
        else:
            # 先错误后警告，各自按行号排序，方便从上往下改。
            ordered = sorted(
                self.issues,
                key=lambda i: (0 if i.severity == "error" else 1, i.line or 0),
            )
            lines.extend("  " + issue.render(self.path) for issue in ordered)
        return "\n".join(lines)


# —— 第一步：纯文本扫描 —— #


def _is_yaml_key_like(text: str) -> bool:
    """判断字符串是否像 YAML key（字母 / 数字 / 下划线 / 连字符 / 点 / 斜杠）。"""
    if not text:
        return False
    return all(ch.isalnum() or ch in "_-./" for ch in text)


def _scan_text_issues(text: str) -> list[Issue]:
    """扫描 Tab 缩进与中文全角冒号——这两类是非程序员最常踩的坑。"""
    issues: list[Issue] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # 1. 缩进位置出现 Tab。行尾的 Tab 不影响解析，不报。
        if raw.startswith("\t") or "\t " in raw or " \t" in raw:
            issues.append(
                Issue(
                    severity="error",
                    code="TAB_INDENT",
                    message="这一行用了 Tab 缩进，YAML 不接受 Tab",
                    fix="把行首的 Tab 全部替换成空格；同一层级统一缩 2 个空格",
                    line=lineno,
                )
            )

        # 2. 中文全角冒号：只有出现在「key 与 value 之间」才报，
        #    避免误伤中文正文（例如 message 里的「说明：xxx」）。
        if CHINESE_COLON in raw:
            stripped = raw.lstrip()
            if stripped.startswith("#"):
                continue
            tail = stripped.removeprefix("- ")
            if ":" in tail:
                # 该行已有英文冒号，全角冒号大概率是正文内容，不报。
                continue
            head, sep, _ = tail.partition(CHINESE_COLON)
            key_candidate = head.strip()
            if sep and key_candidate and _is_yaml_key_like(key_candidate):
                issues.append(
                    Issue(
                        severity="error",
                        code="CHINESE_COLON",
                        message=f"这一行用了中文全角冒号「{CHINESE_COLON}」",
                        fix="把它替换成英文半角冒号「:」。半角冒号比汉字窄，全角冒号和汉字一样宽",
                        line=lineno,
                    )
                )

    return issues


def _scan_duplicate_keys(text: str) -> list[Issue]:
    """同一条规则里重复写了同一个字段。

    YAML 遇到重复 key 会 **静默取最后一个**，这对规则作者很危险：
    改了上面那行却不生效，看半天看不出问题。所以单独扫一遍报错。

    实现：按"列表项"分块——顶头的 ``- `` 开一个新块，块内同缩进的 key 不许重名。
    只在块内比较，所以多条规则各写一个 ``id`` 不会误报。
    """
    issues: list[Issue] = []
    # block_start 是当前列表项的起始行，用来把 key 归到同一条规则下。
    seen: dict[tuple[int, int, str], int] = {}
    block_start = 0

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.lstrip(" ")
        indent = len(raw) - len(stripped)
        content = stripped
        if content.startswith("- "):
            if indent == 0:
                block_start = lineno
            content = content[2:].lstrip()
        if ":" not in content:
            continue
        key = content.split(":", 1)[0].strip()
        if not key or not _is_yaml_key_like(key):
            continue
        marker = (block_start, indent, key)
        if marker in seen:
            issues.append(
                Issue(
                    severity="error",
                    code="DUPLICATE_KEY",
                    message=(f"同一条规则里重复写了字段「{key}」（第 {seen[marker]} 行也有一个）"),
                    fix=(
                        "删掉多余的那一行。YAML 遇到重复字段只认最后一个，"
                        "留着会让你改了上面那行却不生效"
                    ),
                    line=lineno,
                )
            )
        else:
            seen[marker] = lineno

    return issues


# —— 第二步：解析 YAML，拿真实行号 —— #

#: PyYAML 的英文 problem 文本 → （内部错误码, 中文说明, 怎么改）。
#: 逐条翻译是因为 PyYAML 的原文对非程序员毫无帮助，
#: 而这几种恰好覆盖了规则作者手写 YAML 时的绝大多数失误。
_YAML_PROBLEM_HINTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "mapping values are not allowed here",
        "YAML_INDENT",
        "这一行的缩进和上一行对不齐，YAML 读不懂它属于谁",
        "让同一条规则里的所有字段缩进完全一致（统一 2 个空格）；也检查一行里是不是多打了一个冒号",
    ),
    (
        "cannot start any token",
        "TAB_INDENT",
        "这一行用了 Tab 缩进，YAML 不接受 Tab",
        "把行首的 Tab 全部替换成空格；同一层级统一缩 2 个空格",
    ),
    (
        "could not find expected ':'",
        "YAML_MISSING_COLON",
        "这一行缺了分隔字段名和取值的冒号",
        "每个字段都要写成 `字段名: 取值`，冒号后面还要有一个空格",
    ),
    (
        "found unexpected end of stream",
        "YAML_UNCLOSED_QUOTE",
        "有一个引号没有闭合，YAML 一直读到文件末尾也没找到配对的引号",
        "检查这一行附近的引号：开头用双引号结尾也要用双引号，单引号同理",
    ),
    (
        "expected <block end>",
        "YAML_INDENT",
        "这一行的缩进比上下文多了或少了，YAML 读不懂它属于谁",
        "让同一层级的字段对齐到同一列；列表项用顶头的 `- `，字段缩 2 个空格",
    ),
    (
        "found duplicate key",
        "DUPLICATE_KEY",
        "同一条规则里重复写了同一个字段",
        "删掉多余的那一行。YAML 遇到重复字段只认最后一个",
    ),
)


def _translate_yaml_problem(exc: yaml.MarkedYAMLError) -> tuple[str, str, str]:
    """把 PyYAML 的报错翻成中文说明与"怎么改"。"""
    problem = (exc.problem or exc.context or "").strip()
    for needle, code, message, fix in _YAML_PROBLEM_HINTS:
        if needle in problem:
            return code, message, fix
    return (
        "YAML_PARSE",
        f"YAML 解析失败：{problem}",
        "先按上面的 Tab / 全角冒号提示改；"
        "若没有提示，检查这一行的引号是否成对、`- ` 后面有没有空格、缩进是否对齐",
    )


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


# —— 第三步：结构校验（复用引擎的 RuleDef） —— #

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


def _translate_pydantic_error(
    err: dict[str, Any],
    rule_node: yaml.MappingNode | None,
) -> Issue:
    """把一条 Pydantic 报错翻译成中文 Issue，并定位到真实行号。"""
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
                "**前缀按维度选**：合规用 C，品质用 Q，结构用 S，施工用 K，绿色用 G"
                "（同一维度可以有多个文件，例如结构既有 structure.yaml 也有 structure_mic.yaml）"
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


def _check_expressions(rule: RuleDef, rule_node: yaml.MappingNode | None) -> list[Issue]:
    """静态检查规则里的表达式：语法 + 字段名是否存在。"""
    issues: list[Issue] = []
    known = known_field_names()
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


def check_file(path: Path) -> FileReport:
    """校验单个 YAML 文件。"""
    report = FileReport(path=path)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.issues.append(
            Issue(
                severity="error",
                code="READ_ERROR",
                message=f"读不到这个文件（{exc}）",
                fix="确认路径拼写和文件是否存在",
            )
        )
        return report

    report.issues.extend(_scan_text_issues(text))
    report.issues.extend(_scan_duplicate_keys(text))

    # 解析成 node 树以取真实行号。
    try:
        root = yaml.compose(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        code, message, fix = _translate_yaml_problem(exc)
        report.issues.append(
            Issue(
                severity="error",
                code=code,
                message=message,
                fix=fix,
                line=(mark.line + 1) if mark else None,
            )
        )
        report.dedupe()
        return report
    except yaml.YAMLError as exc:
        report.issues.append(
            Issue(
                severity="error",
                code="YAML_PARSE",
                message=f"YAML 解析失败：{str(exc).splitlines()[0]}",
                fix="检查缩进、引号与 `- ` 后的空格",
            )
        )
        return report

    if root is None:
        # 空文件或只有注释：允许。
        report.dedupe()
        return report

    if not isinstance(root, yaml.SequenceNode):
        report.issues.append(
            Issue(
                severity="error",
                code="TOP_NOT_LIST",
                message="文件顶层必须是一个规则列表",
                fix="每条规则以顶头的 `- id: ...` 开头，字段缩进 2 个空格",
                line=root.start_mark.line + 1,
            )
        )
        report.dedupe()
        return report

    data = yaml.safe_load(text)
    for index, rule_node in enumerate(root.value):
        raw = data[index] if isinstance(data, list) and index < len(data) else None
        line = rule_node.start_mark.line + 1

        if not isinstance(raw, dict) or not isinstance(rule_node, yaml.MappingNode):
            report.issues.append(
                Issue(
                    severity="error",
                    code="RULE_NOT_OBJECT",
                    message=f"第 {index + 1} 项不是一条规则",
                    fix="每条规则写成 `- id: C-01` 开头的对象，下面缩进 2 空格写其它字段",
                    line=line,
                )
            )
            continue

        rule_id = raw.get("id") if isinstance(raw.get("id"), str) else None

        try:
            rule = RuleDef.model_validate(raw)
        except ValidationError as exc:
            for err in exc.errors():
                issue = _translate_pydantic_error(err, rule_node)
                issue.rule_id = rule_id
                if issue.line is None:
                    issue.line = line
                report.issues.append(issue)
            continue

        report.issues.extend(_check_expressions(rule, rule_node))
        report.issues.extend(_check_source_todo(rule, rule_node))

    report.dedupe()
    return report


def check_weights(path: Path) -> FileReport:
    """校验角色权重模板 ``weights.yaml``。

    和规则文件是两套东西：这里没有规则 ID，检查的是四个角色齐不齐、
    两两比较矩阵是否互反、以及**一致性比率 CR 有没有超过 0.1**。

    CR 超标只报 **警告**：矩阵由专业组填，判断自相矛盾是需要他们回头改，
    但不该拦住合并（真正该拦的是矩阵写错了根本解不出权重，那是错误）。

    行号：权重模板是"角色名 → 配置"的嵌套结构，Pydantic 式的错误路径下钻在这里
    收益不大，所以统一指到该角色的键所在行；找不到就不带行号。
    """
    report = FileReport(path=path)
    templates, problems = check_weights_file(path)

    # 角色键所在的行号，用于把问题指到具体角色。
    role_lines: dict[str, int] = {}
    try:
        root = yaml.compose(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        root = None
    if isinstance(root, yaml.MappingNode):
        for key_node, _ in root.value:
            key = getattr(key_node, "value", None)
            if isinstance(key, str):
                role_lines[key] = key_node.start_mark.line + 1

    for problem in problems:
        report.issues.append(
            Issue(
                severity="error" if problem.severity == "error" else "warning",
                code=problem.code,
                message=problem.message,
                fix=problem.fix,
                line=role_lines.get(problem.role or ""),
                rule_id=problem.role,
            )
        )

    # 出处还挂着 TODO 的模板，和规则一样提醒一句。
    for key, template in templates.items():
        if "TODO" in template.source:
            report.issues.append(
                Issue(
                    severity="warning",
                    code="WEIGHTS_SOURCE_TODO",
                    message=f"角色 {key}（{template.name}）的矩阵还是占位数值",
                    fix="专业组核定后把 source 里的「【示例】TODO(专业组)」换成真实依据",
                    line=role_lines.get(key),
                    rule_id=key,
                )
            )

    report.dedupe()
    return report


def check_duplicate_ids(
    reports: Iterable[tuple[Path, yaml.Node | None]],
) -> list[tuple[Path, Issue]]:
    """跨文件查重复的规则 ID，两处位置都报出来。"""
    seen: dict[str, tuple[Path, int]] = {}
    out: list[tuple[Path, Issue]] = []
    for path, root in reports:
        if not isinstance(root, yaml.SequenceNode):
            continue
        for rule_node in root.value:
            if not isinstance(rule_node, yaml.MappingNode):
                continue
            for key_node, value_node in rule_node.value:
                if getattr(key_node, "value", None) != "id":
                    continue
                rule_id = getattr(value_node, "value", None)
                if not isinstance(rule_id, str):
                    continue
                line = value_node.start_mark.line + 1
                if rule_id in seen:
                    first_path, first_line = seen[rule_id]
                    out.append(
                        (
                            path,
                            Issue(
                                severity="error",
                                code="DUPLICATE_ID",
                                message=(
                                    f"规则 ID 重复：{_display_path(first_path)}:{first_line} "
                                    "已经用过这个 ID"
                                ),
                                fix="规则 ID 必须全局唯一，给这一条换一个没用过的编号",
                                line=line,
                                rule_id=rule_id,
                            ),
                        )
                    )
                else:
                    seen[rule_id] = (path, line)
    return out


def iter_rule_files(root: Path) -> Iterable[Path]:
    """枚举待校验的 YAML 文件。

    跳过两类：下划线开头的（``_template.yaml`` 这类模板与草稿）和 ``weights.yaml``
    （AHP 角色权重模板，不是规则列表）。显式指定单个文件时不做这些过滤。
    """
    if root.is_file():
        if root.suffix in (".yaml", ".yml"):
            yield root
        return
    if not root.is_dir():
        return
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix not in (".yaml", ".yml"):
            continue
        if path.name.startswith("_") or path.name in NON_RULE_FILENAMES:
            continue
        yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="校验 rules/*.yaml（报错格式：文件名:行号 规则ID — 中文说明 — 怎么改）"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="要校验的文件或目录（默认校验 rules/）",
    )
    parser.add_argument(
        "--rules-dir",
        dest="rules_dir",
        type=Path,
        default=None,
        help="要扫描的规则目录（与 paths 二选一；后者优先）",
    )
    parser.add_argument("--quiet", action="store_true", help="只在有错误时输出")
    args = parser.parse_args(argv)

    # Windows 默认 GBK 控制台会让中文报错乱码；强制 UTF-8 让跨平台一致。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    if args.paths:
        files = [p for path in args.paths for p in iter_rule_files(path)]
    elif args.rules_dir is not None:
        files = list(iter_rule_files(args.rules_dir))
    else:
        files = list(iter_rule_files(ROOT / "rules"))

    # 角色权重模板走另一套检查（check_weights），不当规则列表看。
    # iter_rule_files 对**显式指定的单个文件**不做名字过滤（方便校验 _template.yaml），
    # 所以这里要把 weights.yaml 从规则文件列表里摘出来，免得同一个文件被查两遍。
    weights_paths = [p for p in files if p.name == WEIGHTS_FILENAME]
    files = [p for p in files if p.name != WEIGHTS_FILENAME]
    roots = args.paths or [args.rules_dir or (ROOT / "rules")]
    for root_path in roots:
        candidate = root_path / WEIGHTS_FILENAME
        if root_path.is_dir() and candidate.is_file() and candidate not in weights_paths:
            weights_paths.append(candidate)

    if not files and not weights_paths:
        print(f"未找到任何 YAML 规则文件（在 {_display_path(ROOT / 'rules')} 下添加规则即可）")
        return 0

    reports: list[FileReport] = []
    parsed: list[tuple[Path, yaml.Node | None]] = []
    for path in files:
        reports.append(check_file(path))
        try:
            parsed.append((path, yaml.compose(path.read_text(encoding="utf-8"))))
        except (OSError, yaml.YAMLError):
            parsed.append((path, None))

    # 重复 ID 要跨文件才能查，挂回对应文件的报告上。
    by_path = {report.path: report for report in reports}
    for path, issue in check_duplicate_ids(parsed):
        by_path[path].issues.append(issue)

    reports.extend(check_weights(path) for path in weights_paths)

    total_errors = 0
    total_warnings = 0
    for report in reports:
        total_errors += len(report.errors)
        total_warnings += len(report.warnings)
        if args.quiet and not report.has_errors:
            continue
        print(report.render())

    print()
    print(f"汇总：{len(reports)} 个文件，{total_errors} 个错误，{total_warnings} 个警告")
    if total_errors:
        print("有错误必须改完才能合并（退出码 1）。看不懂报错请对照 docs/rules-guide.md 第 7 节。")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
