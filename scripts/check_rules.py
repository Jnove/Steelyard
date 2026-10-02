"""``rules/*.yaml`` 规则文件校验脚本。

职责（T9 最小可用版，T3 会进一步扩展）：
- 加载 YAML 文件（除 ``weights.yaml``），识别硬约束与评分指标两类规则的必备字段；
- 检查最常见的三类 YAML 格式错误（Tab 缩进 / 中文冒号 / 缩进不齐），给出明确位置；
- 输出每个文件的 ERROR/WARNING 清单，退出码 0 表示全部通过，1 表示有 ERROR。

用法::

    uv run --project backend python scripts/check_rules.py           # 校验 rules/
    uv run --project backend python scripts/check_rules.py path.yaml  # 校验单个文件
    uv run --project backend python scripts/check_rules.py --dir backend/tests/fixtures/guide_examples/

设计：把 YAML 文本先按行扫一遍找 Tab / 中文冒号，再用 ``yaml.safe_load`` 解析，最后
做结构性校验。两步分离是因为一旦文本里就有非法字符，解析错误信息会掩盖真正的问题。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

#: 硬约束 / 评分指标共用的枚举维度。改动时同步 ``app/models/eval.py`` 里的 ``DimensionKey``。
VALID_DIMENSIONS: tuple[str, ...] = ("quality", "structure", "construction", "green")
#: 评分指标支持的 ``scoring.kind``，T9 阶段只校验 piecewise（分段线性）。
VALID_SCORING_KINDS: tuple[str, ...] = ("piecewise",)
#: ``weights.yaml`` 是 AHP 角色权重模板，不是规则列表，单独跳过。
WEIGHTS_FILENAME = "weights.yaml"
#: 中文全角冒号，在 YAML key/value 分隔位置出现就报错。
CHINESE_COLON = "："
#: 一行文字里如果同时含 key 文本与中文冒号，触发"中文冒号"错误的最短长度阈值。
COLON_HINT_MIN_LEN = 2


@dataclass
class Issue:
    """单条校验问题。"""

    severity: str  # "ERROR" / "WARNING"
    code: str
    message: str
    line: int | None = None

    def render(self, path: Path) -> str:
        loc = f"{path}:{self.line}" if self.line is not None else str(path)
        return f"  [{self.severity}] {loc} · {self.code} · {self.message}"


@dataclass
class FileReport:
    """单个文件的校验汇总。"""

    path: Path
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "ERROR" for i in self.issues)

    def render(self) -> str:
        lines = [f"━━ {self.path}"]
        if not self.issues:
            lines.append("  [OK] 无 ERROR / WARNING")
        else:
            lines.extend(issue.render(self.path) for issue in self.issues)
        return "\n".join(lines)


def _is_yaml_key_like(s: str) -> bool:
    """判断字符串是否像 YAML key（字母 / 数字 / 下划线 / 连字符 / 点）。"""
    if not s:
        return False
    return all(ch.isalnum() or ch in "_-./" for ch in s)


def _scan_text_issues(text: str) -> list[Issue]:
    """纯文本扫描：Tab 缩进 / 中文冒号。"""
    issues: list[Issue] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # 1. 行首或键前的空白里若含 Tab，按"Tab 缩进"报错。
        if raw.startswith("\t") or "\t " in raw or " \t" in raw:
            # 只关心缩进位置的 Tab；行尾的 Tab 暂不报错。
            issues.append(
                Issue(
                    severity="ERROR",
                    code="TAB_INDENT",
                    message="检测到 Tab 缩进。YAML 要求用 2 空格缩进，请把 Tab 替换为空格。",
                    line=lineno,
                )
            )

        # 2. 中文全角冒号：仅当它处于「key 与 value 之间」的位置才报，避免误报
        # 中文正文里的「：」（例如注释里的全角句号）。
        if CHINESE_COLON in raw:
            stripped = raw.lstrip()
            if stripped.startswith("#"):
                # 整行注释里的冒号不管
                continue
            # 必须形如 ``key：value``（前面可能有 ``- `` 列表标记）
            tail = stripped.removeprefix("- ")
            if ":" in tail:
                # 该行已经存在英文冒号，全角冒号大概率是中文正文，不再报错
                continue
            head, sep, _ = tail.partition(CHINESE_COLON)
            # head 必须是「像 YAML key」的形态：只含字母 / 数字 / 下划线 / 连字符
            key_candidate = head.strip()
            if sep and key_candidate and _is_yaml_key_like(key_candidate):
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="CHINESE_COLON",
                        message=(
                            f"检测到中文冒号「{CHINESE_COLON}」。YAML 的 key 与 value 之间"
                            "必须用英文半角冒号「:」，请替换。"
                        ),
                        line=lineno,
                    )
                )

    return issues


def _scan_alignment_issues(text: str) -> list[Issue]:
    """缩进不齐：在 YAML 顶层 / 二层位置，所有同辈节点的缩进空格数应该一致。

    实现思路：用一个非常简化的"key 识别器"抓出 ``key:`` 出现的行及其前导空格，
    然后按"父节点缩进"分组比较。最常见的错误是顶层列表项的 ``-`` 与 ``key:``
    错位，或同一层级内的子键缩进不一致。
    """
    issues: list[Issue] = []
    # 只看非空、非注释行
    lines = [
        (idx, raw)
        for idx, raw in enumerate(text.splitlines(), start=1)
        if raw.strip() and not raw.lstrip().startswith("#")
    ]

    # 按缩进级别（连续空格数）分组 key：list[start:list[line]]
    by_indent: dict[int, list[tuple[int, str]]] = {}
    for idx, raw in lines:
        # 计算前导空格数
        stripped = raw.lstrip(" ")
        leading = len(raw) - len(stripped)
        # 仅记录 "key:" 形式（顶层 list 项会带 "- "，识别为同一级）
        content = stripped
        if content.startswith("- "):
            content = content[2:].lstrip()
        # 必须含英文冒号且冒号前有非空内容
        if ":" in content:
            key = content.split(":", 1)[0].strip()
            if key:
                by_indent.setdefault(leading, []).append((idx, key))

    for entries in by_indent.values():
        if len(entries) < 2:
            continue
        # 同一缩进级别内，key 名应都是同辈。但严格判断"父节点相同"需要完整的
        # 树结构，这里采用一个简化启发：同一缩进级别内 key 名重复 = 大概率错位。
        seen: dict[str, int] = {}
        for idx, k in entries:
            if k in seen:
                issues.append(
                    Issue(
                        severity="WARNING",
                        code="UNALIGNED",
                        message=(
                            f"同一缩进级别内重复出现 key「{k}」（行 {seen[k]} 与行 {idx}），"
                            "通常是缩进不齐导致兄弟节点错位，请检查。"
                        ),
                        line=idx,
                    )
                )
            else:
                seen[k] = idx

    return issues


def _check_one_rule(rule: Any, lineno_hint: int) -> list[Issue]:
    """单条规则的结构校验。返回 ERROR 列表。"""
    issues: list[Issue] = []

    if not isinstance(rule, dict):
        issues.append(
            Issue(
                severity="ERROR",
                code="RULE_NOT_OBJECT",
                message=f"规则必须是对象，实际是 {type(rule).__name__}",
                line=lineno_hint,
            )
        )
        return issues

    # 三个共同必填字段
    for key in ("id", "name", "type"):
        if key not in rule:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="MISSING_FIELD",
                    message=f"缺少必填字段「{key}」",
                    line=lineno_hint,
                )
            )

    rule_type = rule.get("type")
    if rule_type not in ("hard", "metric"):
        if "type" in rule:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="BAD_TYPE",
                    message=f"type 必须是 hard 或 metric，实际是 {rule_type!r}",
                    line=lineno_hint,
                )
            )
        return issues

    if rule_type == "hard":
        check = rule.get("check")
        if not isinstance(check, str) or not check.strip():
            issues.append(
                Issue(
                    severity="ERROR",
                    code="HARD_MISSING_CHECK",
                    message="hard 规则必须有 check 表达式（字符串）",
                    line=lineno_hint,
                )
            )

    elif rule_type == "metric":
        # value：字段名或表达式，简单按字符串要求非空
        value = rule.get("value")
        if not isinstance(value, str) or not value.strip():
            issues.append(
                Issue(
                    severity="ERROR",
                    code="METRIC_MISSING_VALUE",
                    message="metric 规则必须有 value 字段名或表达式（字符串）",
                    line=lineno_hint,
                )
            )

        # dimension
        dimension = rule.get("dimension")
        if dimension not in VALID_DIMENSIONS:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="METRIC_BAD_DIMENSION",
                    message=(
                        f"dimension 必须是 {VALID_DIMENSIONS} 之一，实际是 {dimension!r}"
                    ),
                    line=lineno_hint,
                )
            )

        # scoring
        scoring = rule.get("scoring")
        if not isinstance(scoring, dict):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="METRIC_MISSING_SCORING",
                    message="metric 规则必须有 scoring 子对象",
                    line=lineno_hint,
                )
            )
        else:
            kind = scoring.get("kind")
            if kind not in VALID_SCORING_KINDS:
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="METRIC_BAD_SCORING_KIND",
                        message=(
                            f"scoring.kind 必须是 {VALID_SCORING_KINDS} 之一，实际是 {kind!r}"
                        ),
                        line=lineno_hint,
                    )
                )
            points = scoring.get("points")
            if not isinstance(points, list) or not points:
                issues.append(
                    Issue(
                        severity="ERROR",
                        code="METRIC_EMPTY_POINTS",
                        message="scoring.points 必须是非空列表",
                        line=lineno_hint,
                    )
                )
            else:
                # 每项必须是 [数字, 数字] 且第一列单调递增
                xs: list[float] = []
                bad_shape = False
                for i, pt in enumerate(points):
                    if (
                        not isinstance(pt, list)
                        or len(pt) != 2
                        or not all(isinstance(v, (int, float)) for v in pt)
                    ):
                        issues.append(
                            Issue(
                                severity="ERROR",
                                code="METRIC_BAD_POINT",
                                message=f"points[{i}] 必须是 [数字, 数字]",
                                line=lineno_hint,
                            )
                        )
                        bad_shape = True
                    else:
                        xs.append(float(pt[0]))
                if not bad_shape and xs != sorted(set(xs)):
                    issues.append(
                        Issue(
                            severity="ERROR",
                            code="METRIC_POINTS_NOT_MONOTONIC",
                            message=(
                                f"points 第一列必须严格递增，当前是 {xs}。"
                                "「适中最好」的指标应当先升后降，但仍要严格递增（极值点除外，"
                                "极值点用同一个值表示两段）。"
                            ),
                            line=lineno_hint,
                        )
                    )

    return issues


def check_file(path: Path) -> FileReport:
    """校验单个 YAML 文件，返回汇总。"""
    report = FileReport(path=path)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.issues.append(
            Issue(severity="ERROR", code="READ_ERROR", message=str(exc))
        )
        return report

    # 文本层：Tab / 中文冒号
    report.issues.extend(_scan_text_issues(text))

    # 缩进不齐（WARN，启发式）
    report.issues.extend(_scan_alignment_issues(text))

    # 解析层
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        report.issues.append(
            Issue(severity="ERROR", code="YAML_PARSE", message=str(exc).split("\n")[0])
        )
        return report

    if data is None:
        # 空文件（仅注释）— 允许通过
        return report

    if not isinstance(data, list):
        report.issues.append(
            Issue(
                severity="ERROR",
                code="TOP_NOT_LIST",
                message=f"YAML 顶层必须是规则列表（- id: ...），实际是 {type(data).__name__}",
            )
        )
        return report

    for idx, rule in enumerate(data, start=1):
        report.issues.extend(_check_one_rule(rule, lineno_hint=idx))

    return report


def iter_rule_files(root: Path) -> Iterable[Path]:
    """枚举待校验的 YAML 文件。``weights.yaml`` 单独跳过。"""
    if root.is_file():
        if root.suffix in (".yaml", ".yml"):
            yield root
        return
    if not root.is_dir():
        return
    for p in sorted(root.glob("*.yaml")):
        if p.name == WEIGHTS_FILENAME:
            continue
        yield p
    for p in sorted(root.glob("*.yml")):
        if p.name == WEIGHTS_FILENAME:
            continue
        yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 rules/*.yaml")
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
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只在有 ERROR 时输出",
    )
    args = parser.parse_args(argv)

    # Windows 默认 GBK 控制台会让中文 ERROR 输出乱码；强制 UTF-8 让跨平台一致。
    # CI（GitHub Actions / Linux）已经是 UTF-8，这里仅做兜底。
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    repo_root = Path(__file__).resolve().parents[1]
    if args.paths:
        files = [p for path in args.paths for p in iter_rule_files(path)]
    elif args.rules_dir is not None:
        files = list(iter_rule_files(args.rules_dir))
    else:
        files = list(iter_rule_files(repo_root / "rules"))

    if not files:
        # 没有 YAML 规则文件不算错误：T9 阶段规则目录还是空的，等 T3 起由专业组填充。
        print(
            "未找到任何 YAML 规则文件（如果这是首次启用，可以忽略；"
            f"T3 起在 {repo_root / 'rules'} 下添加规则即可）"
        )
        return 0

    total_errors = 0
    total_warnings = 0
    for path in files:
        report = check_file(path)
        if args.quiet and not report.has_errors:
            continue
        print(report.render())
        total_errors += len(report.errors)
        total_warnings += sum(
            1 for i in report.issues if i.severity == "WARNING"
        )

    print()
    print(
        f"汇总：{len(files)} 个文件，{total_errors} 个 ERROR，{total_warnings} 个 WARNING"
    )
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
