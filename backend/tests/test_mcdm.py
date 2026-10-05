"""用数学性质、手算和独立标量计算验证多准则算法。"""

from __future__ import annotations

import numpy as np
import pytest
from app.engine.mcdm import (
    McdmInputError,
    ahp_weights,
    normalize_weights,
    pareto_front,
    rank_acceptability,
    sensitivity,
    topsis,
)


@pytest.mark.parametrize("size", range(1, 11))
def test_ahp_recovers_consistent_weights(size: int) -> None:
    """a_ij=w_i/w_j 时 Aw=nw，主特征值为 n，CI 与 CR 均为 0。"""
    w = np.arange(1, size + 1, dtype=float)
    w /= w.sum()
    result = ahp_weights(w[:, None] / w[None, :])
    np.testing.assert_allclose(result.weights, w, atol=1e-12)
    assert result.lambda_max == pytest.approx(size)
    assert result.ci == pytest.approx(0, abs=1e-12)
    assert result.cr == pytest.approx(0, abs=1e-12)
    assert result.consistent


@pytest.mark.parametrize(
    "matrix",
    [
        [[1, 2], [2, 1]],
        [[1, 0], [0, 1]],
        [[1, -2], [-0.5, 1]],
        [[2, 2], [0.5, 1]],
        [[1, 2, 3], [0.5, 1, 2]],
        [[1, float("nan")], [1, 1]],
        [[1, float("inf")], [1, 1]],
        [[1], [1, 2]],
        np.empty((0, 0)),
        np.ones((11, 11)),
    ],
)
def test_ahp_rejects_invalid_matrix(matrix: object) -> None:
    with pytest.raises(McdmInputError):
        ahp_weights(matrix)  # type: ignore[arg-type]


def test_ahp_absolute_tolerance_and_inconsistency() -> None:
    a = np.ones((4, 4))
    a[0, 0] += 0.5e-6
    ahp_weights(a)
    a[0, 0] = 1 + 2e-6
    with pytest.raises(McdmInputError, match="对角线"):
        ahp_weights(a)
    a = np.ones((4, 4))
    a[0, 1] = 1 + 0.5e-6
    ahp_weights(a)
    a[0, 1] = 1 + 2e-6
    with pytest.raises(McdmInputError, match="互反"):
        ahp_weights(a)
    result = ahp_weights([[1, 9, 1 / 9], [1 / 9, 1, 9], [9, 1 / 9, 1]])
    assert result.cr == pytest.approx(result.ci / 0.58)
    assert result.cr >= 0.1
    assert not result.consistent


def test_topsis_hand_calculation() -> None:
    # 两列范数都是 5，归一化为 [[3/5,4/5],[4/5,3/5]]。
    # 权重 [3/4,1/4] 后 V=[[0.45,0.20],[0.60,0.15]]。
    # 正理想=[0.60,0.20]，负理想=[0.45,0.15]。
    # 方案 0 的 D+=0.15、D-=0.05，C=0.05/0.20=0.25；方案 1 相反，C=0.75。
    result = topsis(np.array([[3, 4], [4, 3]], dtype=float), [3, 1])
    np.testing.assert_allclose(result.closeness, [0.25, 0.75])
    np.testing.assert_allclose(result.ideal_best, [0.60, 0.20])
    np.testing.assert_allclose(result.ideal_worst, [0.45, 0.15])
    assert result.ranks == [2, 1]
    assert result.schemes[0].distance_to_best == pytest.approx(0.15)


def test_topsis_dominance_and_permutation() -> None:
    scores = np.array([[30, 50, 20, 70], [60, 30, 80, 50], [90, 90, 90, 90]], float)
    w = [0.4, 0.2, 0.3, 0.1]
    baseline = topsis(scores, w)
    assert baseline.ranks[2] == 1
    assert baseline.closeness[2] == pytest.approx(1)
    order = np.array([2, 0, 1])
    permuted = topsis(scores[order], w)
    np.testing.assert_allclose(permuted.closeness, np.array(baseline.closeness)[order])
    np.testing.assert_array_equal(permuted.ranks, np.array(baseline.ranks)[order])


