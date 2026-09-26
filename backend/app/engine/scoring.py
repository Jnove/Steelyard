"""评分函数：把指标的真实取值映射成 0–100 分。

目前只有一种评分方式 ``piecewise``（分段线性），它足以表达规则作者的三种诉求：

- **越大越好**：分数序列递增，如 ``[[0.5, 0], [0.8, 70], [0.95, 100]]``；
- **越小越好**：横坐标仍然递增，分数序列递减，如 ``[[60, 100], [200, 0]]``；
- **适中最好**：分数序列先升后降，如 ``[[0.2, 0], [0.55, 100], [0.9, 0]]``。

三种形态共用同一套插值逻辑，规则作者不需要学额外语法——这是 ``points`` 只约束
"横坐标严格递增"而不约束纵坐标单调性的原因。

约定（与 ``check_rules`` 的校验一致）：

- ``points`` 至少 2 个点，横坐标 **严格递增**，纵坐标在 0–100 之间；
- 取值落在两端之外时 **取端点分数**（截断，不做外推）——外推会得出负分或超过 100 分，
  对非程序员来说是难以解释的结果。
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = [
    "MIN_POINTS",
    "SCORE_MAX",
    "SCORE_MIN",
    "describe_piecewise",
    "piecewise_score",
]

#: 分数合法区间。``check_rules`` 与 Pydantic 模型都用这两个常量校验 ``points``。
SCORE_MIN = 0.0
SCORE_MAX = 100.0
#: ``points`` 至少要有两个控制点才能连成一条线。
MIN_POINTS = 2

Point = tuple[float, float]


def piecewise_score(value: float, points: Sequence[Point]) -> float:
    """分段线性插值求分。

    Args:
        value: 指标的真实取值。
        points: 控制点序列 ``[(指标值, 分数), ...]``，横坐标必须严格递增。

    Returns:
        0–100 的分数。取值小于第一个控制点取第一个分数，大于最后一个控制点取最后一个分数。

    Raises:
        ValueError: ``points`` 少于 2 个点，或横坐标不是严格递增。
            正常流程里这两种错误在规则加载阶段就已经被 ``RuleDef`` 拦下，
            这里再判一次是为了让直接调用本函数的人也拿到明确报错。

    示例：
        >>> piecewise_score(0.8, [(0.5, 0.0), (0.8, 70.0), (0.95, 100.0)])
        70.0
        >>> piecewise_score(0.875, [(0.5, 0.0), (0.8, 70.0), (0.95, 100.0)])
        85.0
        >>> piecewise_score(0.1, [(0.5, 0.0), (0.95, 100.0)])  # 左端外截断
        0.0
    """
    if len(points) < MIN_POINTS:
        raise ValueError(f"points 至少需要 {MIN_POINTS} 个控制点，当前只有 {len(points)} 个")

    xs = [float(x) for x, _ in points]
    ys = [float(y) for _, y in points]
    for i in range(1, len(xs)):
        if xs[i] <= xs[i - 1]:
            raise ValueError(f"points 的横坐标必须严格递增，当前是 {xs}")

    # 两端截断：不做线性外推，避免出现负分或超过 100 分。
    if value <= xs[0]:
        return ys[0]
    if value >= xs[-1]:
        return ys[-1]

    # 找到 value 落在哪一段，然后在该段上线性插值。
    for i in range(1, len(xs)):
        if value <= xs[i]:
            x0, x1 = xs[i - 1], xs[i]
            y0, y1 = ys[i - 1], ys[i]
            ratio = (value - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)

    # 上面的循环必然命中（value < xs[-1] 已由前面的截断保证），这里只是让类型检查满意。
    return ys[-1]  # pragma: no cover


def describe_piecewise(points: Sequence[Point]) -> str:
    """把控制点渲染成人类可读的公式字符串，写进结果的 ``formula`` 字段。

    格式与 AGENTS.md 结果 JSON 示例一致：``分段线性 0.5→0, 0.95→100``。

    示例：
        >>> describe_piecewise([(0.5, 0.0), (0.95, 100.0)])
        '分段线性 0.5→0, 0.95→100'
    """
    parts = [f"{_trim(x)}→{_trim(y)}" for x, y in points]
    return "分段线性 " + ", ".join(parts)


def _trim(number: float) -> str:
    """去掉浮点数末尾无意义的 ``.0``，让公式字符串读起来干净。"""
    as_float = float(number)
    if as_float.is_integer():
        return str(int(as_float))
    # 控制点由人手写，保留原始精度就够；round 到 6 位是为了消除二进制浮点误差尾巴。
    return f"{round(as_float, 6):g}"
