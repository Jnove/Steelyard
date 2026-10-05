"""多准则决策：AHP 赋权、TOPSIS 排序、敏感性分析、名次概率、帕累托筛选。

这一层是**纯函数**：输入输出都是 numpy 数组或 Pydantic 模型，不读数据库、不调大模型、
不依赖时间；给定输入（蒙特卡洛给定 ``seed``）结果完全可复现。

准则顺序在整个模块里固定为 :data:`CRITERION_ORDER`
（``quality`` / ``structure`` / ``construction`` / ``green``），与
``app/models/eval.py`` 的 ``DimensionKey`` 一致。所有 ``scores`` 参数都是
**m 个方案 × n 个准则**的矩阵，列顺序必须按这个顺序排。

性能约定
--------
前端的权重滑杆会频繁调用排序接口，所以 TOPSIS 的核心算成
:func:`_closeness_batch`——一次吃一批权重向量。敏感性（16 组）、翻转点扫描
（4 × 101 组）与蒙特卡洛（1000 组）都走这条批量路径，整个 ``/rank`` 接口
在 5 个方案时远快于 100 ms 的预算。

答辩会被追问每一步，所以每个公式都写在对应函数的 docstring 里。
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "AhpResult",
    "CRITERION_ORDER",
    "FlipPoint",
    "McdmInputError",
    "ParetoResult",
    "RANDOM_INDEX",
    "RankAcceptabilityResult",
    "SchemeCloseness",
    "SensitivityCell",
    "SensitivityResult",
    "TopsisResult",
    "ahp_weights",
    "normalize_weights",
    "pareto_front",
    "rank_acceptability",
    "ranks_from_closeness",
    "sensitivity",
    "topsis",
]

#: 准则（＝评估维度）的固定顺序。``scores`` 的列、``weights`` 的元素都按这个顺序。
CRITERION_ORDER: tuple[str, ...] = ("quality", "structure", "construction", "green")

#: Saaty 的随机一致性指标 RI，下标 = 矩阵阶数 n（1–10）。
#: ``n <= 2`` 时任何互反矩阵都必然一致，RI 记 0，CR 直接记 0（见 :func:`ahp_weights`）。
RANDOM_INDEX: dict[int, float] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
}

#: CR 低于这个值才认为两两比较矩阵可接受（Saaty 的经验阈值）。
CR_THRESHOLD = 0.1

#: 判断互反性 ``a_ji == 1 / a_ij`` 时允许的绝对误差。
RECIPROCAL_TOLERANCE = 1e-6

#: 比较贴近度是否相等的容差。浮点运算会让本该并列的方案差出 1e-17，
#: 直接用 ``>`` 比较会把它们排成不同名次。
TIE_TOLERANCE = 1e-9

#: 翻转点扫描的步长（规格要求 0.01）。
FLIP_SCAN_STEP = 0.01

BenefitMask = NDArray[np.bool_]


class McdmInputError(ValueError):
    """输入不合法。消息是中文的，会原样出现在接口的 400 响应里。"""


# —— 结果模型 —— #


class AhpResult(BaseModel):
    """AHP 赋权结果。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "AHP 赋权结果",
            "description": "两两比较矩阵解出的权重，以及一致性检验的中间量",
        }
    )

    weights: list[float] = Field(description="归一化后的权重，和为 1，顺序同 CRITERION_ORDER")
    lambda_max: float = Field(description="最大特征值 λmax")
    ci: float = Field(description="一致性指标 CI = (λmax − n) / (n − 1)")
    cr: float = Field(description="一致性比率 CR = CI / RI；n ≤ 2 时记 0")
    ri: float = Field(description="本阶数对应的随机一致性指标 RI")
    consistent: bool = Field(description=f"CR < {CR_THRESHOLD} 才算通过一致性检验")


class SchemeCloseness(BaseModel):
    """单个方案的 TOPSIS 中间量与结果。"""

    model_config = ConfigDict(json_schema_extra={"title": "方案贴近度"})

    index: int = Field(description="在输入 scores 里的行号，从 0 开始")
    closeness: float = Field(description="贴近度 C = D⁻ / (D⁺ + D⁻)，0–1")
    distance_to_best: float = Field(description="到正理想解的欧氏距离 D⁺")
    distance_to_worst: float = Field(description="到负理想解的欧氏距离 D⁻")
    rank: int = Field(description="名次，从 1 开始；并列时名次相同")