@pytest.mark.parametrize("value", [0.0, 5.0, -5.0])
def test_topsis_identical_schemes(value: float) -> None:
    result = topsis(np.full((3, 4), value), [0.25] * 4)
    assert result.closeness == [0.5] * 3
    assert result.ranks == [1] * 3


def test_topsis_constant_columns_ties_and_costs() -> None:
    scores = np.array([[0, 7, 3], [0, 7, 4], [0, 7, 4], [0, 7, 5]], float)
    result = topsis(scores, [1, 1, 1])
    reference = topsis(scores[:, 2:], [1])
    np.testing.assert_allclose(result.closeness, reference.closeness)
    assert result.ranks == [4, 2, 2, 1]
    cost = topsis(scores, [1, 1, 1], benefit=[True, True, False])
    assert cost.ranks == [1, 2, 2, 4]


def test_topsis_column_scaling_and_large_finite_inputs() -> None:
    scores = np.array([[1, 4], [2, 3], [3, 2]], float)
    reference = topsis(scores, [2, 1])
    result = topsis(scores * [1e300, 1e200], [2e300, 1e300])
    np.testing.assert_allclose(result.closeness, reference.closeness)


@pytest.mark.parametrize("weights", [[0, 0], [-1, 2], [float("nan"), 1], [[1, 2]], []])
def test_invalid_weights(weights: object) -> None:
    with pytest.raises(McdmInputError):
        normalize_weights(weights)  # type: ignore[arg-type]


def test_sensitivity_zero_delta_and_proportional_scaling() -> None:
    scores = np.array([[90, 40, 70, 60], [30, 90, 80, 70]], float)
    w = np.array([0.4, 0.3, 0.2, 0.1])
    result = sensitivity(scores, w, deltas=(0, -0.2, 0.2))
    for cell in result.cells:
        assert sum(cell.weights) == pytest.approx(1)
        assert cell.weights[cell.criterion_index] == pytest.approx(
            w[cell.criterion_index] * (1 + cell.delta)
        )
        others = np.arange(4) != cell.criterion_index
        np.testing.assert_allclose(
            np.array(cell.weights)[others] / w[others],
            np.full(3, (1 - cell.weights[cell.criterion_index]) / w[others].sum()),
        )
        if cell.delta == 0:
            assert cell.ranks == result.baseline_ranks
            assert not cell.rank_changed
    assert result.baseline_ranks == topsis(scores, w).ranks


def test_flip_scan_and_no_flip() -> None:
    # 基准方案 0 获胜。准则 0 扫描从 0 开始时方案 1 获胜，因此翻转点就是 0。
    # 准则 1 增至 0.50 时并列（仍取输入行号最小者），到 0.51 才换成方案 1。
    result = sensitivity([[10, 0], [0, 10]], [0.8, 0.2])
    assert result.flip_points[0].flip_weight == 0
    assert result.flip_points[1].flip_weight == 0.51
    assert result.flip_points[1].new_top_index == 1
    stable = sensitivity([[10, 10], [5, 5]], [0.5, 0.5])
    assert all(p.flip_weight is None for p in stable.flip_points)


def test_sensitivity_one_hot_and_single_criterion() -> None:
    result = sensitivity([[10, 4], [5, 8]], [1, 0], deltas=(0, -0.2))
    assert result.cells[1].weights == pytest.approx([0.8, 0.2])
    for cell in result.cells:
        assert sum(cell.weights) == pytest.approx(1)
    single = sensitivity([[1], [2]], [1])
    assert all(cell.weights == [1] for cell in single.cells)
    assert single.flip_points[0].flip_weight is None


@pytest.mark.parametrize("deltas", [(float("nan"),), (-1.1,)])
def test_invalid_sensitivity_delta(deltas: tuple[float, ...]) -> None:
    with pytest.raises(McdmInputError):
        sensitivity([[1, 2]], [1, 1], deltas=deltas)


def test_acceptability_reproducibility_dominance_and_row_sums() -> None:
    scores = np.array([[90, 90, 90, 90], [30, 50, 40, 60], [50, 40, 60, 30]], float)
    w = [0.4, 0.2, 0.3, 0.1]
    result = rank_acceptability(scores, w, seed=17)
    assert result == rank_acceptability(scores, w, seed=17)
    assert result.first_place_probability == [1, 0, 0]
    np.testing.assert_allclose(np.sum(result.probabilities, axis=1), 1)


