"""专业 YAML 的运行边界；CI 通过不能替代规则实际触发与数据往返验证。"""

from pathlib import Path

import pytest
import yaml
from app.engine.rules import RuleSet, SchemeInput, default_rules_dir, evaluate, load_rules_from_dir
from app.engine.weights import check_weights_file, default_weights_path, load_role_templates
from app.excel import parse_workbook, write_export
from app.models.params import ProjectParams, SchemeParams
from app.schemas.meta import enriched_schema
from pydantic import ValidationError


def _irregularity_result(items: list[str] | None, rule_id: str = "S-10"):
    result = evaluate(
        ProjectParams(),
        [
            SchemeInput(
                scheme_id="1", name="边界测试", params=SchemeParams(irregularity_items=items)
            )
        ],
        load_rules_from_dir(default_rules_dir()),
    )[0]
    return next(item for item in result.compliance if item.rule_id == rule_id)


def test_same_irregularity_category_counts_once() -> None:
    # 4a / 4b + 一项 = 两类；再加第三类才触发专项审查提示。
    items = ["刚度突变", "尺寸突变", "扭转不规则"]
    assert _irregularity_result(items).status == "passed"
    result = _irregularity_result([*items, "楼板不连续"])
    assert result.status == "failed"
    assert result.severity == "warning"


@pytest.mark.parametrize("rule_id", ["S-10", "S-11"])
def test_undeclared_irregularity_is_unknown_not_zero(rule_id: str) -> None:
    assert SchemeParams().irregularity_items is None
    result = _irregularity_result(None, rule_id)
    assert result.status == "insufficient_data"
    assert result.missing_fields == ["irregularity_items"]
    assert _irregularity_result([], rule_id).status == "passed"


@pytest.mark.parametrize(
    "floor,height,lifts,rule_id,status",
    [
        (10, 34, 1, "C-05", "failed"),
        (10, 33, 1, "C-05", "not_applicable"),
        (12, 30, 1, "C-05", "failed"),
        (4, 9, 0, "C-08", "failed"),
        (3, 10, 0, "C-08", "failed"),
        (3, 9, 0, "C-08", "not_applicable"),
    ],
)
def test_lift_rules_use_actual_entry_level_and_height(
    floor: int, height: float, lifts: int, rule_id: str, status: str
) -> None:
    result = evaluate(
        ProjectParams(),
        [
            SchemeInput(
                scheme_id="1",
                name="边界测试",
                params=SchemeParams(
                    floors=18,
                    highest_occupied_floor=floor,
                    highest_occupied_floor_height=height,
                    elevators_per_unit=lifts,
                ),
            )
        ],
        load_rules_from_dir(default_rules_dir()),
    )[0]
    assert next(item for item in result.compliance if item.rule_id == rule_id).status == status


def test_lift_rule_does_not_guess_entry_height_from_total_height() -> None:
    result = evaluate(
        ProjectParams(),
        [
            SchemeInput(
                scheme_id="1",
                name="未核对",
                params=SchemeParams(
                    floors=18,
                    floor_height=3,
                    elevators_per_unit=2,
                ),
            )
        ],
        load_rules_from_dir(default_rules_dir()),
    )[0]
    assert (
        next(item for item in result.compliance if item.rule_id == "C-05").status
        == "insufficient_data"
    )


def test_unknown_irregularity_cannot_silently_pass() -> None:
    with pytest.raises(ValidationError, match="未支持的选项"):
        SchemeParams(irregularity_items=["扭转不规侧"])
    field = next(
        item
        for item in enriched_schema(SchemeParams)["fields"]
        if item["name"] == "irregularity_items"
    )
    assert field["type"] == "array<string>"
    assert field["empty_means_unknown"]
    assert field["allow_custom_options"] is False


