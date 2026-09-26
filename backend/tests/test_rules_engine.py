"""规则引擎的测试：规则定义、表达式、加载、判定与聚合。

组织顺序与 ``app/engine/rules.py`` 一致：RuleDef → 表达式 → 加载 → evaluate → 聚合。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.engine.rules import (
    RuleDef,
    RuleLoadError,
    SchemeInput,
    analyze_expression,
    build_namespace,
    evaluate,
    known_field_names,
    load_rules_from_dir,
    rewrite_contains,
)
from app.models.params import ProjectParams, SchemeParams
from pydantic import ValidationError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD_RULES = FIXTURES / "rules_good"
BAD_RULES = FIXTURES / "rules_bad"


# —— 测试数据 —— #


def _project(**overrides: object) -> ProjectParams:
    base: dict[str, object] = {
        "site_area": 20_000.0,
        "far_max": 2.5,
        "density_max": 0.30,
        "height_max": 80.0,
        "climate_zone": "夏热冬冷",
    }
    base.update(overrides)
    return ProjectParams.model_validate(base)


def _scheme(**overrides: object) -> SchemeParams:
    """一个各字段齐全的方案，测试里按需覆盖单个字段。"""
    base: dict[str, object] = {
        "structure_type": "剪力墙",
        "units": 288,
        "floor_height": 3.1,
        "inner_area_ratio": 0.80,
        "south_room_ratio": 0.62,
        "gfa": 48_000.0,
        "footprint": 5_200.0,
        "buildings": 4,
        "floors": 18,
        "envelope_area": 26_000.0,
        "volume": 140_000.0,
        "std_floor_repeat": 0.80,
        "component_types": 24,
        "prefab_ratio_est": 0.45,
        "risk_features": ["深基坑"],
    }
    base.update(overrides)
    return SchemeParams.model_validate(base)


@pytest.fixture
def ruleset() -> object:
    return load_rules_from_dir(GOOD_RULES)


def _evaluate_one(scheme: SchemeParams, ruleset: object, project: ProjectParams | None = None):
    results = evaluate(
        project or _project(), [SchemeInput("1", "测试方案", scheme)], ruleset  # type: ignore[arg-type]
    )
    return results[0]


def _compliance(result: object, rule_id: str):
    return next(c for c in result.compliance if c.rule_id == rule_id)  # type: ignore[attr-defined]


# —— RuleDef：字段与取值校验 —— #


def _hard(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "C-01",
        "name": "层高下限",
        "type": "hard",
        "check": "floor_height >= 3.0",
        "source": "测试",
    }
    base.update(overrides)
    return base


def _metric(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "K-01",
        "name": "标准层重复率",
        "type": "metric",
        "dimension": "construction",
        "value": "std_floor_repeat",
        "scoring": {"kind": "piecewise", "points": [[0.5, 0], [0.95, 100]]},
        "source": "测试",
    }
    base.update(overrides)
    return base


def test_minimal_hard_rule_is_valid() -> None:
    rule = RuleDef.model_validate(_hard())
    assert rule.type == "hard"
    assert rule.severity == "error", "severity 默认应当是 error"


def test_minimal_metric_rule_defaults_weight_to_one() -> None:
    rule = RuleDef.model_validate(_metric())
    assert rule.weight_in_dimension == 1.0, "weight_in_dimension 默认应当是 1"


@pytest.mark.parametrize("rule_id", ["C-01", "Q-99", "S-00", "K-12", "G-07"])
def test_accepts_valid_rule_ids(rule_id: str) -> None:
    assert RuleDef.model_validate(_hard(id=rule_id)).id == rule_id


@pytest.mark.parametrize(
    "rule_id",
    ["C-1", "C-001", "C-SHAPE", "X-01", "c-01", "C01", "C-01 ", "", "C-1a"],
)
def test_rejects_invalid_rule_ids(rule_id: str) -> None:
    with pytest.raises(ValidationError):
        RuleDef.model_validate(_hard(id=rule_id))


def test_rejects_unknown_field() -> None:
    """未知字段必须报错，不能静默忽略——静默忽略会让规则看起来生效其实没生效。"""
    with pytest.raises(ValidationError, match="serverity"):
        RuleDef.model_validate(_hard(serverity="warning"))


def test_hard_rule_requires_check() -> None:
    payload = _hard()
    del payload["check"]
    with pytest.raises(ValidationError, match="check"):
        RuleDef.model_validate(payload)


def test_metric_rule_requires_dimension_value_scoring() -> None:
    payload = _metric()
    del payload["dimension"]
    del payload["scoring"]
    with pytest.raises(ValidationError, match="dimension"):
        RuleDef.model_validate(payload)


def test_hard_rule_rejects_metric_only_fields() -> None:
    with pytest.raises(ValidationError, match="metric"):
        RuleDef.model_validate(_hard(dimension="quality"))


def test_metric_rule_rejects_hard_only_fields() -> None:
    with pytest.raises(ValidationError, match="hard"):
        RuleDef.model_validate(_metric(check="floor_height >= 3.0"))


def test_rejects_bad_dimension() -> None:
    with pytest.raises(ValidationError):
        RuleDef.model_validate(_metric(dimension="cost"))


def test_rejects_non_positive_weight() -> None:
    with pytest.raises(ValidationError):
        RuleDef.model_validate(_metric(weight_in_dimension=0))


# —— ScoringDef：points 校验 —— #


def test_rejects_points_not_strictly_increasing() -> None:
    with pytest.raises(ValidationError, match="严格递增"):
        RuleDef.model_validate(
            _metric(scoring={"kind": "piecewise", "points": [[0.95, 100], [0.5, 0]]})
        )


def test_rejects_duplicate_x_in_points() -> None:
    with pytest.raises(ValidationError, match="严格递增"):
        RuleDef.model_validate(
            _metric(scoring={"kind": "piecewise", "points": [[0.5, 0], [0.5, 100]]})
        )


@pytest.mark.parametrize("bad_score", [-1, 101, 120])
def test_rejects_score_out_of_range(bad_score: float) -> None:
    """分数越界要报错，且错误路径要带上「第几个控制点」，check_rules 才能指到具体行。"""
    with pytest.raises(ValidationError) as excinfo:
        RuleDef.model_validate(
            _metric(scoring={"kind": "piecewise", "points": [[0.5, 0], [0.95, bad_score]]})
        )
    assert excinfo.value.errors()[0]["loc"] == ("scoring", "points", 1, 1)


def test_rejects_single_point() -> None:
    with pytest.raises(ValidationError, match="控制点"):
        RuleDef.model_validate(_metric(scoring={"kind": "piecewise", "points": [[0.5, 0]]}))


def test_accepts_optimal_in_middle_points() -> None:
    """先升后降必须被接受——这是"适中最好"型指标的唯一写法。"""
    rule = RuleDef.model_validate(
        _metric(scoring={"kind": "piecewise", "points": [[0.2, 0], [0.55, 100], [0.9, 0]]})
    )
    assert rule.scoring is not None
    assert [y for _, y in rule.scoring.points] == [0.0, 100.0, 0.0]


def test_rejects_unknown_scoring_kind() -> None:
    with pytest.raises(ValidationError):
        RuleDef.model_validate(_metric(scoring={"kind": "linear", "points": [[0, 0], [1, 100]]}))


# —— 表达式：contains 语法糖 —— #


@pytest.mark.parametrize(
    "source, expected",
    [
        ("risk_features contains '深基坑'", "('深基坑') in (risk_features)"),
        (
            "floors > 3 and risk_features contains '高支模'",
            "floors > 3 and ('高支模') in (risk_features)",
        ),
        (
            "risk_features contains '深基坑' or floors > 30",
            "('深基坑') in (risk_features) or floors > 30",
        ),
    ],
)
def test_rewrite_contains(source: str, expected: str) -> None:
    assert rewrite_contains(source) == expected


def test_rewrite_contains_leaves_other_expressions_alone() -> None:
    assert rewrite_contains("floor_height >= 3.0") == "floor_height >= 3.0"


def test_contains_inside_string_is_not_rewritten() -> None:
    """字符串里的 contains 是正文，不是运算符。"""
    expression = "structure_type == 'contains'"
    assert rewrite_contains(expression) == expression


# —— 表达式：静态检查 —— #


def test_known_names_include_project_scheme_and_derived() -> None:
    known = known_field_names()
    assert "site_area" in known, "项目层字段"
    assert "floor_height" in known, "方案层字段"
    assert "shape_coef" in known, "派生量"


def test_accepts_valid_expression() -> None:
    assert analyze_expression("floor_height >= 3.0", "check").ok


def test_accepts_allowed_functions() -> None:
    for expression in ("len(risk_features)", "min(floors, 10)", "round(far, 2)", "abs(far - 2)"):
        assert analyze_expression(expression, "value").ok, expression


def test_reports_syntax_error() -> None:
    analyzed = analyze_expression("(floor_height => 3.0", "check")
    assert not analyzed.ok
    assert "不合语法" in analyzed.problems[0].message


def test_reports_unknown_name_with_suggestion() -> None:
    """拼错字段名要给出最接近的候选——这是给非程序员的关键帮助。"""
    analyzed = analyze_expression("floor_hieght >= 3.0", "check")
    assert not analyzed.ok
    problem = analyzed.problems[0]
    assert "floor_hieght" in problem.message
    assert "floor_height" in problem.fix


def test_reports_disallowed_function() -> None:
    analyzed = analyze_expression("sum(risk_features)", "value")
    assert not analyzed.ok
    assert "sum" in analyzed.problems[0].message


@pytest.mark.parametrize(
    "expression",
    [
        "floor_height.real >= 3.0",  # 属性访问
        "window_wall_ratio['南'] <= 0.4",  # 下标取值
        "[f for f in risk_features]",  # 推导式
    ],
)
def test_rejects_disallowed_syntax(expression: str) -> None:
    assert not analyze_expression(expression, "value").ok


def test_collects_referenced_names() -> None:
    analyzed = analyze_expression("far <= far_max and floors > 3", "check")
    assert analyzed.names == {"far", "far_max", "floors"}
    assert "min" not in analyzed.names, "函数名不应被当成字段名"


# —— 加载 —— #


def test_loads_good_fixture(ruleset: object) -> None:
    assert len(ruleset.rules) == 8  # type: ignore[attr-defined]
    assert len(ruleset.hard_rules) == 4  # type: ignore[attr-defined]
    assert len(ruleset.metric_rules) == 4  # type: ignore[attr-defined]


def test_loads_repo_seed_rules() -> None:
    """仓库里 rules/ 下的种子规则必须能被引擎加载。"""
    from app.engine.rules import default_rules_dir

    loaded = load_rules_from_dir(default_rules_dir())
    assert loaded.rules, "rules/ 下应当有种子规则"
    # 种子规则的 source 全是 TODO，加载允许通过但必须被标出来。
    assert len(loaded.todo_source_ids) == len(loaded.rules)


def test_skips_underscore_and_weights_files(tmp_path: Path) -> None:
    """``_template.yaml`` 与 ``weights.yaml`` 不当规则列表处理。"""
    (tmp_path / "_template.yaml").write_text("这不是合法规则列表", encoding="utf-8")
    (tmp_path / "weights.yaml").write_text("也不是", encoding="utf-8")
    (tmp_path / "compliance.yaml").write_text(
        '- id: C-01\n  name: 层高\n  type: hard\n  check: "floor_height >= 3.0"\n'
        '  source: "测试"\n',
        encoding="utf-8",
    )
    assert len(load_rules_from_dir(tmp_path).rules) == 1


def test_missing_rules_dir_yields_empty_ruleset(tmp_path: Path) -> None:
    assert load_rules_from_dir(tmp_path / "does-not-exist").rules == ()


@pytest.mark.parametrize(
    "filename, expected_in_message",
    [
        ("tab_indent.yaml", "YAML"),
        ("chinese_colon.yaml", "规则"),
        ("missing_required.yaml", "id"),
        ("bad_rule_id.yaml", "id"),
        ("duplicate_id.yaml", "重复"),
        ("unknown_field.yaml", "serverity"),
        ("points_not_monotonic.yaml", "递增"),
        ("points_score_out_of_range.yaml", "分数"),
        ("expression_syntax.yaml", "语法"),
        ("unknown_field_in_expression.yaml", "floor_hieght"),
        ("bad_dimension.yaml", "dimension"),
        ("type_field_mismatch.yaml", "metric"),
        ("disallowed_function.yaml", "sum"),
        ("top_not_list.yaml", "列表"),
    ],
)
def test_bad_rule_files_are_rejected(
    tmp_path: Path, filename: str, expected_in_message: str
) -> None:
    """每个错误示例都必须让加载失败，且报错里能看出问题所在。"""
    target = tmp_path / filename
    target.write_bytes((BAD_RULES / filename).read_bytes())
    with pytest.raises(RuleLoadError) as excinfo:
        load_rules_from_dir(tmp_path)
    combined = "\n".join(excinfo.value.problems)
    assert expected_in_message in combined, f"{filename} 的报错里没提到 {expected_in_message}：\n{combined}"


def test_duplicate_id_across_files_is_rejected(tmp_path: Path) -> None:
    """ID 唯一性是全局的，跨文件也要查。"""
    body = '- id: C-01\n  name: 层高\n  type: hard\n  check: "floor_height >= 3.0"\n  source: "测试"\n'
    (tmp_path / "compliance.yaml").write_text(body, encoding="utf-8")
    (tmp_path / "quality.yaml").write_text(body, encoding="utf-8")
    with pytest.raises(RuleLoadError, match="重复"):
        load_rules_from_dir(tmp_path)


# —— 命名空间 —— #


def test_namespace_merges_project_scheme_and_derived() -> None:
    namespace = build_namespace(_project(), _scheme())
    assert namespace.values["site_area"] == 20_000.0, "项目层字段"
    assert namespace.values["floors"] == 18, "方案层字段"
    assert namespace.values["far"] == pytest.approx(48_000 / 20_000), "派生量"


def test_namespace_reports_missing_raw_field_for_derived() -> None:
    """引用派生量但底层字段缺失时，报出来的应当是**原始字段**名。

    对规则作者来说 "缺 volume" 可操作，"缺 shape_coef" 不可操作。
    """
    namespace = build_namespace(_project(), _scheme(volume=None))
    assert namespace.missing_for(["shape_coef"]) == ("volume",)


# —— evaluate：硬约束 —— #


def test_hard_rule_passes(ruleset: object) -> None:
    result = _evaluate_one(_scheme(floor_height=3.1), ruleset)
    assert _compliance(result, "C-01").status == "passed"


def test_hard_rule_fails_with_formatted_message(ruleset: object) -> None:
    """message 里的 ``{字段名}`` 要被换成实际取值。"""
    item = _compliance(_evaluate_one(_scheme(floor_height=2.9), ruleset), "C-01")
    assert item.status == "failed"
    assert item.message == "层高 2.9 m 低于 3.0 m"


def test_hard_rule_carries_traceability_fields(ruleset: object) -> None:
    """每条结果都要带 rule id、source、formula——报告溯源靠这三样。"""
    item = _compliance(_evaluate_one(_scheme(), ruleset), "C-01")
    assert item.rule_id == "C-01"
    assert item.source == "测试固定值"
    assert item.formula == "floor_height >= 3.0"


def test_hard_rule_extracts_limit_and_value(ruleset: object) -> None:
    item = _compliance(_evaluate_one(_scheme(floor_height=2.9), ruleset), "C-01")
    assert item.limit == ">= 3.0"
    assert item.value == pytest.approx(2.9)


def test_hard_rule_severity_from_definition(ruleset: object) -> None:
    assert _compliance(_evaluate_one(_scheme(), ruleset), "C-01").severity == "error"
    assert _compliance(_evaluate_one(_scheme(), ruleset), "C-02").severity == "warning"


def test_warning_failure_does_not_block(ruleset: object) -> None:
    """severity=warning 的不通过项不算"踢出排名"的阻断项。"""
    # gfa 拉高让 far 超过 far_max（2.5）：C-02 是 warning。
    result = _evaluate_one(_scheme(gfa=90_000.0, floor_height=3.1), ruleset)
    assert _compliance(result, "C-02").status == "failed"
    assert not result.has_blocking_failure


def test_error_failure_blocks(ruleset: object) -> None:
    result = _evaluate_one(_scheme(floor_height=2.9), ruleset)
    assert result.has_blocking_failure


def test_hard_rule_insufficient_data_lists_missing_fields(ruleset: object) -> None:
    """缺数据不抛异常：记 insufficient_data 并说清缺哪些字段。"""
    item = _compliance(_evaluate_one(_scheme(volume=None), ruleset), "C-03")
    assert item.status == "insufficient_data"
    assert item.missing_fields == ["volume"]
    assert "volume" in item.message


def test_hard_rule_placeholder_kept_when_value_missing(ruleset: object) -> None:
    """取不到值时 ``{字段名}`` 保持原样，而不是抛 KeyError 或印出 None。"""
    item = _compliance(_evaluate_one(_scheme(gfa=None), ruleset), "C-02")
    assert item.status == "insufficient_data"


# —— evaluate：when 条件 —— #


def test_when_false_marks_not_applicable(ruleset: object) -> None:
    item = _compliance(_evaluate_one(_scheme(structure_type="剪力墙"), ruleset), "C-04")
    assert item.status == "not_applicable"
    assert "不适用" in item.message


def test_when_true_evaluates_check(ruleset: object) -> None:
    passing = _evaluate_one(
        _scheme(structure_type="钢结构", risk_features=["超限构件"]), ruleset
    )
    assert _compliance(passing, "C-04").status == "passed"

    failing = _evaluate_one(_scheme(structure_type="钢结构", risk_features=["深基坑"]), ruleset)
    assert _compliance(failing, "C-04").status == "failed"


def test_when_missing_data_marks_insufficient(ruleset: object) -> None:
    """``when`` 用到的字段没填时，判不了"这条规则适不适用"，记 insufficient_data。"""
    item = _compliance(_evaluate_one(_scheme(structure_type=None), ruleset), "C-04")
    assert item.status == "insufficient_data"
    assert item.missing_fields == ["structure_type"]


def test_metric_when_false_is_not_applicable(ruleset: object) -> None:
    result = _evaluate_one(_scheme(floors=5), ruleset)
    assert result.metrics["Q-01"].status == "not_applicable"
    assert result.metrics["Q-01"].score is None


# —— evaluate：指标 —— #


def test_metric_scores_and_formula(ruleset: object) -> None:
    metric = _evaluate_one(_scheme(std_floor_repeat=0.80), ruleset).metrics["K-01"]
    assert metric.status == "scored"
    assert metric.value == pytest.approx(0.80)
    assert metric.score == pytest.approx(70.0)
    assert metric.formula == "std_floor_repeat；分段线性 0.5→0, 0.8→70, 0.95→100"
    assert metric.source == "测试固定值"


def test_metric_formula_expands_derived_quantity(ruleset: object) -> None:
    """指标取的是派生量时，公式里要带上派生量自己的算法，方便一路追到原始字段。"""
    metric = _evaluate_one(_scheme(), ruleset).metrics["G-01"]
    assert "shape_coef = envelope_area / volume" in metric.formula


def test_metric_insufficient_data_is_not_scored(ruleset: object) -> None:
    metric = _evaluate_one(_scheme(envelope_area=None), ruleset).metrics["G-01"]
    assert metric.status == "insufficient_data"
    assert metric.score is None
    assert metric.missing_fields == ["envelope_area"]


def test_metric_truncates_at_endpoints(ruleset: object) -> None:
    assert _evaluate_one(_scheme(std_floor_repeat=0.2), ruleset).metrics["K-01"].score == 0.0
    assert _evaluate_one(_scheme(std_floor_repeat=1.0), ruleset).metrics["K-01"].score == 100.0


# —— evaluate：维度聚合与覆盖率 —— #


def test_dimension_score_is_weighted_average(ruleset: object) -> None:
    """construction 维度有 K-01（权重 3）与 K-02（权重 1）。

    std_floor_repeat=0.80 → 70 分；component_types=24 → 在 [8,100] 与 [40,0] 之间，
    (24-8)/(40-8) = 0.5 → 50 分。加权平均 = (70*3 + 50*1) / 4 = 65。
    """
    result = _evaluate_one(_scheme(std_floor_repeat=0.80, component_types=24), ruleset)
    assert result.metrics["K-02"].score == pytest.approx(50.0)
    assert result.dimension_scores.construction == pytest.approx(65.0)


def test_coverage_is_one_when_all_metrics_have_data(ruleset: object) -> None:
    result = _evaluate_one(_scheme(), ruleset)
    assert result.dimension_coverage.construction == pytest.approx(1.0)


def test_coverage_drops_when_data_missing(ruleset: object) -> None:
    """K-01（权重 3）缺数据时，construction 覆盖率 = 1 / (3+1) = 0.25。"""
    result = _evaluate_one(_scheme(std_floor_repeat=None), ruleset)
    assert result.dimension_coverage.construction == pytest.approx(0.25)
    # 维度得分只由有数据的 K-02 决定。
    assert result.dimension_scores.construction == pytest.approx(
        result.metrics["K-02"].score
    )


def test_not_applicable_metric_excluded_from_coverage(ruleset: object) -> None:
    """``not_applicable`` 不计入覆盖率分母——它本来就不该参与这个方案的评估。

    quality 维度只有 Q-01 一条，floors=5 时它不适用，于是分母为 0，覆盖率记 0。
    """
    result = _evaluate_one(_scheme(floors=5), ruleset)
    assert result.dimension_coverage.quality == pytest.approx(0.0)
    assert result.dimension_scores.quality == pytest.approx(0.0)


def test_dimension_with_no_data_scores_zero(ruleset: object) -> None:
    """整个维度都没数据时得 0 分且覆盖率 0，而不是抛异常或给满分。"""
    result = _evaluate_one(_scheme(envelope_area=None, volume=None), ruleset)
    assert result.dimension_scores.green == pytest.approx(0.0)
    assert result.dimension_coverage.green == pytest.approx(0.0)


# —— evaluate：整体性质 —— #


def test_evaluate_is_deterministic(ruleset: object) -> None:
    """引擎必须是确定性的：同样输入跑两次结果完全一致。"""
    scheme = _scheme()
    first = _evaluate_one(scheme, ruleset)
    second = _evaluate_one(scheme, ruleset)
    assert first.model_dump() == second.model_dump()


def test_evaluate_returns_one_result_per_scheme(ruleset: object) -> None:
    schemes = [
        SchemeInput("1", "A", _scheme(floor_height=3.1)),
        SchemeInput("2", "B", _scheme(floor_height=2.9)),
    ]
    results = evaluate(_project(), schemes, ruleset)  # type: ignore[arg-type]
    assert [r.scheme_id for r in results] == ["1", "2"]
    assert [r.scheme_name for r in results] == ["A", "B"]
    assert not results[0].has_blocking_failure
    assert results[1].has_blocking_failure


def test_evaluate_covers_every_rule(ruleset: object) -> None:
    """每条规则都要在结果里出现——不能因为缺数据就悄悄漏掉一条。"""
    result = _evaluate_one(_scheme(), ruleset)
    assert {c.rule_id for c in result.compliance} == {
        r.id for r in ruleset.hard_rules  # type: ignore[attr-defined]
    }
    assert set(result.metrics) == {r.id for r in ruleset.metric_rules}  # type: ignore[attr-defined]


def test_empty_scheme_does_not_crash(ruleset: object) -> None:
    """全空方案是常见情形（刚建好还没填），必须能跑完并全部记为数据不足。"""
    result = _evaluate_one(SchemeParams(), ruleset)
    assert all(c.status in ("insufficient_data", "not_applicable") for c in result.compliance)
    assert all(m.status in ("insufficient_data", "not_applicable") for m in result.metrics.values())
