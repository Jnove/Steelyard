"""ProjectParams / SchemeParams 的字段校验测试。

覆盖任务 T2 验收标准：
- 合法方案
- 缺项方案
- 比例填成百分数
- 负面积
"""

from __future__ import annotations

import pytest
from app.models import (
    CLIMATE_ZONES,
    RISK_FEATURE_OPTIONS,
    STRUCTURE_TYPES,
    ProjectParams,
    SchemeParams,
)
from pydantic import ValidationError


class TestSchemeParams:
    """SchemeParams 字段校验。"""

    def test_valid_full_scheme(self) -> None:
        """完整合法方案。"""
        scheme = SchemeParams(
            structure_type="框架-剪力墙",
            units=120,
            unit_mix={"两室": 60, "三室": 60},
            floor_height=3.0,
            inner_area_ratio=0.78,
            south_room_ratio=0.65,
            window_floor_ratio=0.25,
            window_wall_ratio={"南": 0.40, "北": 0.25},
            elevators_per_unit=2,
            gfa=18000,
            footprint=2400,
            buildings=4,
            floors=18,
            envelope_area=9000,
            volume=54000,
            std_floor_repeat=0.82,
            component_types=12,
            risk_features=["大悬挑", "深基坑"],
            prefab_ratio_est=0.35,
        )
        assert scheme.gfa == 18000
        assert scheme.risk_features == ["大悬挑", "深基坑"]

    def test_partial_scheme_keeps_other_fields_none(self) -> None:
        """真实数据常有缺项；缺项必须允许。"""
        scheme = SchemeParams(gfa=10000)
        dumped = scheme.model_dump()
        assert dumped["gfa"] == 10000
        assert dumped["floors"] is None
        assert dumped["units"] is None
        assert dumped["risk_features"] == []  # 默认空列表

    def test_reject_percentage_for_ratio(self) -> None:
        """比例字段填 1-100 的百分数应报错并提示。"""
        with pytest.raises(ValidationError) as ei:
            SchemeParams(inner_area_ratio=82)
        assert "请填小数" in str(ei.value)

    def test_accept_ratio_boundary_zero_and_one(self) -> None:
        """0 与 1（= 100%）是允许的，不应误报。"""
        SchemeParams(inner_area_ratio=0)
        SchemeParams(inner_area_ratio=1.0)

    def test_reject_percentage_in_window_wall_ratio(self) -> None:
        """嵌套字典里的窗墙比也要做同样的百分数检查。"""
        with pytest.raises(ValidationError) as ei:
            SchemeParams(window_wall_ratio={"南": 40})
        assert "窗墙比" in str(ei.value)

    def test_reject_negative_area(self) -> None:
        """面积必须 > 0。"""
        with pytest.raises(ValidationError):
            SchemeParams(gfa=-100)
        with pytest.raises(ValidationError):
            SchemeParams(footprint=-1.0)

    def test_reject_zero_area(self) -> None:
        """面积 = 0 也不允许。"""
        with pytest.raises(ValidationError):
            SchemeParams(gfa=0)

    def test_structure_type_enum(self) -> None:
        """structure_type 必须是枚举里的值。"""
        for st in STRUCTURE_TYPES:
            assert SchemeParams(structure_type=st).structure_type == st
        with pytest.raises(ValidationError):
            SchemeParams(structure_type="木结构")

    def test_unit_mix_must_sum_to_units(self) -> None:
        """户型配比之和必须等于总户数。"""
        with pytest.raises(ValidationError) as ei:
            SchemeParams(units=100, unit_mix={"A": 30, "B": 40})
        assert "户型配比" in str(ei.value)

    def test_unit_mix_can_be_omitted_with_units(self) -> None:
        """只给 units 没给 unit_mix 应允许（先填粗后填细）。"""
        assert SchemeParams(units=100).unit_mix is None

    def test_risk_features_default_empty(self) -> None:
        """未提供 risk_features 时默认为空列表（不是 None）。"""
        assert SchemeParams().risk_features == []

    def test_risk_features_accept_custom(self) -> None:
        """risk_features 允许用户填预设以外的字符串。"""
        custom = ["本项目特殊风险"]
        assert SchemeParams(risk_features=custom).risk_features == custom

    def test_preset_options_exposed(self) -> None:
        """RISK_FEATURE_OPTIONS 暴露给前端做下拉。"""
        assert "大悬挑" in RISK_FEATURE_OPTIONS
        assert "深基坑" in RISK_FEATURE_OPTIONS


class TestProjectParams:
    """ProjectParams 字段校验。"""

    def test_valid_project(self) -> None:
        params = ProjectParams(
            site_area=20000,
            far_max=2.5,
            density_max=0.30,
            height_max=54,
            climate_zone="夏热冬冷",
        )
        assert params.climate_zone == "夏热冬冷"

    def test_climate_zone_enum(self) -> None:
        for zone in CLIMATE_ZONES:
            assert ProjectParams(climate_zone=zone).climate_zone == zone
        with pytest.raises(ValidationError):
            ProjectParams(climate_zone="撒哈拉")

    def test_density_max_must_be_0_1(self) -> None:
        """建筑密度是小数，填 30 应报错。"""
        with pytest.raises(ValidationError) as ei:
            ProjectParams(density_max=30)
        assert "请填小数" in str(ei.value)

    def test_far_max_is_not_capped_at_1(self) -> None:
        """容积率上限不是 0-1 比值，可以 > 1（中国典型 0.5-4.0）。"""
        assert ProjectParams(far_max=3.5).far_max == 3.5
        assert ProjectParams(far_max=0.5).far_max == 0.5

    def test_partial_project(self) -> None:
        """项目层也可以缺项。"""
        assert ProjectParams().site_area is None
        assert ProjectParams(site_area=1000).density_max is None