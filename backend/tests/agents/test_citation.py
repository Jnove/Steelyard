"""引用校验的舍入、百分数、规则常数与位置精度。"""

from __future__ import annotations

import pytest
from app.agents.citation import check_citations


@pytest.mark.parametrize(
    "text",
    [
        "贴近度0.63",
        "贴近度 0.6",
        "贴近度1",
        "比例63%",
        "比例63.49％",
        "比例 63.5%",
        "面积1,234.56m²",
        "分数 -2.3",
        "得分 .63",
        "有5个方案、4个维度",
        "2025年",
    ],
)
def test_allowed_numbers(text: str) -> None:
    assert not check_citations(text, {"values": [0.6349, 1234.56, -2.345]}, [], 5)


@pytest.mark.parametrize(
    "text",
    [
        "分数998.23",
        "增长998.23%",
        "分数 -998.23",
        "比例 63.49",
        "伪造规范 GB 99823-2025",
        "得分 2.98e5",
    ],
)
def test_reject_unbacked_numbers(text: str) -> None:
    issues = check_citations(text, {"ratio": 0.6349}, [], 5)
    assert issues
    for issue in issues:
        assert text[issue.start : issue.end] == issue.text


def test_real_rule_source_and_constants() -> None:
    rules = [{"id": "C-03", "source": "GB 55038-2025 TODO(专业组)", "check": "floor_height >= 3.0"}]
    assert not check_citations("C-03（source：GB 55038-2025）；层高 3.0 m", {}, rules, 5)
    assert check_citations("层高 3.98 m", {}, rules, 5)


def test_user_message_is_not_evidence() -> None:
    assert check_citations("用户说得分 998.23", {}, [], 5)


def test_half_up_and_percent_precision() -> None:
    assert not check_citations("得分 2.68；比例 26.8%", {"values": [2.675, 0.2675]}, [], 5)
    assert check_citations("比例 267.5%", {"values": [2.675]}, [], 5)


def test_percent_json_and_comma_lists() -> None:
    assert not check_citations("比例 0.82；数值 1,2", {"ratio": "82%", "values": [1, 2]}, [], 5)
    assert check_citations("数值 234.56", {"area": "1,234.56"}, [], 5)