def test_irregularity_excel_preserves_unknown_empty_and_declared(tmp_path: Path) -> None:
    source = [
        {"name": str(i), "params": {"irregularity_items": value}}
        for i, value in enumerate([None, [], ["扭转不规则"]])
    ]
    path = write_export(tmp_path / "roundtrip.xlsx", {}, source)
    parsed = parse_workbook(path)
    assert not parsed.errors
    assert [
        SchemeParams.model_validate(item["params"]).irregularity_items for item in parsed.schemes
    ] == [
        None,
        [],
        ["扭转不规则"],
    ]


def test_boolean_field_round_trips_through_excel(tmp_path: Path) -> None:
    """布尔字段（是否设地下室）必须能在 Excel 里往返：写出「是 / 否」，读回仍是布尔。

    这个字段类型此前**既没有写入分支也没有解析分支**：导出后重新解析会直接报
    「字段类型 boolean 暂未支持」，而这条链只在"导出 → 再解析"时才会暴露
    （CI 的前端数据层测试正是靠演示工作簿的解析快照发现的），所以在这里钉住，
    并同时覆盖"未填写保持 None"。
    """
    source = [
        {"name": "有地下室", "params": {"has_basement": True}},
        {"name": "无地下室", "params": {"has_basement": False}},
        {"name": "未填写", "params": {}},
    ]
    path = write_export(tmp_path / "bool.xlsx", {}, source)
    parsed = parse_workbook(path)
    assert not parsed.errors
    assert [
        SchemeParams.model_validate(item["params"]).has_basement for item in parsed.schemes
    ] == [True, False, None]


def _round2_evaluation(rule_id: str, **params):
    # 独立加载待测规则，避免无关规则的缺值或失败掩盖阻断语义。
    rules = RuleSet(
        rules=tuple(
            rule for rule in load_rules_from_dir(default_rules_dir()).rules if rule.id == rule_id
        ),
        origins={},
    )
    result = evaluate(
        ProjectParams(),
        [SchemeInput(scheme_id="1", name="二轮边界", params=SchemeParams(**params))],
        rules,
    )[0]
    return result, result.compliance[0]


@pytest.mark.parametrize(
    "upper,foundation,status",
    [(40, 25, "failed"), (25, 30, "passed"), (40, None, "insufficient_data")],
)
def test_foundation_concrete_grade_is_independent_of_superstructure(
    upper: float, foundation: float | None, status: str
) -> None:
    result, item = _round2_evaluation(
        "S-17",
        foundation_type="筏形基础",
        concrete_grade=upper,
        foundation_concrete_grade=foundation,
    )
    assert item.status == status
    assert result.has_blocking_failure == (status == "failed")
    if foundation is None:
        assert item.missing_fields == ["foundation_concrete_grade"]


@pytest.mark.parametrize("foundation_type", ["独立基础", "条形基础", "桩基础"])
def test_foundation_concrete_rule_does_not_apply_to_other_foundations(
    foundation_type: str,
) -> None:
    _, item = _round2_evaluation("S-17", foundation_type=foundation_type)
    assert item.status == "not_applicable"


@pytest.mark.parametrize(
    "retaining_type,two_in_one,grade,status,missing",
    [
        ("地下连续墙", True, 25, "failed", []),
        ("地下连续墙", True, 30, "passed", []),
        ("地下连续墙", False, 25, "not_applicable", []),
        ("地下连续墙", None, 30, "insufficient_data", ["retaining_wall_two_in_one"]),
        ("地下连续墙", True, None, "insufficient_data", ["retaining_concrete_grade"]),
        ("排桩", False, 25, "not_applicable", []),
        ("土钉墙", False, None, "not_applicable", []),
        ("排桩", None, 25, "insufficient_data", ["retaining_wall_two_in_one"]),
    ],
)
def test_two_in_one_wall_rule_requires_declared_applicability(
    retaining_type: str,
    two_in_one: bool | None,
    grade: float | None,
    status: str,
    missing: list[str],
) -> None:
    result, item = _round2_evaluation(
        "K-07",
        retaining_type=retaining_type,
        retaining_wall_two_in_one=two_in_one,
        retaining_concrete_grade=grade,
    )
    assert item.status == status
    assert item.missing_fields == missing
    assert result.has_blocking_failure == (status == "failed")


