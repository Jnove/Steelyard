"""``/api/projects/{id}/evaluate`` 与 ``/api/rules[/reload]`` 的接口测试。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app.config import get_settings
from app.engine.rules import load_rules_from_dir, set_ruleset_for_testing
from fastapi.testclient import TestClient

GOOD_RULES = Path(__file__).resolve().parent / "fixtures" / "rules_good"


@pytest.fixture(autouse=True)
def fixed_ruleset() -> Iterator[None]:
    """整个模块用固定的测试规则集，不受 ``rules/`` 里种子规则变化影响。"""
    set_ruleset_for_testing(load_rules_from_dir(GOOD_RULES))
    yield
    set_ruleset_for_testing(None)


def _create_project(client: TestClient) -> int:
    response = client.post(
        "/api/projects",
        json={
            "name": "测试项目",
            "params": {
                "site_area": 20000,
                "far_max": 2.5,
                "density_max": 0.3,
                "height_max": 80,
                "climate_zone": "夏热冬冷",
            },
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _scheme_payload(name: str, **overrides: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "structure_type": "剪力墙",
        "units": 288,
        "floor_height": 3.1,
        "inner_area_ratio": 0.8,
        "gfa": 48000,
        "footprint": 5200,
        "buildings": 4,
        "floors": 18,
        "envelope_area": 26000,
        "volume": 140000,
        "std_floor_repeat": 0.8,
        "component_types": 24,
        "prefab_ratio_est": 0.45,
        "risk_features": ["深基坑"],
    }
    params.update(overrides)
    return {"name": name, "params": params}


def _add_scheme(client: TestClient, project_id: int, name: str, **overrides: Any) -> int:
    response = client.post(
        f"/api/projects/{project_id}/schemes", json=_scheme_payload(name, **overrides)
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


# —— POST /evaluate —— #


def test_evaluate_returns_one_result_per_scheme(client: TestClient) -> None:
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")
    _add_scheme(client, project_id, "B 方案", floor_height=2.9)

    response = client.post(f"/api/projects/{project_id}/evaluate")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == project_id
    assert body["rule_count"] == 8
    assert len(body["results"]) == 2
    assert [r["scheme_name"] for r in body["results"]] == ["A 方案", "B 方案"]


def test_evaluate_result_carries_traceability(client: TestClient) -> None:
    """每条合规结果与指标结果都要带 rule_id / source / formula。"""
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")

    result = client.post(f"/api/projects/{project_id}/evaluate").json()["results"][0]

    for item in result["compliance"]:
        assert item["rule_id"]
        assert item["source"]
        assert item["formula"]
    for metric in result["metrics"].values():
        assert metric["rule_id"]
        assert metric["source"]
        assert metric["formula"]


def test_evaluate_reports_dimension_scores_and_coverage(client: TestClient) -> None:
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")

    result = client.post(f"/api/projects/{project_id}/evaluate").json()["results"][0]

    assert set(result["dimension_scores"]) == {"quality", "structure", "construction", "green"}
    assert set(result["dimension_coverage"]) == {"quality", "structure", "construction", "green"}
    assert result["dimension_coverage"]["construction"] == pytest.approx(1.0)
    # 测试规则集里没有 structure 维度的指标，该维度得分与覆盖率都应为 0。
    assert result["dimension_scores"]["structure"] == pytest.approx(0.0)
    assert result["dimension_coverage"]["structure"] == pytest.approx(0.0)


def test_evaluate_is_idempotent(client: TestClient) -> None:
    """重复评估不该越评越多行，也不该改变结果。"""
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")

    first = client.post(f"/api/projects/{project_id}/evaluate").json()
    second = client.post(f"/api/projects/{project_id}/evaluate").json()
    assert first == second

    stored = client.get(f"/api/projects/{project_id}/evaluate").json()
    assert len(stored["results"]) == 1


def test_evaluate_persists_results(client: TestClient) -> None:
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案", floor_height=2.9)

    client.post(f"/api/projects/{project_id}/evaluate")
    stored = client.get(f"/api/projects/{project_id}/evaluate").json()

    assert len(stored["results"]) == 1
    failed = [c for c in stored["results"][0]["compliance"] if c["status"] == "failed"]
    assert any(c["rule_id"] == "C-01" for c in failed)


def test_get_evaluation_before_evaluating_is_empty(client: TestClient) -> None:
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")
    assert client.get(f"/api/projects/{project_id}/evaluate").json()["results"] == []


def test_evaluate_excludes_whatif_by_default(client: TestClient) -> None:
    project_id = _create_project(client)
    base_id = _add_scheme(client, project_id, "A 方案")
    payload = _scheme_payload("A 方案（假设）", floor_height=3.3)
    payload["is_whatif"] = True
    payload["parent_id"] = base_id
    assert client.post(f"/api/projects/{project_id}/schemes", json=payload).status_code == 201

    default_run = client.post(f"/api/projects/{project_id}/evaluate").json()
    assert len(default_run["results"]) == 1

    with_whatif = client.post(
        f"/api/projects/{project_id}/evaluate", params={"include_whatif": True}
    ).json()
    assert len(with_whatif["results"]) == 2


def test_evaluate_missing_project_is_404(client: TestClient) -> None:
    assert client.post("/api/projects/9999/evaluate").status_code == 404


def test_evaluate_without_schemes_is_400(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(f"/api/projects/{project_id}/evaluate")
    assert response.status_code == 400
    assert "方案" in response.json()["detail"]


def test_evaluate_handles_empty_params(client: TestClient) -> None:
    """刚建好还没填参数的方案也要能评估完，全部记为数据不足。"""
    project_id = _create_project(client)
    assert (
        client.post(
            f"/api/projects/{project_id}/schemes", json={"name": "空方案", "params": {}}
        ).status_code
        == 201
    )

    result = client.post(f"/api/projects/{project_id}/evaluate").json()["results"][0]
    assert all(
        c["status"] in ("insufficient_data", "not_applicable") for c in result["compliance"]
    )


# —— GET /api/rules —— #


def test_list_rules(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    assert body["rule_count"] == 8
    assert body["hard_count"] == 4
    assert body["metric_count"] == 4
    assert len(body["rules"]) == 8
    assert all(r["source_file"] == "engine.yaml" for r in body["rules"])


def test_list_rules_includes_derived_quantities(client: TestClient) -> None:
    """前端要展示"评分依据"，派生量的公式必须一起返回。"""
    body = client.get("/api/rules").json()
    names = {q["name"] for q in body["derived_quantities"]}
    assert {"far", "density", "shape_coef", "height"} <= names
    shape = next(q for q in body["derived_quantities"] if q["name"] == "shape_coef")
    assert shape["formula"] == "envelope_area / volume"
    assert shape["label"] == "体形系数"


def test_list_rules_exposes_rule_definition(client: TestClient) -> None:
    body = client.get("/api/rules").json()
    metric = next(r["definition"] for r in body["rules"] if r["definition"]["id"] == "K-01")
    assert metric["dimension"] == "construction"
    assert metric["scoring"]["kind"] == "piecewise"
    assert metric["weight_in_dimension"] == 3


# —— POST /api/rules/reload —— #


def test_reload_rules_in_dev(client: TestClient) -> None:
    get_settings.cache_clear()
    response = client.post("/api/rules/reload")
    assert response.status_code == 200, response.text
    # 热重载读的是仓库里真实的 rules/，条数与种子规则一致。
    assert response.json()["rule_count"] > 0
    assert response.json()["todo_source_ids"], "种子规则的 source 仍是 TODO，应当被标出来"


def test_reload_rules_forbidden_in_prod(client: TestClient, monkeypatch: Any) -> None:
    """生产环境不开放热重载：规则变更应当走 Git 提交 + CI 校验。"""
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        response = client.post("/api/rules/reload")
        assert response.status_code == 403
        assert "开发环境" in response.json()["detail"]
    finally:
        get_settings.cache_clear()