def test_acceptability_matches_independent_scalar_topsis() -> None:
    """批量结果必须与逐组用公式计算相同，防止抽样维度或名次计数轴写反。"""
    scores = np.array([[70, 30], [30, 70], [50, 50]], float)
    w = np.array([0.6, 0.4])
    sampled = np.random.default_rng(19).dirichlet(w * 50, size=128)
    counts = np.zeros((3, 3))
    normalized = scores / np.sqrt((scores**2).sum(axis=0))
    for weights in sampled:
        v = normalized * weights
        dp = np.linalg.norm(v - v.max(axis=0), axis=1)
        dm = np.linalg.norm(v - v.min(axis=0), axis=1)
        c = dm / (dp + dm)
        for i in range(3):
            rank = 1 + np.count_nonzero(c > c[i] + 1e-9)
            counts[i, rank - 1] += 1
    result = rank_acceptability(scores, w, n=128, seed=19)
    np.testing.assert_allclose(result.probabilities, counts / 128)


def test_acceptability_zero_weights_and_ties() -> None:
    scores = [[3, 100], [3, 0], [2, 100]]
    result = rank_acceptability(scores, [1, 0])
    assert result.probabilities == [[1, 0, 0], [1, 0, 0], [0, 0, 1]]
    # 多个正权重时，同样只在活跃维度抽样，忽略列的数据变化不影响概率。
    a = rank_acceptability([[1, 3, 100], [3, 1, 0]], [0.4, 0.6, 0], seed=12)
    b = rank_acceptability([[1, 3], [3, 1]], [0.4, 0.6], seed=12)
    assert a.probabilities == b.probabilities


@pytest.mark.parametrize(
    "options",
    [
        {"n": 0},
        {"n": 1.5},
        {"n": True},
        {"concentration": 0},
        {"concentration": float("nan")},
        {"seed": -1},
    ],
)
def test_invalid_acceptability_options(options: dict[str, object]) -> None:
    with pytest.raises(McdmInputError):
        rank_acceptability([[1, 2]], [1, 1], **options)  # type: ignore[arg-type]


def test_pareto_dominators_identical_and_costs() -> None:
    scores = np.array([[3, 3], [1, 1], [3, 3], [2, 4], [2, 2]], float)
    result = pareto_front(scores)
    assert result.non_dominated == [0, 2, 3]
    assert result.dominated_by == {1: [0, 2, 3, 4], 4: [0, 2, 3]}
    cost = pareto_front([[3, 1], [2, 2]], benefit=[True, False])
    assert cost.dominated_by == {1: [0]}
    # 支配按精确不等式判断，不能把一维微小变差忽略成全面占优。
    assert pareto_front([[3, 3 - 1e-10], [2, 3]]).non_dominated == [0, 1]


def test_pure_functions_preserve_inputs_and_global_rng() -> None:
    scores = np.array([[3, 1], [1, 3]], float)
    w = np.array([0.6, 0.4])
    a = w[:, None] / w[None, :]
    before_scores, before_w, before_a = scores.copy(), w.copy(), a.copy()
    state = np.random.get_state()
    ahp_weights(a)
    topsis(scores, w)
    sensitivity(scores, w)
    rank_acceptability(scores, w)
    pareto_front(scores)
    np.testing.assert_array_equal(scores, before_scores)
    np.testing.assert_array_equal(w, before_w)
    np.testing.assert_array_equal(a, before_a)
    after = np.random.get_state()
    assert state[0] == after[0]
    np.testing.assert_array_equal(state[1], after[1])
    assert state[2:] == after[2:]


def test_empty_scheme_arrays() -> None:
    scores = np.empty((0, 4))
    assert topsis(scores, [1] * 4).schemes == []
    assert sensitivity(scores, [1] * 4).baseline_ranks == []
    assert rank_acceptability(scores, [1] * 4).probabilities == []
    assert pareto_front(scores).non_dominated == []
