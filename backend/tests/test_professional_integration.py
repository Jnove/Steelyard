"""专业 YAML 的运行边界；CI 通过不能替代规则实际触发与数据往返验证。"""

from pathlib import Path

import pytest
import yaml
from app.engine.rules import SchemeInput, default_rules_dir, evaluate, load_rules_from_dir
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
