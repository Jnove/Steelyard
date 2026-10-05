"""数字溯源校验；白名单受本次工具证据约束。"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.agents.state import NumberIssue

# 规则编号、单位指数单独处理，避免把 C-03 当成负数或 m² 当成面积。
NUMBER_RE = re.compile(
    r"(?<![\d.])(?<![A-Za-z_])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?(?:\s*[%％])?"
)
RULE_RE = re.compile(r"\b[CQSKG]-\d{2}\b")
STANDARD_RE = re.compile(r"\b(?:GB(?:/T)?|JGJ(?:/T)?|DB[\d/]*)\s*[\d.-]+")
YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*年")


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.strip().replace(",", "").rstrip("%％").strip())
    except InvalidOperation:
        return None


def collect_numbers(value: Any) -> set[Decimal]:
    """收集数值字段以及公式、source、编号里明确存在的数字；不读取用户消息。"""
    numbers: set[Decimal] = set()
    if isinstance(value, bool) or value is None:
        return numbers
    if isinstance(value, (int, float)):
        if math.isfinite(value):
            numbers.add(Decimal(str(value)))
    elif isinstance(value, str):
        for match in NUMBER_RE.finditer(value):
            number = _decimal(match[0])
            if number is not None:
                numbers.add(number / 100 if match[0].strip().endswith(("%", "％")) else number)
        # 只从规范编号补收组成部分，不能把面积或百分数拆成别的数值。
        for standard in STANDARD_RE.finditer(value):
            for match in re.finditer(r"\d+(?:\.\d+)?", standard[0]):
                numbers.add(Decimal(match[0]))
    elif isinstance(value, dict):
        for item in value.values():
            numbers.update(collect_numbers(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers.update(collect_numbers(item))
    return numbers


def check_citations(
    text: str, evidence: dict[str, Any], rules: list[dict[str, Any]], scheme_count: int
) -> list[NumberIssue]:
    numbers = (
        collect_numbers(evidence) | collect_numbers(rules) | {Decimal(scheme_count), Decimal(4)}
    )
    # 格式化支持 Python 的舍入以及通常报告使用的四舍五入。
    allowed: set[Decimal] = set(numbers)
    for number in numbers:
        for digits in range(3):
            step = Decimal(1).scaleb(-digits)
            allowed.add(round(number, digits))
            allowed.add(number.quantize(step, rounding=ROUND_HALF_UP))
    spans = [
        m.span() for pattern in (RULE_RE, STANDARD_RE, YEAR_RE) for m in pattern.finditer(text)
    ]
    trusted_strings = str(rules) + str(evidence)
    issues: list[NumberIssue] = []
    for match in NUMBER_RE.finditer(text):
        # 年份按任务要求白名单；规范编号仅在实际 source 中存在时豁免。
        exempt = any(
            a <= match.start()
            and match.end() <= b
            and (text[a:b] in trusted_strings or YEAR_RE.fullmatch(text[a:b]))
            for a, b in spans
        )
        if exempt:
            continue
        raw = match[0].strip()
        number = _decimal(raw)
        if number is None:
            continue
        if raw.endswith(("%", "％")):
            valid = any(
                0 <= value <= 1
                and any(
                    number
                    in (
                        round(value * 100, digits),
                        (value * 100).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP),
                    )
                    for digits in range(3)
                )
                for value in numbers
            )
        else:
            valid = number in allowed
        if not valid:
            issues.append(NumberIssue(text=raw, start=match.start(), end=match.start() + len(raw)))
    return issues
