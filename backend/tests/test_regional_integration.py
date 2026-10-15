"""地区册与自定义覆盖层、REST、Agent 证据的跨层回归。"""
from __future__ import annotations

import pytest
from app.agents.tools import AgentTools
from app.custom.rules import add_rule
from app.engine.rules import RuleDef, SchemeInput, evaluate, get_ruleset
from app.models import ProjectParams, SchemeParams
from app.schemas.meta import enriched_schema
from fastapi import HTTPException
from sqlmodel import Session

PROJECT = {"site_area": 18000, "far_max": 2.5, "density_max": 0.22, "height_max": 120,
           "climate_zone": "夏热冬冷", "seismic_intensity": "6度(0.05g)"}
MIC_SCHEME = {"structure_type": "MiC", "mic_system": "模块化叠合剪力墙结构", "floors": 20,
              "floor_height": 3.0, "concrete_grade": 30, "units": 320}


def _evaluate_items(packs, project_overrides=None, **overrides):
    local = [code for code in packs if code != "GB"]
    project = ProjectParams.model_validate({**PROJECT, "standard_packs": packs,
        "province": local[0] if local else None, **(project_overrides or {})})
    result = evaluate(project, [SchemeInput(scheme_id="1", name="规则审核样例",
        params=SchemeParams.model_validate({**MIC_SCHEME, **overrides}))], get_ruleset().select_packs(packs))[0]
    return {item.rule_id: item.status for item in result.compliance}


def _create(client, province=None, packs=None):
    response = client.post("/api/projects", json={"name": "地区审核", "params": {
        **PROJECT, "province": province, "standard_packs": packs,
    }})
    assert response.status_code == 201, response.text
    project = response.json()
    response = client.post(f"/api/projects/{project['id']}/schemes", json={"name": "样例", "params": MIC_SCHEME})
    assert response.status_code == 201, response.text
    return project


def test_region_scope_rejects_foreign_or_unspecified_province():
    for params in ({"standard_packs": ["GB", "ZJ"]},
                   {"province": "ZJ", "standard_packs": ["GB", "LN"]},
                   {"province": "ZJ", "standard_packs": ["GB", "LN", "ZJ"]}):
        with pytest.raises(ValueError, match="省份"):
            ProjectParams.model_validate(params)
    assert ProjectParams(province="ZJ", standard_packs=["GB", "ZJ"]).province == "ZJ"


def test_standard_pack_metadata_preserves_empty_and_required_gb():
    field = next(item for item in enriched_schema(ProjectParams)["fields"] if item["name"] == "standard_packs")
    assert field["empty_means_unknown"] is True
    assert field["required_options"] == ["GB"]
    assert field["allow_custom_options"] is False


def test_zero_measurements_are_judged_instead_of_rejected():
    assert SchemeParams(daylight_room_count=0, per_capita_green=0, sunlight_hours=0).daylight_room_count == 0
    result = _evaluate_items(["GB", "NX"], daylight_room_count=0, living_space_count=3)
    assert result["NX-Q-02"] == "failed"
    result = _evaluate_items(["GB", "JL"], per_capita_green=0)
    assert result["JL-G-01"] == "failed"
    with pytest.raises(ValueError):
        SchemeParams(total_elevators=0)


def test_local_metrics_wait_for_duplicate_weight_policy():
    with pytest.raises(ValueError, match="重复计权"):
        RuleDef.model_validate({"id": "ZJ-Q-99", "pack": "ZJ", "name": "重复指标", "type": "metric",
                               "dimension": "quality", "value": "floor_height", "source": "经验规则：示例",
                               "scoring": {"kind": "piecewise", "points": [[0, 0], [5, 100]]}})


