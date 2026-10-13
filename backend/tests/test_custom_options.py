"""自定义枚举选项（覆盖层第一片）。

守住三条：
1. 只有**开放枚举**（``extensible=True``）能加值，``structure_type`` 这类封闭枚举必须拒绝
   ——规则会按它的取值分支，多一个规则不认识的取值会让规则静默失效；
2. 加进来的值只影响它挂的那个字段，且内建候选值永远保留；
3. 生产环境（``APP_ENV`` 非 dev）写接口 403，读接口照常可用。
"""

from __future__ import annotations

from typing import Any

import pytest
from app.config import get_settings
from app.custom.options import MAX_OPTION_LENGTH, extensible_fields
from fastapi.testclient import TestClient

FIELD = "risk_features"


def _scheme_field(client: TestClient, name: str) -> dict[str, Any]:
    body = client.get("/api/schema/scheme").json()
    field = next(item for item in body["fields"] if item["name"] == name)
    assert isinstance(field, dict)
    return field


def test_only_open_enums_are_extensible() -> None:
    """风险特征开放；超限不规则类型保持专业核定的封闭清单。"""
    fields = extensible_fields()
    assert set(fields) == {"risk_features"}
    # 封闭枚举绝不能出现在开放清单里
    for closed in ("structure_type", "mic_system", "climate_zone", "seismic_intensity", "irregularity_items"):
        assert closed not in fields
    # 开放字段要带上内建候选值，界面才知道哪些不可删
    assert "大悬挑" in fields[FIELD]["builtin"]


def test_added_option_shows_up_in_schema_and_can_be_removed(client: TestClient) -> None:
    before = _scheme_field(client, FIELD)

    created = client.post(
        "/api/custom/options", json={"field": FIELD, "value": "临近地铁振动"}
    )
    assert created.status_code == 201, created.text
    option_id = created.json()["id"]

    after = _scheme_field(client, FIELD)
    assert "临近地铁振动" in after["options"]
    assert after["custom_options"] == ["临近地铁振动"]
    # 内建候选值一个都不能少
    assert set(before["options"]) <= set(after["options"])
    # 别的字段不受影响
    assert "临近地铁振动" not in _scheme_field(client, "irregularity_items")["options"]

    removed = client.delete(f"/api/custom/options/{option_id}")
    assert removed.status_code == 204
    back = _scheme_field(client, FIELD)
    assert back["options"] == before["options"]
    assert back.get("custom_options", []) == []


def test_closed_enum_is_rejected_with_a_reason(client: TestClient) -> None:
    response = client.post(
        "/api/custom/options", json={"field": "structure_type", "value": "木结构"}
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "不支持自定义选项" in detail["message"]
    problem = detail["problems"][0]
    assert problem["code"] == "FIELD_NOT_EXTENSIBLE"
    # 改法要说清为什么，而不只是"不允许"
    assert "静默失效" in problem["fix"]


def test_duplicate_values_are_rejected(client: TestClient) -> None:
    builtin = _scheme_field(client, FIELD)["options"][0]
    clash = client.post("/api/custom/options", json={"field": FIELD, "value": builtin})
    assert clash.status_code == 422
    assert "内建选项" in clash.json()["detail"]["message"]

    assert (
        client.post("/api/custom/options", json={"field": FIELD, "value": "临近地铁振动"}).status_code
        == 201
    )
    again = client.post("/api/custom/options", json={"field": FIELD, "value": "临近地铁振动"})
    assert again.status_code == 422
    assert "已经添加过" in again.json()["detail"]["message"]


def test_empty_and_overlong_values_are_rejected(client: TestClient) -> None:
    blank = client.post("/api/custom/options", json={"field": FIELD, "value": "   "})
    assert blank.status_code == 422
    assert blank.json()["detail"]["problems"][0]["code"] == "OPTION_EMPTY"

    long_value = client.post(
        "/api/custom/options", json={"field": FIELD, "value": "长" * (MAX_OPTION_LENGTH + 1)}
    )
    assert long_value.status_code == 422
    assert long_value.json()["detail"]["problems"][0]["code"] == "OPTION_TOO_LONG"


def test_deleting_a_missing_option_reports_it(client: TestClient) -> None:
    response = client.delete("/api/custom/options/9999")
    assert response.status_code == 422
    assert response.json()["detail"]["problems"][0]["code"] == "OPTION_NOT_FOUND"


def test_writes_are_closed_outside_dev_but_reads_stay_open(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        blocked = client.post("/api/custom/options", json={"field": FIELD, "value": "临时"})
        assert blocked.status_code == 403, blocked.text
        assert "只在开发环境可用" in blocked.json()["detail"]

        # 读接口（前端渲染表单要用）不受影响
        listed = client.get("/api/custom/options")
        assert listed.status_code == 200
        assert {item["name"] for item in listed.json()["fields"]} == {
            "risk_features",
        }
    finally:
        get_settings.cache_clear()


def test_irregularity_enum_is_closed_in_registry_and_scheme_validation(client: TestClient) -> None:
    from app.models import SchemeParams
    from pydantic import ValidationError

    response = client.post("/api/custom/options", json={"field": "irregularity_items", "value": "自定义未知项"})
    assert response.status_code == 422
    assert response.json()["detail"]["problems"][0]["code"] == "FIELD_NOT_EXTENSIBLE"
    with pytest.raises(ValidationError):
        SchemeParams(irregularity_items=["自定义未知项"])
    assert SchemeParams(irregularity_items=[]).irregularity_items == []