class TopsisResult(BaseModel):
    """TOPSIS 排序结果。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "TOPSIS 排序结果",
            "description": "贴近度、名次与正负理想解，供报告溯源",
        }
    )

    schemes: list[SchemeCloseness] = Field(description="按输入顺序给出，不重排")
    ideal_best: list[float] = Field(description="正理想解 v⁺（加权归一化空间里）")
    ideal_worst: list[float] = Field(description="负理想解 v⁻")
    weights: list[float] = Field(description="本次排序实际使用的权重")

    @property
    def closeness(self) -> list[float]:
        return [s.closeness for s in self.schemes]

    @property
    def ranks(self) -> list[int]:
        return [s.rank for s in self.schemes]

    @property
    def top_index(self) -> int | None:
        """第一名的行号；没有方案时为 ``None``。并列第一时取行号最小的那个。"""
        firsts = [s.index for s in self.schemes if s.rank == 1]
        return firsts[0] if firsts else None


class SensitivityCell(BaseModel):
    """敏感性表里的一格：某个准则的权重乘上 ``(1 + delta)`` 之后重新排序的结果。"""

    model_config = ConfigDict(json_schema_extra={"title": "敏感性单元"})

    criterion: str = Field(description="被扰动的准则名")
    criterion_index: int = Field(description="被扰动的准则下标")
    delta: float = Field(description="扰动比例，如 -0.2 表示该准则权重下调 20%")
    weights: list[float] = Field(description="扰动并重新归一化后的权重，和为 1")
    top_index: int | None = Field(description="该权重下的第一名方案行号")
    ranks: list[int] = Field(description="该权重下每个方案的名次，按输入顺序")
    rank_changed: bool = Field(description="与基准排名相比，是否有任一方案名次变化")
    top_changed: bool = Field(description="第一名是否换人")


class FlipPoint(BaseModel):
    """某个准则的"翻转点"：权重调到多少时第一名换人。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "翻转点",
            "description": "该准则权重在 [0, 1] 内扫描时，第一名首次改变的权重值",
        }
    )

    criterion: str = Field(description="准则名")
    criterion_index: int = Field(description="准则下标")
    baseline_weight: float = Field(
        description="该准则当前的权重。翻转点在它之下表示「调低会翻」，之上表示「调高会翻」"
    )
    flip_weight: float | None = Field(
        description="第一名首次改变时该准则的权重；整个区间内都不变则为 null"
    )
    new_top_index: int | None = Field(description="翻转后的第一名行号；没有翻转则为 null")


class SensitivityResult(BaseModel):
    """敏感性分析结果：扰动表 + 翻转点。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "敏感性分析",
            "description": "逐准则扰动权重后的排名变化，以及第一名的翻转点",
        }
    )

    baseline_weights: list[float] = Field(description="基准权重")
    baseline_ranks: list[int] = Field(description="基准排名，按输入顺序")
    baseline_top_index: int | None = Field(description="基准第一名行号")
    cells: list[SensitivityCell] = Field(description="扰动表，按 (准则, delta) 展开")
    flip_points: list[FlipPoint] = Field(description="每个准则一条")

    @property
    def any_rank_changed(self) -> bool:
        """有任何一格排名发生变化——结论「不稳」的最粗判据。"""
        return any(cell.rank_changed for cell in self.cells)


class RankAcceptabilityResult(BaseModel):
    """名次概率矩阵（蒙特卡洛）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "名次概率",
            "description": "在基准权重附近随机抽样，统计每个方案落到每个名次的概率",
        }
    )

    probabilities: list[list[float]] = Field(
        description="第 i 行第 r 列 = 方案 i 排第 (r+1) 名的概率；每行和为 1"
    )
    first_place_probability: list[float] = Field(description="每个方案排第一的概率")
    samples: int = Field(description="抽样组数")
    concentration: float = Field(description="Dirichlet 集中度；越大越贴近基准权重")
    seed: int = Field(description="随机种子；同 seed 结果完全可复现")