def test_steel_foundation_depth_recommendation_warns_without_blocking() -> None:
    result, item = _round2_evaluation(
        "S-26",
        structure_type="钢结构",
        floors=20,
        floor_height=3,
        foundation_type="筏形基础",
        foundation_depth=1,
    )
    assert item.status == "failed"
    assert item.severity == "warning"
    assert not result.has_blocking_failure


def test_steel_foundation_depth_missing_is_unknown() -> None:
    _, item = _round2_evaluation(
        "S-26", structure_type="钢结构", floors=20, floor_height=3, foundation_type="筏形基础"
    )
    assert item.status == "insufficient_data"
    assert item.missing_fields == ["foundation_depth"]


def test_foundation_and_wall_fields_round_trip_without_defaults(tmp_path: Path) -> None:
    values = [(30, True), (25, False), (None, None)]
    path = write_export(
        tmp_path / "foundation-wall.xlsx",
        {},
        [
            {
                "name": str(index),
                "params": {
                    "foundation_concrete_grade": grade,
                    "retaining_wall_two_in_one": two_in_one,
                },
            }
            for index, (grade, two_in_one) in enumerate(values)
        ],
    )
    parsed = parse_workbook(path)
    assert not parsed.errors
    assert [
        (params.foundation_concrete_grade, params.retaining_wall_two_in_one)
        for params in [SchemeParams.model_validate(item["params"]) for item in parsed.schemes]
    ] == values


@pytest.mark.parametrize(
    "retaining,brace,status",
    [(40, 20, "failed"), (20, 25, "passed"), (40, None, "insufficient_data")],
)
def test_brace_concrete_does_not_reuse_wall_grade(
    retaining: float, brace: float | None, status: str
) -> None:
    _, item = _round2_evaluation(
        "K-09",
        brace_type="混凝土内支撑",
        retaining_concrete_grade=retaining,
        brace_concrete_grade=brace,
    )
    assert item.status == status
    if brace is None:
        assert item.missing_fields == ["brace_concrete_grade"]


@pytest.mark.parametrize(
    "structure,local_grade,status",
    [
        ("框架", 25, "failed"),
        ("剪力墙", 30, "passed"),
        ("框架", None, "insufficient_data"),
        ("钢结构", None, "not_applicable"),
        ("MiC", None, "not_applicable"),
    ],
)
def test_staggered_concrete_rule_checks_only_declared_concrete_members(
    structure: str, local_grade: float | None, status: str
) -> None:
    _, item = _round2_evaluation(
        "S-27",
        structure_type=structure,
        has_staggered_floor=True,
        concrete_grade=40,
        staggered_concrete_grade=local_grade,
    )
    assert item.status == status
    if status == "insufficient_data":
        assert item.missing_fields == ["staggered_concrete_grade"]


@pytest.mark.parametrize(
    "has_wall,thickness,status,missing",
    [
        (True, 200, "failed", []),
        (True, 250, "passed", []),
        (False, None, "not_applicable", []),
        (None, None, "insufficient_data", ["has_out_of_plane_staggered_wall"]),
        (True, None, "insufficient_data", ["staggered_wall_thickness"]),
    ],
)
def test_staggered_wall_does_not_reuse_general_wall_thickness(
    has_wall: bool | None, thickness: float | None, status: str, missing: list[str]
) -> None:
    _, item = _round2_evaluation(
        "S-28",
        structure_type="剪力墙",
        has_staggered_floor=True,
        has_out_of_plane_staggered_wall=has_wall,
        shear_wall_thickness=300,
        staggered_wall_thickness=thickness,
    )
    assert item.status == status
    assert item.missing_fields == missing


