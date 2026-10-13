"""Regression tests for runtime custom overlay integration boundaries."""
from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from app.agents.storage import AgentResultRow, ReportCacheRow
from app.agents.tools import AgentTools
from app.api.rank import RankRequest
from app.custom.signature import SIGNATURE_KEY, rules_signature
from app.engine.rules import load_rules_from_dir, set_ruleset_for_testing
from app.models import EvalResultRow, Scheme
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select


@pytest.fixture(autouse=True)
def fixed_rules() -> Iterator[None]:
    set_ruleset_for_testing(load_rules_from_dir(Path(__file__).parent / "fixtures" / "rules_good"))
    yield
    set_ruleset_for_testing(None)


def setup_project(client: TestClient, custom: dict | None = None) -> tuple[int, int]:
    project = client.post("/api/projects", json={"name": "custom review", "params": {
        "site_area": 20000, "far_max": 2.5, "density_max": 0.3, "height_max": 80,
    }})
    assert project.status_code == 201, project.text
    pid = project.json()["id"]
    scheme = client.post(f"/api/projects/{pid}/schemes", json={"name": "A", "params": {
        "floor_height": 3.1, "inner_area_ratio": 0.8, "custom": custom or {},
    }})
    assert scheme.status_code == 201, scheme.text
    return pid, scheme.json()["id"]


FIELD = {"key": "wall_share", "label": "wall share", "kind": "ratio"}
METRIC = {"id": "X-01", "name": "wall metric", "type": "metric", "dimension": "quality",
          "source": "经验规则（测试）：测试输入约束", "value": "wall_share", "when": "wall_share >= 0",
          "scoring": {"kind": "piecewise", "points": [[0, 0], [1, 100]]}, "weight_in_dimension": 1}


def test_registered_custom_field_scores_and_is_explained(client: TestClient, engine: Any) -> None:
    field = client.post("/api/custom/fields", json=FIELD)
    assert field.status_code == 201, field.text
    created = client.post("/api/custom/rules", json=METRIC)
    assert created.status_code == 201, created.text
    assert created.json()["is_valid"] is True
    assert client.get("/api/custom/rules").json()[0]["is_valid"] is True
    pid, _ = setup_project(client, {"wall_share": 0.62})
    evaluated = client.post(f"/api/projects/{pid}/evaluate")
    assert evaluated.status_code == 200, evaluated.text
    result = evaluated.json()["results"][0]["metrics"]["X-01"]
    assert result["status"] == "scored"
    assert result["score"] == pytest.approx(62)
    tools = AgentTools(engine, pid)
    assert tools.explain_metric("X-01")["source"] == METRIC["source"]
    assert "X-01" in {r["id"] for r in tools.rule_definitions()}
    deleted = client.delete(f"/api/custom/fields/{field.json()['id']}")
    assert deleted.status_code in (409, 422)
    assert client.get("/api/rules").status_code == 200


@pytest.mark.parametrize("kind,value", [("number", True), ("integer", 1.5), ("integer", False),
    ("ratio", 1.01), ("ratio", "0.5"), ("integer", 10 ** 400), ("text", 4), ("list", "one"), ("list", [1])])
def test_scheme_api_rejects_custom_type_bypass(client: TestClient, kind: str, value: Any) -> None:
    assert client.post("/api/custom/fields", json={**FIELD, "kind": kind}).status_code == 201
    pid, sid = setup_project(client)
    response = client.post(f"/api/projects/{pid}/schemes", json={"name": "bad", "params": {"custom": {"wall_share": value}}})
    assert response.status_code == 422, response.text
    updated = client.put(f"/api/projects/{pid}/schemes/{sid}", json={"params": {"custom": {"wall_share": value}}})
    assert updated.status_code == 422, updated.text
    assert client.get(f"/api/projects/{pid}/schemes/{sid}").json()["params"]["custom"] == {}


@pytest.mark.parametrize("key", ["floor_height", "site_area", "sv_ratio", "unregistered_value"])
def test_custom_input_cannot_shadow_or_add_unregistered_fields(client: TestClient, key: str) -> None:
    pid, _ = setup_project(client)
    response = client.post(f"/api/projects/{pid}/schemes", json={"name": "bad", "params": {"custom": {key: 0.8}}})
    assert response.status_code == 422, response.text