def test_only_project_rules_enter_evidence_and_runtime_custom_survives(client, engine):
    with Session(engine) as session:
        add_rule(session, payload={"id": "X-91", "name": "运行期层高核对", "type": "hard",
                                  "check": "floor_height >= 3", "message": "层高不足",
                                  "source": "经验规则（审核）：层高核对"})
    project = _create(client)
    project_id = project["id"]
    post = client.post(f"/api/projects/{project_id}/evaluate")
    assert post.status_code == 200, post.text
    evaluation = post.json()
    ids = {item["rule_id"] for item in evaluation["results"][0]["compliance"]}
    assert "X-91" in ids
    assert not any(item.startswith("ZJ-") for item in ids)
    assert client.get(f"/api/projects/{project_id}/evaluate").json()["rule_count"] == evaluation["rule_count"]
    tools = AgentTools(engine, project_id)
    definitions = tools.rule_definitions()
    assert {item["pack"] for item in definitions} == {"GB"}
    assert any(item["id"] == "X-91" for item in definitions)
    with pytest.raises(ValueError):
        tools.explain_metric("ZJ-S-01")
    selected = client.get(f"/api/rules?project_id={project_id}").json()
    assert selected["rule_count"] == evaluation["rule_count"]
    ranked = client.post(f"/api/projects/{project_id}/rank", json={"role": "government", "monte_carlo_samples": 10})
    assert ranked.status_code == 200, ranked.text
    assert tools.get_result(project_id)["evaluation"]["rule_count"] == evaluation["rule_count"]


def test_switching_packs_invalidates_every_consumer_without_touching_other_project(client, engine):
    a = _create(client, "ZJ", ["GB"])
    b = _create(client)
    for project in (a, b):
        assert client.post(f"/api/projects/{project['id']}/evaluate").status_code == 200
    response = client.put(f"/api/projects/{a['id']}", json={"params": {**a["params"], "standard_packs": ["GB", "ZJ"]}})
    assert response.status_code == 200
    assert client.get(f"/api/projects/{a['id']}/evaluate").status_code == 409
    assert client.post(f"/api/projects/{a['id']}/rank", json={"role": "government"}).status_code == 409
    with pytest.raises(HTTPException) as error:
        AgentTools(engine, a["id"]).get_result(a["id"])
    assert error.value.status_code == 409
    assert client.get(f"/api/projects/{b['id']}/evaluate").status_code == 200
    current = client.post(f"/api/projects/{a['id']}/evaluate").json()
    assert "ZJ-S-01" in {item["rule_id"] for item in current["results"][0]["compliance"]}
    assert client.get(f"/api/projects/{a['id']}/evaluate").json()["rule_count"] == current["rule_count"]
    assert AgentTools(engine, a["id"]).explain_metric("ZJ-S-01")["pack"] == "ZJ"


def test_empty_region_is_explicitly_uncollected(client):
    packs = {item["code"]: item for item in client.get("/api/standards/packs").json()}
    assert packs["AH"]["coverage"] == "not_collected"
    assert "不能宣称" in packs["AH"]["note"]
    assert packs["ZJ"]["coverage"] == "partial"


def test_recommendation_is_warning_and_local_conditions_are_not_guessed():
    ln = _evaluate_items(["GB", "LN"], floor_height=3.1, has_fresh_air=True)
    assert ln["LN-Q-01"] == "passed"
    assert ln["LN-Q-04"] == "failed"
    assert get_ruleset().by_id("LN-Q-04").severity == "warning"
    sx = _evaluate_items(["GB", "SX"], green_ratio=0.32)
    assert sx["SX-G-01"] == "insufficient_data"
    sx = _evaluate_items(["GB", "SX"], green_ratio=0.32, sx_land_use_class="高层Ⅰ类")
    assert sx["SX-G-01"] == "failed"
    zj = _evaluate_items(["GB", "ZJ"], mic_system="模块化全预制剪力墙结构", floors=35,
                         project_overrides={"seismic_intensity": "7度(0.10g)"})
    assert zj["ZJ-S-06"] == "insufficient_data"
    high_ratio = _evaluate_items(["GB", "ZJ"], mic_system="模块化全预制剪力墙结构", floors=35,
                         mic_precast_wall_shear_ratio=0.9,
                         project_overrides={"seismic_intensity": "7度(0.10g)"})
    assert high_ratio["ZJ-S-06"] == "failed"
    low_ratio = _evaluate_items(["GB", "ZJ"], mic_system="模块化全预制剪力墙结构", floors=35,
                         mic_precast_wall_shear_ratio=0.8,
                         project_overrides={"seismic_intensity": "7度(0.10g)"})
    assert low_ratio["ZJ-S-06"] == "passed"
