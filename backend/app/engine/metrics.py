"""派生量（derived quantity）的集中定义。

规则作者在 YAML 里可以像用普通字段一样引用这里的名字，引擎在评估时先把它们算出来，
再连同项目层、方案层的原始字段一起构成表达式的命名空间。

设计要点
--------
- **集中定义**：新增派生量只改这个文件；``scripts/gen_field_table.py`` 会从这里读取，
  自动渲染进 ``docs/fields.generated.md``，规则作者看到的字段表永远和代码一致。
- **每个派生量自带中文名与公式字符串**：``formula`` 会原样写进评估结果的 ``formula``
  字段，这是报告可溯源的基础——看报告的人能直接看到"这个数是怎么算出来的"。
- **缺数据不抛异常**：任一依赖字段为空（或分母为 0）时返回 ``None``，
  由调用方决定记成 ``insufficient_data`` 还是跳过计分。
- ``compute`` 与 ``formula`` 必须语义一致，由 ``tests/test_metrics.py`` 用表达式求值
  交叉验证，防止改了公式忘了改注释。

单位与量纲约定（与 AGENTS.md 一致）：长度 m、面积 m²、体积 m³，比例类一律 0–1 小数。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DERIVED_BY_NAME",
    "DERIVED_QUANTITIES",
    "DerivedQuantity",
    "DerivedValue",
    "compute_derived",
    "derived_names",
]


def _num(value: Any) -> float | None:
    """把命名空间里的值转成 float；不是数字（含 None / bool / 字符串）就返回 None。

    ``bool`` 被显式排除：``True`` 在 Python 里等于 1，但用布尔字段去算面积比显然是笔误，
    宁可当缺数据处理。
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _div(numerator: Any, denominator: Any) -> float | None:
    """安全除法：任一侧缺数据或分母为 0 时返回 ``None``。"""
    a = _num(numerator)
    b = _num(denominator)
    if a is None or b is None or b == 0:
        return None
    return a / b


def _mul(left: Any, right: Any) -> float | None:
    """安全乘法：任一侧缺数据时返回 ``None``。"""
    a = _num(left)
    b = _num(right)
    if a is None or b is None:
        return None
    return a * b


@dataclass(frozen=True)
class DerivedQuantity:
    """一个派生量的完整定义。

    Attributes:
        name: 规则 YAML 里引用的英文字段名。
        label: 中文名，前端与报告展示用。
        unit: 单位；无量纲写 "—"。
        formula: 公式字符串，写进评估结果的 ``formula`` 字段，供报告溯源。
        deps: 计算所依赖的原始字段名；缺任一项即判为数据不足。
        compute: 实际计算函数，入参是完整命名空间，返回 ``float`` 或 ``None``。
        note: 给规则作者看的一句话说明。
    """

    name: str
    label: str
    unit: str
    formula: str
    deps: tuple[str, ...]
    compute: Callable[[Mapping[str, Any]], float | None] = field(compare=False)
    note: str = ""


@dataclass(frozen=True)
class DerivedValue:
    """派生量的一次计算结果。"""

    quantity: DerivedQuantity
    value: float | None
    #: 取值为空的依赖字段名；``value is None`` 时用它告诉用户"缺哪些字段"。
    missing_fields: tuple[str, ...] = ()

    @property
    def is_available(self) -> bool:
        return self.value is not None


