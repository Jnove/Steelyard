"""自定义规则（覆盖层）：校验同源、与内建规则合并、可删除。

守住四条：
1. **校验同源**——界面新增的规则过的是 ``check_rules`` 的同一份校验器，
   报错措辞与"怎么改"完全一致；
2. 自定义规则接在内建规则**后面**一起参与评估，可在 ``GET /api/rules`` 里看到，
   ``source_file`` 固定为"（界面自定义）"；
3. ID 不能与内建规则重复（全局唯一）；
4. 比文件更严：``source`` 必填且不允许挂 TODO——自定义规则没有 CI 把关，出处是唯一依据。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app.config import get_settings
from app.custom.rules import CUSTOM_ORIGIN
from app.engine.rules import load_rules_from_dir, set_ruleset_for_testing
from fastapi.testclient import TestClient

GOOD_RULES = Path(__file__).resolve().parent / "fixtures" / "rules_good"
#: 固定测试规则集里有 8 条内建规则（见 fixtures/rules_good/engine.yaml）。
BUILTIN_COUNT = 8


@pytest.fixture(autouse=True)
def fixed_ruleset() -> Iterator[None]:
    """整个模块用固定的测试规则集，不受 ``rules/`` 里种子规则变化影响。"""
    set_ruleset_for_testing(load_rules_from_dir(GOOD_RULES))
    yield
    set_ruleset_for_testing(None)


METRIC_RULE: dict[str, Any] = {
    "id": "X-01",
    "name": "自定义：得房率越高越好",
    "type": "metric",
    "dimension": "quality",
    "source": "经验规则（专业组）：本次比选自定，得房率高对住户有利",
    "value": "inner_area_ratio",
    "scoring": {"kind": "piecewise", "points": [[0.70, 0], [0.85, 100]]},
    "weight_in_dimension": 1,
}

HARD_RULE: dict[str, Any] = {
    "id": "X-02",
    "name": "自定义：层高不得低于 3.2",
    "type": "hard",
    "source": "经验规则（结构组）：本期要求比国标更严，取 3.2 m",
    "check": "floor_height >= 3.2",
    "message": "层高 {floor_height} m 低于本期自定的 3.2 m",
}


def _create_project(client: TestClient) -> int:
    response = client.post(
        "/api/projects",
        json={
            "name": "自定义规则测试项目",
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


def _add_scheme(client: TestClient, project_id: int, name: str) -> None:
    response = client.post(
        f"/api/projects/{project_id}/schemes",
        json={
            "name": name,
            "params": {
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
            },
        },
    )
    assert response.status_code == 201, response.text


def _problems(response: Any) -> list[dict[str, str]]:
    return list(response.json()["detail"]["problems"])


# —— 合并与生效 —— #


def test_custom_rules_join_the_ruleset_and_can_be_removed(client: TestClient) -> None:
    before = client.get("/api/rules").json()
    assert before["rule_count"] == BUILTIN_COUNT

    created = client.post("/api/custom/rules", json=METRIC_RULE)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["is_valid"] is True
    assert body["origin"] == CUSTOM_ORIGIN
    assert body["name"] == METRIC_RULE["name"]
    assert body["type"] == "metric"
    assert body["dimension"] == "quality"

    after = client.get("/api/rules").json()
    assert after["rule_count"] == BUILTIN_COUNT + 1
    custom = [r for r in after["rules"] if r["definition"]["id"] == "X-01"]
    assert len(custom) == 1
    # 前端靠这个标识给自定义规则打标：未进入 git、不参与 CI 校验
    assert custom[0]["source_file"] == CUSTOM_ORIGIN
    # 内建规则一条都不能少，且仍排在前面前
    assert [r["definition"]["id"] for r in after["rules"]][:BUILTIN_COUNT] == [
        r["definition"]["id"] for r in before["rules"]
    ]

    assert client.delete(f"/api/custom/rules/{body['id']}").status_code == 204
    assert client.get("/api/rules").json()["rule_count"] == BUILTIN_COUNT
    assert client.get("/api/custom/rules").json() == []


def test_custom_rules_take_effect_in_evaluation(client: TestClient) -> None:
    project_id = _create_project(client)
    _add_scheme(client, project_id, "A 方案")

    baseline = client.post(f"/api/projects/{project_id}/evaluate").json()
    assert baseline["rule_count"] == BUILTIN_COUNT
    assert "X-02" not in {c["rule_id"] for c in baseline["results"][0]["compliance"]}

    assert client.post("/api/custom/rules", json=HARD_RULE).status_code == 201
    assert client.post("/api/custom/rules", json=METRIC_RULE).status_code == 201

    evaluated = client.post(f"/api/projects/{project_id}/evaluate").json()
    assert evaluated["rule_count"] == BUILTIN_COUNT + 2
    result = evaluated["results"][0]

    # 硬约束：层高 3.1 < 3.2，应当判不通过，并带上出处供报告溯源
    failed = {c["rule_id"]: c for c in result["compliance"] if c["status"] == "failed"}
    assert "X-02" in failed
    assert failed["X-02"]["source"] == HARD_RULE["source"]

    # 评分指标：得房率 0.8 → 落在 [0.70, 0.85] 之间，拿到一个 0–100 的分
    metric = result["metrics"]["X-01"]
    assert metric["dimension"] == "quality"
    assert metric["score"] == pytest.approx((0.8 - 0.70) / (0.85 - 0.70) * 100)
    assert metric["source"] == METRIC_RULE["source"]


# —— 校验同源 —— #


def test_validation_matches_check_rules(client: TestClient) -> None:
    unknown = client.post("/api/custom/rules", json={**METRIC_RULE, "colour": "红"})
    assert unknown.status_code == 422
    problem = _problems(unknown)[0]
    assert problem["code"] == "UNKNOWN_FIELD"
    assert "无法识别的字段" in problem["message"]
    assert problem["fix"]  # 与 check_rules 一样要给出"怎么改"

    typo = client.post("/api/custom/rules", json={**HARD_RULE, "check": "floor_hight >= 3.0"})
    assert typo.status_code == 422
    problem = _problems(typo)[0]
    assert problem["code"] == "BAD_EXPRESSION"
    assert "floor_height" in problem["fix"]  # 拼写候选

    flat = client.post(
        "/api/custom/rules",
        json={**METRIC_RULE, "scoring": {"kind": "piecewise", "points": [[0.9, 0], [0.7, 100]]}},
    )
    assert flat.status_code == 422
    problem = _problems(flat)[0]
    assert problem["code"] == "POINTS_NOT_MONOTONIC"
    assert "从小到大" in problem["fix"]

    bad_id = client.post("/api/custom/rules", json={**METRIC_RULE, "id": "X1"})
    assert bad_id.status_code == 422
    assert _problems(bad_id)[0]["code"] == "BAD_RULE_ID"

    # 请求体不是对象时由 FastAPI 自己拦下（detail 是它那套列表结构），
    # 域层的 RULE_NOT_OBJECT 只在直接调用领域函数时出现。
    not_object = client.post("/api/custom/rules", json=["不是对象"])
    assert not_object.status_code == 422
    assert isinstance(not_object.json()["detail"], list)


def test_source_is_required_and_todo_is_refused(client: TestClient) -> None:
    missing = client.post("/api/custom/rules", json={k: v for k, v in METRIC_RULE.items() if k != "source"})
    assert missing.status_code == 422
    problem = _problems(missing)[0]
    assert problem["code"] == "SOURCE_REQUIRED"
    assert "出处" in problem["fix"]

    todo = client.post("/api/custom/rules", json={**METRIC_RULE, "source": "TODO(专业组)：待补"})
    assert todo.status_code == 422
    assert _problems(todo)[0]["code"] == "SOURCE_TODO"


def test_ids_must_be_globally_unique(client: TestClient) -> None:
    reserved = client.post("/api/custom/rules", json={**METRIC_RULE, "id": "C-01"})
    assert reserved.status_code == 422
    problem = _problems(reserved)[0]
    assert problem["code"] == "RULE_ID_RESERVED"
    assert "C-01" in problem["message"]

    assert client.post("/api/custom/rules", json=METRIC_RULE).status_code == 201
    duplicate = client.post("/api/custom/rules", json=METRIC_RULE)
    assert duplicate.status_code == 422
    assert _problems(duplicate)[0]["code"] == "RULE_ID_DUPLICATE"


def test_delete_missing_rule_reports_it(client: TestClient) -> None:
    response = client.delete("/api/custom/rules/9999")
    assert response.status_code == 422
    assert _problems(response)[0]["code"] == "RULE_NOT_FOUND"


def test_writes_are_closed_outside_dev(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        blocked = client.post("/api/custom/rules", json=METRIC_RULE)
        assert blocked.status_code == 403, blocked.text
        assert "只在开发环境可用" in blocked.json()["detail"]
        # 读接口照常：前端要能列出规则
        assert client.get("/api/custom/rules").status_code == 200
        assert client.get("/api/rules").status_code == 200
    finally:
        get_settings.cache_clear()