def test_rule_mutation_invalidates_old_scores_and_agent_evidence(client: TestClient, engine: Any) -> None:
    pid, _ = setup_project(client)
    assert client.post(f"/api/projects/{pid}/evaluate").status_code == 200
    with Session(engine) as session:
        session.add(ReportCacheRow(key="old", project_id=pid, output={"conclusion": "old"}))
        session.commit()
    added = client.post("/api/custom/rules", json={**METRIC, "value": "inner_area_ratio", "when": "inner_area_ratio >= 0"})
    assert added.status_code == 201, added.text
    assert client.get(f"/api/projects/{pid}/evaluate").json()["results"] == []
    assert client.post(f"/api/projects/{pid}/rank", json={"weights": [1, 1, 1, 1]}).status_code == 409
    with Session(engine) as session:
        assert session.exec(select(EvalResultRow)).all() == []
        assert session.exec(select(AgentResultRow)).all() == []
        assert session.exec(select(ReportCacheRow)).all() == []
    assert client.post(f"/api/projects/{pid}/evaluate").status_code == 200
    assert client.delete(f"/api/custom/rules/{added.json()['id']}").status_code == 204
    assert client.post(f"/api/projects/{pid}/rank", json={"weights": [1, 1, 1, 1]}).status_code == 409


def test_agent_custom_whatif_updates_nested_value_and_keeps_parent(client: TestClient, engine: Any) -> None:
    assert client.post("/api/custom/fields", json=FIELD).status_code == 201
    pid, sid = setup_project(client, {"wall_share": 0.4})
    tools = AgentTools(engine, pid)
    changed = tools.update_scheme_param(sid, "wall_share", 0.8)
    assert changed["before"] == 0.4
    with Session(engine) as session:
        parent = session.get(Scheme, sid)
        copy = session.get(Scheme, changed["scheme_id"])
        assert parent.params["custom"] == {"wall_share": 0.4}
        assert copy.params["custom"] == {"wall_share": 0.8}
    with pytest.raises(ValueError):
        tools.update_scheme_param(sid, "wall_share", 2)


def test_export_user_strings_remain_python_literals(client: TestClient) -> None:
    text = 'quote" slash\\ newline\n__import__("os")'
    assert client.post("/api/custom/fields", json={**FIELD, "label": text, "description": text, "unit": text}).status_code == 201
    assert client.post("/api/custom/options", json={"field": "risk_features", "value": 'quote"\\tail'}).status_code == 201
    exported = client.get("/api/custom/export").json()
    fields_tree = ast.parse("class SchemeParams:\n" + exported["fields_python"])
    assert len(fields_tree.body) == 1
    assert isinstance(fields_tree.body[0], ast.ClassDef)
    assert len(fields_tree.body[0].body) == 1
    assert isinstance(fields_tree.body[0].body[0], ast.AnnAssign)
    assert text in [node.value for node in ast.walk(fields_tree) if isinstance(node, ast.Constant)]
    options_tree = ast.parse("options = [\n" + exported["options_python"] + "]")
    assert isinstance(options_tree.body[0].value.elts[0], ast.Constant)


def test_reserved_names_cannot_create_ambiguous_exports(client: TestClient) -> None:
    assert client.post("/api/custom/fields", json={**FIELD, "key": "class"}).status_code == 422
    assert client.post("/api/custom/rules", json={**METRIC, "id": "Q-99", "value": "inner_area_ratio", "when": "inner_area_ratio > 0"}).status_code == 422
    assert client.post("/api/custom/weight-templates", json={"name": "custom:3", "weights": [1, 1, 1, 1]}).status_code == 422


def test_custom_rule_changes_agent_cache_key(client: TestClient, engine: Any) -> None:
    pid, _ = setup_project(client)
    tools = AgentTools(engine, pid)
    request = RankRequest(weights=[1, 1, 1, 1])
    baseline = tools.cache_key(request)
    added = client.post("/api/custom/rules", json={**METRIC, "value": "inner_area_ratio", "when": "inner_area_ratio > 0"})
    assert added.status_code == 201, added.text
    assert tools.cache_key(request) != baseline


