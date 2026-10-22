"""下沙路演的评分、输入缺失和报告边界；不指定任何方案必须排名第一。"""

import json
from pathlib import Path

import pytest
from app.agents.presentation import compact_evidence
from app.agents.readable import builtin_labels, reader_evidence, render_reader_demo
from app.agents.tools import AgentTools
from app.engine.rules import SchemeInput, evaluate, load_rules_from_dir
from app.models import Project, ProjectParams, Scheme, SchemeParams
from pydantic import ValidationError
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "data/schemes/xiasha-real"


def load_inputs():
    project = ProjectParams.model_validate(json.loads((CASE / "project.json").read_text(encoding="utf-8"))["params"])
    schemes = [SchemeInput(str(index), path.stem, SchemeParams.model_validate(json.loads(path.read_text(encoding="utf-8"))["params"]))
               for index, path in enumerate(sorted(CASE.glob("[ABC]_*.json")), 1)]
    return project, schemes, load_rules_from_dir(ROOT / "rules").select_packs(("GB", "ZJ"))


def test_xiasha_scores_use_each_construction_input_once_and_exclude_unverified_proxies():
    project, schemes, rules = load_inputs()
    assert len(schemes) == 3
    assert project.seismic_intensity is None
    for result in evaluate(project, schemes, rules):
        assert "G-02" not in result.metrics and "G-03" not in result.metrics
        for key in ("G-05", "Q-05", "Q-06"):
            assert result.metrics[key].status == "not_applicable"
            assert result.metrics[key].score is None
        k1, k2 = result.metrics["K-01"], result.metrics["K-02"]
        assert result.dimension_scores.construction == pytest.approx((k1.score * 2 + k2.score) / 3, abs=1e-4)
        assert sum(item.status == "insufficient_data" for item in result.compliance) == 5
        assert next(item for item in result.compliance if item.rule_id == "K-05").status == "failed"
    assert all(item.params.unit_mix is None and item.params.risk_features == [] for item in schemes)


def test_mic_wall_shear_missing_is_exposed_after_seismic_input_is_provided():
    project, schemes, rules = load_inputs()
    supplied = project.model_copy(update={"seismic_intensity": "6度(0.05g)"})
    result = evaluate(supplied, [schemes[1]], rules)[0]
    item = next(item for item in result.compliance if item.rule_id == "ZJ-S-05")
    assert item.status == "insufficient_data"
    assert "mic_precast_wall_shear_ratio" in item.missing_fields


def test_exclusions_cannot_disable_hard_rules_and_legacy_projects_keep_proxy_scores():
    with pytest.raises(ValidationError):
        ProjectParams(scoring_exclusions=["C-01"])
    project, schemes, rules = load_inputs()
    legacy = project.model_copy(update={"scoring_exclusions": []})
    result = evaluate(legacy, schemes[:1], rules)[0]
    assert all(result.metrics[key].status == "scored" for key in ("G-05", "Q-05", "Q-06"))


def test_report_keeps_counts_exclusions_and_teaching_notes_even_when_details_are_compacted():
    project, schemes, rules = load_inputs()
    rows = [row.model_dump(mode="json") for row in evaluate(project, schemes, rules)]
    evidence = {"evaluation": {"results": rows}, "data_notes": {
        "project_notes": project.project_notes, "scoring_exclusions": project.scoring_exclusions,
        "schemes": [{"scheme_id": row.scheme_id, "scheme_notes": row.params.scheme_notes} for row in schemes],
    }}
    brief = compact_evidence(evidence)
    assert all(row["insufficient_compliance_count"] == 5 for row in brief["evaluation"]["results"])
    assert all({"G-05", "Q-05", "Q-06"} <= set(row["unscored_metrics"]) for row in brief["evaluation"]["results"])
    view = reader_evidence(evidence, 2, "解释方案取舍", builtin_labels())
    assert "0.95" in view["方案数据说明"]
    assert "2025年12月" in view["案例来源与边界"]
    report = render_reader_demo({"reader_view": view, "response_mode": "brief_report"})
    assert "已知条件下的评分与取舍" in report
    assert "暂不计分" in report
    assert "教学假设" in report


def test_case_notes_are_scoped_to_the_current_project(engine):
    with Session(engine) as session:
        project = Project(name="本项目", params={"project_notes": "本项目来源"})
        other = Project(name="其他项目", params={"project_notes": "不得串入"})
        session.add_all([project, other])
        session.flush()
        session.add_all([
            Scheme(project_id=project.id, name="本候选", params={"scheme_notes": "本方案假设"}),
            Scheme(project_id=other.id, name="其他候选", params={"scheme_notes": "其他方案秘密"}),
            Scheme(project_id=project.id, name="副本", is_whatif=True, params={"scheme_notes": "副本假设"}),
        ])
        session.commit()
        project_id = project.id
    tools = AgentTools(engine, project_id)
    notes = tools.case_context()
    assert notes["project_notes"] == "本项目来源"
    assert [row["scheme_notes"] for row in notes["schemes"]] == ["本方案假设"]
    assert len(tools.case_context(True)["schemes"]) == 2