@pytest.mark.parametrize(
    "classification,status",
    [("高层", "failed"), ("多层", "passed"), (None, "insufficient_data")],
)
def test_wall_thickness_uses_structural_classification_not_residential_height(
    classification: str | None, status: str
) -> None:
    _, item = _round2_evaluation(
        "S-22",
        structure_type="剪力墙",
        structural_height_classification=classification,
        floors=20,
        floor_height=3,
        shear_wall_thickness=150,
    )
    assert item.status == status
    if classification is None:
        assert item.missing_fields == ["structural_height_classification"]


@pytest.mark.parametrize(
    "system,classification,status",
    [
        ("框架", "高层", "failed"),
        ("框架", "多层", "not_applicable"),
        ("框架-中心支撑", "高层", "not_applicable"),
        ("筒体和巨型框架", "高层", "not_applicable"),
        ("框架", None, "insufficient_data"),
    ],
)
def test_single_span_limit_applies_only_to_declared_highrise_steel_frame(
    system: str, classification: str | None, status: str
) -> None:
    _, item = _round2_evaluation(
        "S-29",
        structure_type="钢结构",
        steel_system=system,
        structural_height_classification=classification,
        floors=20,
        floor_height=3,
        is_single_span_frame=True,
    )
    assert item.status == status
    if classification is None:
        assert item.missing_fields == ["structural_height_classification"]


def test_named_weights_keep_all_five_roles_and_dimension_order() -> None:
    roles = load_role_templates()
    expected = {
        "government": [0.15, 0.25, 0.10, 0.15],
        "developer": [0.20, 0.20, 0.20, 0.15],
        "contractor": [0.10, 0.25, 0.25, 0.10],
        "resident": [0.45, 0.15, 0.05, 0.15],
        "design": [0.20, 0.25, 0.10, 0.15],
    }
    assert set(roles) == set(expected)
    for key, weights in expected.items():
        assert roles[key].weights == pytest.approx([value / sum(weights) for value in weights])
        assert roles[key].ahp is None
        assert "compliance 原始权重" in roles[key].source


def test_named_weights_ignore_yaml_key_order(tmp_path: Path) -> None:
    raw = yaml.safe_load(default_weights_path().read_text(encoding="utf-8"))
    for config in raw["roles"].values():
        config["weights"] = dict(reversed(list(config["weights"].items())))
    path = tmp_path / "weights.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    roles = load_role_templates(path)
    assert roles["design"].weights == pytest.approx([2 / 7, 2.5 / 7, 1 / 7, 1.5 / 7])


@pytest.mark.parametrize(
    "change,code",
    [
        ("negative", "WEIGHTS_NOT_POSITIVE"),
        ("sum", "WEIGHTS_SUM"),
        ("missing_dimension", "WEIGHTS_DIMENSIONS"),
        ("alias_collision", "WEIGHTS_DUPLICATE_ROLE"),
        ("unknown_section", "WEIGHTS_UNKNOWN_SECTION"),
    ],
)
def test_named_weights_reject_invalid_config(tmp_path: Path, change: str, code: str) -> None:
    raw = yaml.safe_load(default_weights_path().read_text(encoding="utf-8"))
    if change == "negative":
        raw["roles"]["government"]["weights"]["compliance"] = -0.35
    elif change == "sum":
        raw["roles"]["government"]["weights"]["quality"] = 0.9
    elif change == "missing_dimension":
        del raw["roles"]["government"]["weights"]["green"]
    elif change == "alias_collision":
        raw["roles"]["resident"] = raw["roles"]["residents"]
    else:
        raw["typo"] = {}
    path = tmp_path / "weights.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    assert any(issue.code == code for issue in check_weights_file(path)[1])


def test_legacy_four_role_weights_still_load(tmp_path: Path) -> None:
    raw = {
        key: {"name": key, "weights": [1, 1, 1, 1]}
        for key in ["government", "developer", "contractor", "resident"]
    }
    path = tmp_path / "weights.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    assert set(load_role_templates(path)) == set(raw)