def test_reload_same_rule_id_with_new_threshold_rejects_old_evidence(
    client: TestClient, engine: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api import rules as rules_api
    from app.engine import rules as rule_engine

    pid, _ = setup_project(client)
    original = client.post(f"/api/projects/{pid}/evaluate").json()
    assert client.get(f"/api/projects/{pid}/evaluate").json()["rule_count"] == original["rule_count"]
    tools = AgentTools(engine, pid)
    old_key = tools.cache_key(RankRequest(weights=[1, 1, 1, 1]))
    definitions = [rule.model_dump(mode="json") for rule in rule_engine.get_ruleset().rules]
    changed = next(rule for rule in definitions if rule["id"] == "C-01")
    changed["check"] = "floor_height >= 3.2"
    (tmp_path / "rules.yaml").write_text(yaml.safe_dump(definitions, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(rules_api, "reload_ruleset", lambda: rule_engine.reload_ruleset(tmp_path))
    assert client.post("/api/rules/reload").status_code == 200
    assert len(rule_engine.get_ruleset().rules) == original["rule_count"]
    assert tools.cache_key(RankRequest(weights=[1, 1, 1, 1])) != old_key
    assert client.get(f"/api/projects/{pid}/evaluate").status_code == 409
    assert client.post(f"/api/projects/{pid}/rank", json={"weights": [1, 1, 1, 1]}).status_code == 409
    with pytest.raises(HTTPException) as rejected:
        tools.get_result(pid)
    assert rejected.value.status_code == 409
    new = client.post(f"/api/projects/{pid}/evaluate")
    assert new.status_code == 200, new.text
    item = next(item for item in new.json()["results"][0]["compliance"] if item["rule_id"] == "C-01")
    assert item["status"] == "failed"
    assert client.get(f"/api/projects/{pid}/evaluate").status_code == 200
    assert client.post(f"/api/projects/{pid}/rank", json={"weights": [1, 1, 1, 1]}).status_code == 200


def test_legacy_unsigned_results_are_rejected_without_rewriting_data(client: TestClient, engine: Any) -> None:
    pid, sid = setup_project(client)
    assert client.post(f"/api/projects/{pid}/evaluate").status_code == 200
    with Session(engine) as session:
        row = session.exec(select(EvalResultRow).where(EvalResultRow.scheme_id == sid)).one()
        row.result = {key: value for key, value in row.result.items() if key != SIGNATURE_KEY}
        agent = session.get(AgentResultRow, pid)
        agent.evaluation = {key: value for key, value in agent.evaluation.items() if key != SIGNATURE_KEY}
        session.add(row)
        session.add(agent)
        session.commit()
        original = dict(row.result)
        original_params = dict(session.get(Scheme, sid).params)
    assert client.get(f"/api/projects/{pid}/evaluate").status_code == 409
    assert client.post(f"/api/projects/{pid}/rank", json={"weights": [1, 1, 1, 1]}).status_code == 409
    with pytest.raises(HTTPException) as rejected:
        AgentTools(engine, pid).get_result(pid)
    assert rejected.value.status_code == 409
    with Session(engine) as session:
        assert session.exec(select(EvalResultRow).where(EvalResultRow.scheme_id == sid)).one().result == original
        assert session.get(Scheme, sid).params == original_params


def test_rule_signature_excludes_checkout_origin_paths(engine: Any) -> None:
    from app.engine.rules import RuleSet, get_ruleset

    base = get_ruleset()
    moved = RuleSet(rules=base.rules, origins={rule.id: "Z:/other/worktree/rules.yaml" for rule in base.rules}, todo_source_ids=base.todo_source_ids)
    with Session(engine) as session:
        assert rules_signature(session, ruleset=base) == rules_signature(session, ruleset=moved)


@pytest.mark.parametrize("kind,value", [("number", 0), ("number", -2.25), ("integer", 0), ("integer", -2)])
def test_generic_numeric_export_preserves_zero_and_negative_values(client: TestClient, kind: str, value: Any) -> None:
    assert client.post("/api/custom/fields", json={**FIELD, "kind": kind}).status_code == 201
    pid, sid = setup_project(client, {"wall_share": value})
    assert client.get(f"/api/projects/{pid}/schemes/{sid}").json()["params"]["custom"]["wall_share"] == value
    exported = client.get("/api/custom/export").json()
    tree = ast.parse("class SchemeParams:\n" + exported["fields_python"])
    field_call = tree.body[0].body[0].value
    assert "gt" not in {argument.arg for argument in field_call.keywords}
    assert any("校验器" in note for note in exported["notes"])