#: 全部派生量。**新增派生量只改这里**，字段对照表与规则静态检查都从这里取名字。
#:
#: 顺序即计算顺序：靠后的派生量可以引用靠前的派生量（目前还没有这种情况，
#: 所有派生量都只依赖原始字段）。
DERIVED_QUANTITIES: tuple[DerivedQuantity, ...] = (
    DerivedQuantity(
        name="far",
        label="容积率",
        unit="—",
        formula="gfa / site_area",
        deps=("gfa", "site_area"),
        compute=lambda ns: _div(ns.get("gfa"), ns.get("site_area")),
        note="总建筑面积与用地面积之比；与项目层 far_max 比较即可判上限。",
    ),
    DerivedQuantity(
        name="density",
        label="建筑密度",
        unit="—",
        formula="footprint / site_area",
        deps=("footprint", "site_area"),
        compute=lambda ns: _div(ns.get("footprint"), ns.get("site_area")),
        note="基底面积与用地面积之比，0–1 小数；与项目层 density_max 比较。",
    ),
    DerivedQuantity(
        name="shape_coef",
        label="体形系数",
        unit="—",
        formula="envelope_area / volume",
        deps=("envelope_area", "volume"),
        compute=lambda ns: _div(ns.get("envelope_area"), ns.get("volume")),
        note="外表面积与体积之比，越小越利于节能。",
    ),
    DerivedQuantity(
        name="height",
        label="建筑总高",
        unit="m",
        formula="floors * floor_height",
        deps=("floors", "floor_height"),
        compute=lambda ns: _mul(ns.get("floors"), ns.get("floor_height")),
        note="层数乘层高；与项目层 height_max 比较即可判限高。",
    ),
    DerivedQuantity(
        name="units_per_building",
        label="单栋户数",
        unit="户/栋",
        formula="units / buildings",
        deps=("units", "buildings"),
        compute=lambda ns: _div(ns.get("units"), ns.get("buildings")),
        note="疏散与电梯服务的关键指标。",
    ),
    DerivedQuantity(
        name="units_per_floor",
        label="每层户数",
        unit="户/层",
        formula="units / (floors * buildings)",
        deps=("units", "floors", "buildings"),
        compute=lambda ns: _div(ns.get("units"), _mul(ns.get("floors"), ns.get("buildings"))),
        note="决定标准层交通核大小。",
    ),
    DerivedQuantity(
        name="floor_efficiency",
        label="楼层效率",
        unit="—",
        formula="footprint * floors / gfa",
        deps=("footprint", "floors", "gfa"),
        compute=lambda ns: _div(_mul(ns.get("footprint"), ns.get("floors")), ns.get("gfa")),
        note="基底与层数对总建筑面积的利用率，越接近 1 越理想。",
    ),
)

#: 按名字索引，方便按字段名取中文名与公式。
DERIVED_BY_NAME: dict[str, DerivedQuantity] = {q.name: q for q in DERIVED_QUANTITIES}


def derived_names() -> frozenset[str]:
    """全部派生量的字段名集合，供表达式静态检查使用。"""
    return frozenset(DERIVED_BY_NAME)


def compute_derived(namespace: Mapping[str, Any]) -> dict[str, DerivedValue]:
    """按声明顺序算出全部派生量。

    Args:
        namespace: 已经合并好的原始字段命名空间（项目层 + 方案层）。

    Returns:
        字段名 → :class:`DerivedValue`。取不到值的派生量也在返回值里，
        ``value`` 为 ``None`` 且 ``missing_fields`` 说明缺了什么，
        这样"缺数据"能一路传到最终结果里给用户看。

    实现说明：为了让后声明的派生量能引用先声明的，每算完一个就写回一份工作命名空间。
    """
    working: dict[str, Any] = dict(namespace)
    results: dict[str, DerivedValue] = {}

    for quantity in DERIVED_QUANTITIES:
        missing = tuple(
            dep for dep in quantity.deps if _num(working.get(dep)) is None
        )
        value = quantity.compute(working) if not missing else None
        # 依赖都齐但结果仍为 None 的唯一原因是分母为 0，此时把分母记为"缺数据"，
        # 因为对规则作者来说"体积填了 0"和"体积没填"同样无法判定。
        if value is None and not missing:
            missing = tuple(dep for dep in quantity.deps if _num(working.get(dep)) == 0)
        results[quantity.name] = DerivedValue(
            quantity=quantity, value=value, missing_fields=missing
        )
        working[quantity.name] = value

    return results
