"""分段线性评分的测试。

验收标准要求覆盖四种情形：端点、点间插值、两端外截断、先升后降（适中最好）。
"""

from __future__ import annotations

import pytest
from app.engine.scoring import describe_piecewise, piecewise_score

#: 「越大越好」的典型折线：0.5 分，0.8 得 70，0.95 满分。
BIGGER_IS_BETTER: list[tuple[float, float]] = [(0.5, 0.0), (0.8, 70.0), (0.95, 100.0)]
#: 「越小越好」：横坐标仍递增，纵坐标递减。
SMALLER_IS_BETTER: list[tuple[float, float]] = [(60.0, 100.0), (120.0, 70.0), (200.0, 0.0)]
#: 「适中最好」：纵坐标先升后降，峰值在 0.55。
OPTIMAL_IN_MIDDLE: list[tuple[float, float]] = [(0.2, 0.0), (0.55, 100.0), (0.9, 0.0)]


# —— 端点 —— #


@pytest.mark.parametrize(
    "value, expected",
    [(0.5, 0.0), (0.8, 70.0), (0.95, 100.0)],
)
def test_control_points_hit_exactly(value: float, expected: float) -> None:
    """取值正好落在控制点上时，分数就是该控制点的分数。"""
    assert piecewise_score(value, BIGGER_IS_BETTER) == pytest.approx(expected)


# —— 点间插值 —— #


def test_interpolates_between_points() -> None:
    """0.5→0 与 0.8→70 之间的中点（0.65）应当得 35 分。"""
    assert piecewise_score(0.65, BIGGER_IS_BETTER) == pytest.approx(35.0)


def test_interpolates_in_second_segment() -> None:
    """插值要用落在的那一段，而不是整条折线的首尾。

    0.875 是 0.8 与 0.95 的中点，应当得 (70 + 100) / 2 = 85 分。
    如果实现错用了首尾两点，会算成 62.5 分。
    """
    assert piecewise_score(0.875, BIGGER_IS_BETTER) == pytest.approx(85.0)


def test_interpolates_on_descending_segment() -> None:
    """递减段同样插值：120 与 200 的中点 160 应当得 35 分。"""
    assert piecewise_score(160.0, SMALLER_IS_BETTER) == pytest.approx(35.0)


# —— 两端外截断 —— #


@pytest.mark.parametrize("value", [0.49, 0.0, -100.0])
def test_truncates_below_first_point(value: float) -> None:
    """小于第一个控制点时取第一个分数，不做线性外推（否则会出负分）。"""
    assert piecewise_score(value, BIGGER_IS_BETTER) == pytest.approx(0.0)


@pytest.mark.parametrize("value", [0.96, 1.0, 1e6])
def test_truncates_above_last_point(value: float) -> None:
    """大于最后一个控制点时取最后一个分数，不做外推（否则会超过 100 分）。"""
    assert piecewise_score(value, BIGGER_IS_BETTER) == pytest.approx(100.0)


def test_truncation_uses_endpoint_score_not_extremes() -> None:
    """「越小越好」的左端截断应当是 100 分（第一个控制点的分数），不是 0 分。

    这条专门防一种实现错误：把"截断"写成"夹到 0–100"。
    """
    assert piecewise_score(10.0, SMALLER_IS_BETTER) == pytest.approx(100.0)
    assert piecewise_score(10_000.0, SMALLER_IS_BETTER) == pytest.approx(0.0)


# —— 先升后降（适中最好） —— #


def test_optimal_in_middle_peaks_at_middle_point() -> None:
    assert piecewise_score(0.55, OPTIMAL_IN_MIDDLE) == pytest.approx(100.0)


def test_optimal_in_middle_is_symmetric_around_peak() -> None:
    """峰值两侧等距的取值，分数应当同样地掉下来。

    0.375 是 0.2 与 0.55 的中点 → 50 分；
    0.725 是 0.55 与 0.9 的中点 → 也是 50 分。
    """
    assert piecewise_score(0.375, OPTIMAL_IN_MIDDLE) == pytest.approx(50.0)
    assert piecewise_score(0.725, OPTIMAL_IN_MIDDLE) == pytest.approx(50.0)


def test_optimal_in_middle_drops_on_both_sides() -> None:
    """太低和太高都该低分——这正是"适中最好"要表达的东西。"""
    low = piecewise_score(0.25, OPTIMAL_IN_MIDDLE)
    peak = piecewise_score(0.55, OPTIMAL_IN_MIDDLE)
    high = piecewise_score(0.85, OPTIMAL_IN_MIDDLE)
    assert low < peak
    assert high < peak


# —— 非法输入 —— #


def test_rejects_single_point() -> None:
    with pytest.raises(ValueError, match="至少需要"):
        piecewise_score(1.0, [(0.5, 50.0)])


def test_rejects_non_increasing_x() -> None:
    with pytest.raises(ValueError, match="严格递增"):
        piecewise_score(1.0, [(0.9, 0.0), (0.5, 100.0)])


def test_rejects_duplicate_x() -> None:
    """横坐标相等也不允许：同一个取值对应两个分数说不清该用哪个。"""
    with pytest.raises(ValueError, match="严格递增"):
        piecewise_score(1.0, [(0.5, 0.0), (0.5, 100.0)])


# —— 公式字符串 —— #


def test_describe_piecewise_matches_agents_md_format() -> None:
    """公式字符串格式与 AGENTS.md 结果 JSON 示例一致。"""
    assert describe_piecewise([(0.5, 0.0), (0.95, 100.0)]) == "分段线性 0.5→0, 0.95→100"


def test_describe_piecewise_trims_float_noise() -> None:
    """整数不带 .0，小数不带二进制浮点尾巴。"""
    assert describe_piecewise([(60.0, 100.0), (120.0, 70.0)]) == "分段线性 60→100, 120→70"