class ParetoResult(BaseModel):
    """帕累托筛选结果。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "帕累托筛选",
            "description": "非劣方案，以及每个被支配方案被谁支配",
        }
    )

    non_dominated: list[int] = Field(description="非劣（帕累托最优）方案的行号")
    dominated_by: dict[int, list[int]] = Field(
        description="键是被支配方案的行号，值是支配它的方案行号列表"
    )

    @property
    def dominated(self) -> list[int]:
        return sorted(self.dominated_by)


# —— 工具 —— #


def _as_matrix(scores: NDArray[np.float64] | list[list[float]], what: str) -> NDArray[np.float64]:
    """把输入转成 2 维 float 数组并做基本校验。"""
    try:
        array = np.asarray(scores, dtype=float)
    except (ValueError, TypeError) as exc:
        raise McdmInputError(f"{what} 必须是各行长度相同的数字矩阵") from exc
    if array.ndim != 2:
        raise McdmInputError(f"{what} 必须是二维矩阵（方案 × 准则），当前是 {array.ndim} 维")
    if array.size and not np.isfinite(array).all():
        raise McdmInputError(f"{what} 里出现了 NaN 或无穷大，请检查上游的评估结果")
    return array


def normalize_weights(weights: NDArray[np.float64] | list[float]) -> NDArray[np.float64]:
    """把权重归一化成和为 1。

    Raises:
        McdmInputError: 权重含负数、或全部为 0（无法归一化）。
    """
    try:
        array = np.asarray(weights, dtype=float)
    except (ValueError, TypeError) as exc:
        raise McdmInputError("权重必须是一维数字数组") from exc
    if array.ndim != 1:
        raise McdmInputError("权重必须是一维数字数组")
    if array.size == 0:
        raise McdmInputError("权重不能为空")
    if not np.isfinite(array).all():
        raise McdmInputError("权重里出现了 NaN 或无穷大")
    if (array < 0).any():
        raise McdmInputError(f"权重不能为负数，当前是 {array.tolist()}")
    largest = array.max()
    if largest <= 0:
        raise McdmInputError("权重全部为 0，无法归一化")
    # 先除最大元素，防止有限但很大的权重求和溢出。
    scaled = array / largest
    return scaled / scaled.sum()


def _benefit_mask(benefit: list[bool] | NDArray[np.bool_] | None, n_criteria: int) -> BenefitMask:
    """准则类型掩码：``True`` 为效益型（越大越好），``False`` 为成本型（越小越好）。

    默认全部为效益型——四个维度得分都是"越高越好"。
    """
    if benefit is None:
        return np.ones(n_criteria, dtype=bool)
    mask = np.asarray(benefit, dtype=bool).ravel()
    if mask.size != n_criteria:
        raise McdmInputError(f"benefit 长度 {mask.size} 与准则数 {n_criteria} 不一致")
    return mask


def ranks_from_closeness(closeness: NDArray[np.float64]) -> NDArray[np.int_]:
    """贴近度 → 名次（越大越靠前，从 1 开始，并列时名次相同）。

    名次 = 1 + 严格优于自己的方案数（体育竞赛式排名：1, 2, 2, 4）。
    比较时带 :data:`TIE_TOLERANCE` 容差，免得浮点尾差把本该并列的拆开。

    支持批量：输入 ``(m,)`` 返回 ``(m,)``；输入 ``(k, m)`` 按行独立排名返回 ``(k, m)``。
    """
    values = np.asarray(closeness, dtype=float)
    if values.ndim == 1:
        better = values[None, :] > (values[:, None] + TIE_TOLERANCE)
        return 1 + better.sum(axis=1).astype(int)
    # (k, m)：[s, i, j] = 第 s 组里方案 j 是否严格优于方案 i
    better = values[:, None, :] > (values[:, :, None] + TIE_TOLERANCE)
    return 1 + better.sum(axis=2).astype(int)


# —— 1. AHP 赋权 —— #


def ahp_weights(matrix: NDArray[np.float64] | list[list[float]]) -> AhpResult:
    """用两两比较矩阵解出权重，并做一致性检验。

    步骤（Saaty 的特征向量法）：

    1. 校验 A 是 n×n 正互反矩阵：元素为正、对角线为 1、``a_ji = 1 / a_ij``；
    2. 解特征值问题 ``A w = λ w``，取最大特征值 λmax 对应的特征向量；
       特征向量取实部、取绝对值后归一化成和为 1，即权重 w；
    3. 一致性指标 ``CI = (λmax − n) / (n − 1)``；
    4. 一致性比率 ``CR = CI / RI``，RI 查 :data:`RANDOM_INDEX`；
       ``CR < 0.1`` 才接受这份判断。

    为什么取实部与绝对值：正互反矩阵的 λmax 与对应特征向量在理论上都是实的正的
    （Perron–Frobenius 定理），但 ``numpy.linalg.eig`` 会返回复数类型，
    且特征向量的整体符号不定，所以取实部再取绝对值。

    Args:
        matrix: n×n 两两比较矩阵。``a_ij`` 表示"准则 i 比准则 j 重要多少倍"。

    Returns:
        :class:`AhpResult`——权重、λmax、CI、CR、RI 与是否通过一致性检验。

    Raises:
        McdmInputError: 不是方阵、元素非正、对角线不为 1、或不满足互反性。

    示例（由已知权重构造的完全一致矩阵，应当原样还原权重且 CR = 0）：
        >>> w = [0.4, 0.3, 0.2, 0.1]
        >>> a = [[wi / wj for wj in w] for wi in w]
        >>> result = ahp_weights(a)
        >>> [round(x, 6) for x in result.weights]
        [0.4, 0.3, 0.2, 0.1]
        >>> round(result.cr, 9)
        0.0
    """
    array = _as_matrix(matrix, "两两比较矩阵")
    n = array.shape[0]
    if array.shape[1] != n:
        raise McdmInputError(f"两两比较矩阵必须是方阵，当前是 {array.shape[0]}×{array.shape[1]}")
    if n == 0:
        raise McdmInputError("两两比较矩阵不能为空")
    if n not in RANDOM_INDEX:
        raise McdmInputError("RI 表只支持 1–10 阶矩阵，请减少准则数")
    if (array <= 0).any():
        raise McdmInputError("两两比较矩阵的元素必须全为正数（用 1/3 这样的分数表示「不如」）")
    diagonal = np.diag(array)
    if not np.allclose(diagonal, 1.0, atol=RECIPROCAL_TOLERANCE, rtol=0):
        raise McdmInputError(f"两两比较矩阵的对角线必须全为 1，当前是 {diagonal.tolist()}")
    if not np.allclose(array, 1.0 / array.T, atol=RECIPROCAL_TOLERANCE, rtol=0):
        raise McdmInputError(
            "两两比较矩阵必须互反：如果 a[i][j] = 3，那么 a[j][i] 必须是 1/3。"
            f"允许的误差是 {RECIPROCAL_TOLERANCE:g}，请检查上三角与下三角是否对应"
        )

    eigenvalues, eigenvectors = np.linalg.eig(array)
    principal = int(np.argmax(eigenvalues.real))
    lambda_max = float(eigenvalues.real[principal])
    vector = np.abs(eigenvectors[:, principal].real)
    total = vector.sum()
    if total <= 0:  # pragma: no cover - 正互反矩阵不会走到这里
        raise McdmInputError("解出的特征向量全为 0，无法归一化，请检查矩阵数值")
    weights = vector / total

    ri = RANDOM_INDEX[n]
    if n <= 2:
        # 1 阶与 2 阶的互反矩阵必然一致（λmax 恒等于 n），RI 为 0，直接记 CR = 0。
        ci = 0.0
        cr = 0.0
    else:
        ci = (lambda_max - n) / (n - 1)
        cr = ci / ri if ri > 0 else 0.0

    return AhpResult(
        weights=weights.tolist(),
        lambda_max=lambda_max,
        ci=float(ci),
        cr=float(cr),
        ri=float(ri),
        consistent=bool(cr < CR_THRESHOLD),
    )


# —— 2. TOPSIS —— #


def _normalized(scores: NDArray[np.float64]) -> NDArray[np.float64]:
    """向量归一化：``r_ij = x_ij / sqrt(Σ_i x_ij²)``。

    某一列全为 0 时该列范数为 0，直接把整列置 0（而不是除以 0）——
    这一列对所有方案都一样，本来就不该影响排序。
    """
    if scores.shape[0] == 0:
        return scores.copy()
    # 按列先缩放再求范数，等价于原公式，同时避免大数平方溢出。
    scale = np.max(np.abs(scores), axis=0)
    scaled = scores / np.where(scale > 0, scale, 1.0)
    norms = np.sqrt((scaled**2).sum(axis=0))
    safe = np.where(norms > 0, norms, 1.0)
    return scaled / safe


def _closeness_batch(
    scores: NDArray[np.float64],
    weights_batch: NDArray[np.float64],
    benefit: BenefitMask,
) -> NDArray[np.float64]:
    """一次算一批权重下的贴近度。

    Args:
        scores: ``(m, n)`` 方案 × 准则。
        weights_batch: ``(k, n)`` k 组权重。
        benefit: ``(n,)`` 效益型 / 成本型掩码。

    Returns:
        ``(k, m)`` 每组权重下每个方案的贴近度。

    这是整个模块的热点：敏感性、翻转点扫描、蒙特卡洛都调它。写成批量是因为
    逐组调用的 Python 开销会让 404 次翻转点扫描变成毫秒级里的大头。
    """
    if scores.shape[0] == 0:
        return np.empty((weights_batch.shape[0], 0), dtype=float)
    normalized = _normalized(scores)  # (m, n)
    weighted = weights_batch[:, None, :] * normalized[None, :, :]  # (k, m, n)

    column_max = weighted.max(axis=1)  # (k, n)
    column_min = weighted.min(axis=1)  # (k, n)
    # 效益型准则以列最大为正理想、列最小为负理想；成本型反过来。
    ideal_best = np.where(benefit[None, :], column_max, column_min)  # (k, n)
    ideal_worst = np.where(benefit[None, :], column_min, column_max)

    d_plus = np.sqrt(((weighted - ideal_best[:, None, :]) ** 2).sum(axis=2))  # (k, m)
    d_minus = np.sqrt(((weighted - ideal_worst[:, None, :]) ** 2).sum(axis=2))

    denominator = d_plus + d_minus
    # D⁺ + D⁻ = 0 只会在"所有方案在所有准则上都相同"时出现（正负理想解重合）。
    # 此时谁也不比谁好，贴近度统一记 0.5，而不是除以 0。
    return np.where(denominator > 0, d_minus / np.where(denominator > 0, denominator, 1.0), 0.5)


def topsis(
    scores: NDArray[np.float64] | list[list[float]],
    weights: NDArray[np.float64] | list[float],
    benefit: list[bool] | NDArray[np.bool_] | None = None,
) -> TopsisResult:
    """TOPSIS 排序（逼近理想解排序法）。

    步骤：

    1. **向量归一化**消除量纲：``r_ij = x_ij / sqrt(Σ_i x_ij²)``；
    2. **加权**：``v_ij = w_j · r_ij``；
    3. **正负理想解**：效益型准则取 ``v⁺_j = max_i v_ij``、``v⁻_j = min_i v_ij``，
       成本型准则反过来；
    4. **欧氏距离**：``D⁺_i = sqrt(Σ_j (v_ij − v⁺_j)²)``，``D⁻_i`` 同理对 ``v⁻``；
    5. **贴近度**：``C_i = D⁻_i / (D⁺_i + D⁻_i)``，越大越好。

    边界处理：

    - 某一列全为 0 → 该列归一化后置 0，不出现除零；
    - 某一列所有方案相等 → ``v⁺_j = v⁻_j``，该列对两个距离的贡献都是 0，自然不影响排序；
    - ``D⁺ + D⁻ = 0``（所有方案完全相同）→ ``C`` 统一记 0.5；
    - 贴近度相同（含浮点尾差，容差 :data:`TIE_TOLERANCE`）→ 名次相同。

    Args:
        scores: ``(m, n)`` 方案 × 准则，列序同 :data:`CRITERION_ORDER`。
        weights: ``(n,)`` 权重；内部会归一化成和为 1。
        benefit: ``(n,)`` 每个准则是否为效益型；默认全部效益型。

    Returns:
        :class:`TopsisResult`，``schemes`` 按输入顺序排列（**不重排**），名次写在
        每个元素的 ``rank`` 里。

    Raises:
        McdmInputError: 维度不匹配、含 NaN、权重非法。
    """
    matrix = _as_matrix(scores, "scores")
    n_schemes, n_criteria = matrix.shape
    normalized_weights = normalize_weights(weights)
    if normalized_weights.size != n_criteria:
        raise McdmInputError(f"权重个数 {normalized_weights.size} 与准则数 {n_criteria} 不一致")
    mask = _benefit_mask(benefit, n_criteria)

    if n_schemes == 0:
        return TopsisResult(
            schemes=[],
            ideal_best=[0.0] * n_criteria,
            ideal_worst=[0.0] * n_criteria,
            weights=normalized_weights.tolist(),
        )

    normalized = _normalized(matrix)
    weighted = normalized_weights[None, :] * normalized
    column_max = weighted.max(axis=0)
    column_min = weighted.min(axis=0)
    ideal_best = np.where(mask, column_max, column_min)
    ideal_worst = np.where(mask, column_min, column_max)

    d_plus = np.sqrt(((weighted - ideal_best) ** 2).sum(axis=1))
    d_minus = np.sqrt(((weighted - ideal_worst) ** 2).sum(axis=1))
    closeness = _closeness_batch(matrix, normalized_weights[None, :], mask)[0]
    ranks = ranks_from_closeness(closeness)

    return TopsisResult(
        schemes=[
            SchemeCloseness(
                index=i,
                closeness=float(closeness[i]),
                distance_to_best=float(d_plus[i]),
                distance_to_worst=float(d_minus[i]),
                rank=int(ranks[i]),
            )
            for i in range(n_schemes)
        ],
        ideal_best=ideal_best.tolist(),
        ideal_worst=ideal_worst.tolist(),
        weights=normalized_weights.tolist(),
    )


# —— 3. 敏感性分析 —— #


def _perturb(weights: NDArray[np.float64], index: int, new_weight: float) -> NDArray[np.float64]:
    """把第 ``index`` 个权重设成 ``new_weight``，其余权重按原比例缩放使总和为 1。

    ``new_weight`` 会被夹到 ``[0, 1]``。其余权重原本全为 0（或只有一个准则）时
    没有"原比例"可循，此时把剩余份额平均分给它们。
    """
    perturbed = np.array(weights, dtype=float)
    target = float(np.clip(new_weight, 0.0, 1.0))
    perturbed[index] = target

    others = np.ones(perturbed.size, dtype=bool)
    others[index] = False
    remaining = 1.0 - target
    others_total = weights[others].sum()

    if others.sum() == 0:
        # 只有一个准则，权重只能是 1。
        perturbed[index] = 1.0
    elif others_total > 0:
        perturbed[others] = weights[others] * (remaining / others_total)
    else:
        perturbed[others] = remaining / others.sum()
    return perturbed


def sensitivity(
    scores: NDArray[np.float64] | list[list[float]],
    weights: NDArray[np.float64] | list[float],
    deltas: tuple[float, ...] = (-0.2, -0.1, 0.1, 0.2),
    benefit: list[bool] | NDArray[np.bool_] | None = None,
    criterion_names: tuple[str, ...] | None = None,
) -> SensitivityResult:
    """权重敏感性分析：扰动表 + 第一名的翻转点。

    **扰动表**：对每个准则 i 与每个 ``delta``，令 ``w_i ← w_i × (1 + delta)``，
    其余权重按原比例缩放使总和仍为 1，重新跑一次 TOPSIS，记下第一名与排名是否变化。

    注意 ``w_i × (1 + delta)`` 是**相对**扰动：``w_i`` 本来是 0 时乘任何系数还是 0，
    这一格的排名自然不会变，不是 bug。

    **翻转点**：对每个准则，把它的权重从 0 到 1 以 :data:`FLIP_SCAN_STEP` 步长扫一遍
    （其余权重同样按原比例补足到 1），找出第一名**首次**与基准不同时的那个权重值。
    整个区间内第一名都不变则为 ``None``。

    返回里同时给出 ``baseline_weight``：翻转点落在它**之下**说明"把这个准则调低会翻"，
    落在**之上**说明"调高会翻"，前端据此才能把翻转点画在滑杆的正确一侧。

    Args:
        scores: ``(m, n)`` 方案 × 准则。
        weights: 基准权重。
        deltas: 扰动比例。含 ``0.0`` 时那一格必然与基准完全一致。
        benefit: 准则类型掩码；默认全部效益型。
        criterion_names: 准则名，默认取 :data:`CRITERION_ORDER` 的前 n 个。

    Returns:
        :class:`SensitivityResult`。
    """
    matrix = _as_matrix(scores, "scores")
    n_schemes, n_criteria = matrix.shape
    base = normalize_weights(weights)
    if base.size != n_criteria:
        raise McdmInputError(f"权重个数 {base.size} 与准则数 {n_criteria} 不一致")
    mask = _benefit_mask(benefit, n_criteria)
    names = criterion_names or CRITERION_ORDER[:n_criteria]
    if len(names) != n_criteria:
        raise McdmInputError("准则名称个数与 scores 的列数不一致")
    if any(not np.isfinite(delta) or delta < -1 for delta in deltas):
        raise McdmInputError("扰动比例必须是有限数且不能小于 -1")

    baseline_closeness = _closeness_batch(matrix, base[None, :], mask)[0]
    baseline_ranks = ranks_from_closeness(baseline_closeness)
    baseline_top = _first_place(baseline_ranks)

    # —— 扰动表：把所有 (准则, delta) 的权重一次算完 ——
    cells: list[SensitivityCell] = []
    if n_schemes and deltas:
        perturbed_weights = np.array(
            [
                _perturb(base, i, base[i] * (1.0 + delta))
                for i in range(n_criteria)
                for delta in deltas
            ]
        )
        batch_closeness = _closeness_batch(matrix, perturbed_weights, mask)
        batch_ranks = ranks_from_closeness(batch_closeness)
        for position, (i, delta) in enumerate(
            (i, delta) for i in range(n_criteria) for delta in deltas
        ):
            ranks = batch_ranks[position]
            top = _first_place(ranks)
            cells.append(
                SensitivityCell(
                    criterion=names[i],
                    criterion_index=i,
                    delta=float(delta),
                    weights=perturbed_weights[position].tolist(),
                    top_index=top,
                    ranks=ranks.tolist(),
                    rank_changed=bool((ranks != baseline_ranks).any()),
                    top_changed=bool(top != baseline_top),
                )
            )

    return SensitivityResult(
        baseline_weights=base.tolist(),
        baseline_ranks=baseline_ranks.tolist() if n_schemes else [],
        baseline_top_index=baseline_top,
        cells=cells,
        flip_points=_flip_points(matrix, base, mask, names, baseline_top),
    )


def _first_place(ranks: NDArray[np.int_]) -> int | None:
    """名次数组里第一名的行号；并列第一时取行号最小的。没有方案时返回 ``None``。"""
    firsts = np.flatnonzero(ranks == 1)
    return int(firsts[0]) if firsts.size else None


def _flip_points(
    scores: NDArray[np.float64],
    base: NDArray[np.float64],
    mask: BenefitMask,
    names: tuple[str, ...],
    baseline_top: int | None,
) -> list[FlipPoint]:
    """逐准则扫描权重，找第一名首次改变的位置。见 :func:`sensitivity` 的说明。"""
    n_criteria = base.size
    if scores.shape[0] == 0 or baseline_top is None:
        return [
            FlipPoint(
                criterion=names[i],
                criterion_index=i,
                baseline_weight=float(base[i]),
                flip_weight=None,
                new_top_index=None,
            )
            for i in range(n_criteria)
        ]

    steps = np.round(np.arange(0.0, 1.0 + FLIP_SCAN_STEP / 2, FLIP_SCAN_STEP), 2)
    out: list[FlipPoint] = []
    for i in range(n_criteria):
        candidates = np.array([_perturb(base, i, float(t)) for t in steps])
        closeness = _closeness_batch(scores, candidates, mask)
        ranks = ranks_from_closeness(closeness)
        tops = np.array([_first_place(row) for row in ranks])
        changed = np.flatnonzero(tops != baseline_top)
        if changed.size:
            first = int(changed[0])
            out.append(
                FlipPoint(
                    criterion=names[i],
                    criterion_index=i,
                    baseline_weight=float(base[i]),
                    flip_weight=float(steps[first]),
                    new_top_index=int(tops[first]),
                )
            )
        else:
            out.append(
                FlipPoint(
                    criterion=names[i],
                    criterion_index=i,
                    baseline_weight=float(base[i]),
                    flip_weight=None,
                    new_top_index=None,
                )
            )
    return out


# —— 4. 名次概率（蒙特卡洛） —— #


def rank_acceptability(
    scores: NDArray[np.float64] | list[list[float]],
    base_weights: NDArray[np.float64] | list[float],
    n: int = 1000,
    concentration: float = 50.0,
    seed: int = 0,
    benefit: list[bool] | NDArray[np.bool_] | None = None,
) -> RankAcceptabilityResult:
    """在基准权重附近随机抽权重，统计每个方案落到每个名次的概率。

    步骤：

    1. 以 ``α = base_weights × concentration`` 为参数从 Dirichlet 分布抽 ``n`` 组权重。
       Dirichlet 抽出的向量天然和为 1，期望正比于 ``base_weights``，
       ``concentration`` 越大抽样越集中在基准权重附近；
    2. 一次性（向量化）算出这 ``n`` 组权重下的贴近度与名次；
    3. ``probabilities[i][r]`` = 方案 i 排第 ``r+1`` 名的频率。

    零权重维度固定为 0，只在正权重维度上抽样；只有一个正权重时该维度固定为 1。
    并列使用竞赛名次（如 1、1、3），因此每行和为 1，但每列不一定和为 1。

    这里的概率描述指定 Dirichlet 权重模型下的排名频率；
    它随基准权重和集中度变化，不是方案客观最优的置信度。

    Args:
        scores: ``(m, n)`` 方案 × 准则。
        base_weights: 基准权重。
        n: 抽样组数。
        concentration: Dirichlet 集中度。
        seed: 随机种子；**同 seed 结果完全可复现**。
        benefit: 准则类型掩码；默认全部效益型。

    Returns:
        :class:`RankAcceptabilityResult`，每行概率和为 1。
    """
    matrix = _as_matrix(scores, "scores")
    n_schemes, n_criteria = matrix.shape
    base = normalize_weights(base_weights)
    if base.size != n_criteria:
        raise McdmInputError(f"权重个数 {base.size} 与准则数 {n_criteria} 不一致")
    if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n <= 0:
        raise McdmInputError(f"抽样组数必须是正整数，当前是 {n}")
    if not np.isfinite(concentration) or concentration <= 0:
        raise McdmInputError(f"集中度必须是正数，当前是 {concentration}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise McdmInputError("随机种子必须是非负整数")
    mask = _benefit_mask(benefit, n_criteria)

    if n_schemes == 0:
        return RankAcceptabilityResult(
            probabilities=[],
            first_place_probability=[],
            samples=n,
            concentration=float(concentration),
            seed=seed,
        )

    rng = np.random.default_rng(seed)
    active = base > 0
    sampled = np.zeros((n, n_criteria), dtype=float)
    if active.sum() == 1:
        sampled[:, active] = 1.0
    else:
        sampled[:, active] = rng.dirichlet(base[active] * concentration, size=n)

    closeness = _closeness_batch(matrix, sampled, mask)  # (n, m)
    ranks = ranks_from_closeness(closeness)  # (n, m)

    # 名次取值 1..m，统计每个方案每个名次的频率。
    positions = np.arange(1, n_schemes + 1)
    counts = (ranks[:, :, None] == positions[None, None, :]).sum(axis=0)  # (m, m)
    probabilities = counts / n

    return RankAcceptabilityResult(
        probabilities=probabilities.tolist(),
        first_place_probability=probabilities[:, 0].tolist(),
        samples=n,
        concentration=float(concentration),
        seed=seed,
    )


# —— 5. 帕累托筛选 —— #


def pareto_front(
    scores: NDArray[np.float64] | list[list[float]],
    benefit: list[bool] | NDArray[np.bool_] | None = None,
) -> ParetoResult:
    """帕累托筛选：找出非劣方案，并记下每个被支配方案被谁支配。

    **支配关系**：方案 A 支配方案 B，当且仅当 A 在**所有**准则上都不差于 B，
    且在**至少一个**准则上严格更好。

    - 完全相同的两个方案**互不支配**（没有"至少一个严格更好"）；
    - 非劣方案之间是真正的取舍——看板上高亮它们，等于告诉用户
      "这几个之间没有谁全面更好，得由你按偏好选"。

    成本型准则（``benefit`` 里为 ``False``）在比较前取相反数，这样统一按"越大越好"处理。

    Args:
        scores: ``(m, n)`` 方案 × 准则。
        benefit: 准则类型掩码；默认全部效益型。

    Returns:
        :class:`ParetoResult`。``non_dominated`` 升序，``dominated_by`` 的值也升序。
    """
    matrix = _as_matrix(scores, "scores")
    n_schemes, n_criteria = matrix.shape
    mask = _benefit_mask(benefit, n_criteria)
    # 统一成"越大越好"：成本型准则取相反数。
    oriented = np.where(mask[None, :], matrix, -matrix)

    if n_schemes == 0:
        return ParetoResult(non_dominated=[], dominated_by={})

    # [a, b, j] = 方案 a 在准则 j 上是否不差于 / 严格好于 方案 b
    at_least_as_good = oriented[:, None, :] >= oriented[None, :, :]
    strictly_better = oriented[:, None, :] > oriented[None, :, :]
    dominates = at_least_as_good.all(axis=2) & strictly_better.any(axis=2)  # [a, b]

    dominated_by: dict[int, list[int]] = {}
    for b in range(n_schemes):
        dominators = np.flatnonzero(dominates[:, b])
        if dominators.size:
            dominated_by[b] = [int(a) for a in dominators]

    non_dominated = [i for i in range(n_schemes) if i not in dominated_by]
    return ParetoResult(non_dominated=non_dominated, dominated_by=dominated_by)


# —— 权重来源 —— #

WeightSource = Literal["role", "weights", "pairwise_matrix"]
"""排序权重的三种来源，与 ``POST /api/projects/{id}/rank`` 的入参对应。"""
