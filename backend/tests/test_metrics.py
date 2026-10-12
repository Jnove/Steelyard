"""派生量的测试。

重点有三条：
1. 每个派生量的 ``compute`` 与它自己声明的 ``formula`` 语义一致
   （防止改了公式忘了改注释，或反过来）；
2. 缺数据、分母为 0 时返回 ``None`` 而不是抛异常；
3. 派生量的名字、依赖字段都真实存在于参数模型里。
"""

from __future__ import annotations

import pytest
from app.engine.metrics import (
    DERIVED_BY_NAME,
    DERIVED_QUANTITIES,
    compute_derived,
    derived_names,
)
from app.models.params import ProjectParams, SchemeParams
from simpleeval import SimpleEval

#: 一组完整、互不为零的输入，用来交叉验证 compute 与 formula。
FULL_INPUT: dict[str, float] = {
    "site_area": 20_000.0,
    "gfa": 48_000.0,
    "footprint": 5_200.0,
    "buildings": 4.0,
    "floors": 18.0,
    "floor_height": 2.9,
    "envelope_area": 26_000.0,
    "volume": 140_000.0,
    "units": 288.0,
    "min_plan_width": 15.0,
}


def test_derived_names_are_unique() -> None:
    names = [q.name for q in DERIVED_QUANTITIES]
    assert len(names) == len(set(names)), f"派生量名字有重复：{names}"


def test_t3_required_quantities_exist() -> None:
    """T3 规格明确要求的四个派生量必须在册。"""
    for name in ("far", "density", "shape_coef", "height"):
        assert name in DERIVED_BY_NAME, f"缺少派生量 {name}"


def test_derived_deps_are_real_fields() -> None:
    """派生量依赖的字段必须真实存在于项目层或方案层模型里。

    这条能挡住"模型改了字段名但派生量没跟着改"——否则规则加载时才会炸。
    """
    real = set(ProjectParams.model_fields) | set(SchemeParams.model_fields)
    for quantity in DERIVED_QUANTITIES:
        unknown = [dep for dep in quantity.deps if dep not in real]
        assert not unknown, f"派生量 {quantity.name} 依赖了不存在的字段 {unknown}"


@pytest.mark.parametrize("quantity", DERIVED_QUANTITIES, ids=[q.name for q in DERIVED_QUANTITIES])
def test_compute_matches_declared_formula(quantity: object) -> None:
    """``compute`` 的结果必须等于按 ``formula`` 字符串算出来的结果。

    ``formula`` 会原样写进评估结果供报告溯源，所以它不能只是一句注释——
    这条测试把它变成了会失败的断言。
    """
    evaluator = SimpleEval(names=dict(FULL_INPUT), functions={})
    expected = evaluator.eval(quantity.formula)  # type: ignore[attr-defined]
    actual = quantity.compute(FULL_INPUT)  # type: ignore[attr-defined]
    assert actual == pytest.approx(expected), (
        f"{quantity.name} 的 compute 与 formula "  # type: ignore[attr-defined]
        f"`{quantity.formula}` 不一致"  # type: ignore[attr-defined]
    )


def test_compute_derived_values() -> None:
    """抽查几个具体数值，确认量纲和方向没搞反。"""
    result = compute_derived(FULL_INPUT)
    assert result["far"].value == pytest.approx(48_000 / 20_000)
    assert result["density"].value == pytest.approx(5_200 / 20_000)
    assert result["shape_coef"].value == pytest.approx(26_000 / 140_000)
    assert result["height"].value == pytest.approx(18 * 2.9)
    assert result["units_per_building"].value == pytest.approx(288 / 4)


def test_missing_dependency_yields_none_and_names_it() -> None:
    """缺依赖字段时返回 None，并说清缺的是哪个原始字段。"""
    partial = dict(FULL_INPUT)
    partial["volume"] = None  # type: ignore[assignment]
    result = compute_derived(partial)
    shape = result["shape_coef"]
    assert shape.value is None
    assert not shape.is_available
    assert shape.missing_fields == ("volume",)


def test_zero_denominator_yields_none() -> None:
    """分母为 0 不抛 ZeroDivisionError，而是当"判不了"处理。"""
    partial = dict(FULL_INPUT)
    partial["site_area"] = 0.0
    result = compute_derived(partial)
    assert result["far"].value is None
    # 对规则作者来说，"用地面积填了 0"和"没填"同样需要回去补数据。
    assert "site_area" in result["far"].missing_fields


def test_all_missing_is_safe() -> None:
    """全空输入不应抛异常，每个派生量都返回 None。"""
    result = compute_derived({})
    assert set(result) == set(derived_names())
    assert all(dv.value is None for dv in result.values())


def test_bool_is_not_treated_as_number() -> None:
    """布尔值不当数字用：True 在 Python 里等于 1，但拿它算面积比显然是笔误。"""
    partial = dict(FULL_INPUT)
    partial["volume"] = True  # type: ignore[assignment]
    assert compute_derived(partial)["shape_coef"].value is None


def test_every_quantity_has_chinese_label_and_formula() -> None:
    """每个派生量都要有中文名和公式字符串——这是报告可溯源的前提。"""
    for quantity in DERIVED_QUANTITIES:
        assert quantity.label.strip(), f"{quantity.name} 缺中文名"
        assert quantity.formula.strip(), f"{quantity.name} 缺公式字符串"
        assert quantity.unit.strip(), f"{quantity.name} 缺单位"
