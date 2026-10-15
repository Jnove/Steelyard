"""Schema 端点与 schema 导出脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from app.models import EvalResult, ProjectParams, SchemeParams
from fastapi.testclient import TestClient


@pytest.fixture
def exported_schemas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    from scripts import export_schema

    out = tmp_path / "data" / "schema"
    monkeypatch.setattr(export_schema, "OUT_DIR", out)
    assert export_schema.main() == 0
    return out


def read_schema(out: Path, name: str) -> dict[str, Any]:
    return json.loads((out / "jsonschema" / f"{name}.schema.json").read_text(encoding="utf-8"))


class TestSchemaEndpoint:
    @pytest.mark.parametrize(
        ("route", "model"),
        [("project", ProjectParams), ("scheme", SchemeParams), ("eval", EvalResult)],
    )
    def test_field_descriptions_preserved(self, client: TestClient, route, model) -> None:
        resp = client.get(f"/api/schema/{route}")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"title", "description", "group_order", "fields"}
        fields = {field["name"]: field for field in body["fields"]}
        assert set(fields) == set(model.model_fields)
        for name, field in model.model_fields.items():
            assert fields[name]["description"] == field.description

    def test_all_schemas(self, client: TestClient) -> None:
        resp = client.get("/api/schema")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"project_params", "scheme_params", "eval_result"}

    def test_scheme_schema_has_chinese_meta(self, client: TestClient) -> None:
        resp = client.get("/api/schema/scheme")
        body = resp.json()

        assert body["title"] == "方案参数"
        assert body["group_order"][0] == "基本信息"

        by_name = {f["name"]: f for f in body["fields"]}
        # 关键字段的中文 label / unit / group 必须正确
        assert by_name["gfa"]["label"] == "总建筑面积"
        assert by_name["gfa"]["unit"] == "m²"
        assert by_name["gfa"]["group"] == "结构与造价"

        assert by_name["structure_type"]["enum"] == [
            "剪力墙",
            "框架-剪力墙",
            "框架",
            "钢结构",
            "MiC",
        ]
        assert by_name["risk_features"]["options"][0] == "大悬挑"
        assert by_name["prefab_ratio_est"]["group"] == "绿色低碳"

    def test_project_schema_has_chinese_meta(self, client: TestClient) -> None:
        resp = client.get("/api/schema/project")
        body = resp.json()
        by_name = {f["name"]: f for f in body["fields"]}
        assert by_name["site_area"]["label"] == "用地面积"
        assert by_name["site_area"]["unit"] == "m²"
        assert by_name["climate_zone"]["enum"][2] == "夏热冬冷"


class TestExportScript:
    """scripts/export_schema.py 的产物校验。"""

    def test_export_filenames_and_english_model_titles(self, exported_schemas: Path) -> None:
        names = {
            "ProjectParams",
            "SchemeParams",
            "EvalResult",
            "ProjectRead",
            "ProjectCreate",
            "SchemeRead",
            "SchemeCreate",
            "EvaluateResponse",
            "RulesResponse",
            "ImportResponse",
            "RankRequest",
            "RankResponse",
            "AgentRequest",
            "AgentOutput",
            "QuestionSuggestions",
        }
        assert {p.name for p in (exported_schemas / "jsonschema").iterdir()} == {
            f"{name}.schema.json" for name in names
        }
        for name in names:
            schema = read_schema(exported_schemas, name)
            assert schema["title"] == name
            assert schema["type"] == "object"
            for key, definition in schema.get("$defs", {}).items():
                assert definition["title"] == key
                assert key.isascii()

    @pytest.mark.parametrize("route", ["project", "scheme", "eval"])
    def test_enriched_exports_match_endpoint(
        self, exported_schemas: Path, client: TestClient, route: str
    ) -> None:
        exported = json.loads(
            (exported_schemas / f"{route}.schema.json").read_text(encoding="utf-8")
        )
        assert exported == client.get(f"/api/schema/{route}").json()

    @pytest.mark.parametrize("name", ["ProjectRead", "ProjectCreate", "SchemeRead", "SchemeCreate"])
    def test_resource_params_retain_nested_metadata(
        self, exported_schemas: Path, name: str
    ) -> None:
        schema = read_schema(exported_schemas, name)
        params_name = "ProjectParams" if name.startswith("Project") else "SchemeParams"
        assert schema["properties"]["params"]["$ref"] == f"#/$defs/{params_name}"
        params = schema["$defs"][params_name]
        field = params["properties"]["site_area" if name.startswith("Project") else "gfa"]
        assert (
            field["description"]
            == field["label"]
            == ("用地面积" if name.startswith("Project") else "总建筑面积")
        )
        assert field["unit"] == "m²"
        assert field["essential"] is True
        assert field["anyOf"] == [{"exclusiveMinimum": 0, "type": "number"}, {"type": "null"}]
        assert params["group_order"][0] == "基本信息"
        assert params["description"]
        assert "name" in schema["required"]
        if name.endswith("Read"):
            assert "params" in schema["required"]
            assert schema["properties"]["created_at"]["format"] == "date-time"
        else:
            assert "params" not in schema["required"]
            assert schema["properties"]["name"]["minLength"] == 1

    def test_parameter_collections_enums_and_constraints(self, exported_schemas: Path) -> None:
        props = read_schema(exported_schemas, "SchemeParams")["properties"]
        assert props["unit_mix"]["anyOf"] == [
            {"additionalProperties": {"type": "integer"}, "type": "object"},
            {"type": "null"},
        ]
        assert props["risk_features"]["items"] == {"type": "string"}
        assert props["risk_features"]["options"][0] == "大悬挑"
        assert props["structure_type"]["anyOf"][0]["enum"] == props["structure_type"]["enum"]
        assert props["inner_area_ratio"]["anyOf"] == [
            {"minimum": 0, "maximum": 1, "type": "number"},
            {"type": "null"},
        ]

    @pytest.mark.parametrize("name", ["EvalResult", "EvaluateResponse"])
    def test_evaluation_nested_types_and_descriptions(
        self, exported_schemas: Path, name: str
    ) -> None:
        schema = read_schema(exported_schemas, name)
        if name == "EvaluateResponse":
            assert schema["properties"]["results"]["items"] == {"$ref": "#/$defs/EvalResult"}
            result = schema["$defs"]["EvalResult"]
        else:
            result = schema
        props = result["properties"]
        assert props["compliance"]["items"] == {"$ref": "#/$defs/ComplianceItem"}
        assert props["compliance"]["description"] == "合规判定清单"
        assert props["metrics"]["additionalProperties"] == {"$ref": "#/$defs/MetricResult"}
        assert props["dimension_scores"]["$ref"] == "#/$defs/DimensionScores"
        assert props["dimension_coverage"]["$ref"] == "#/$defs/DimensionCoverage"
        assert props["topsis"]["anyOf"] == [{"$ref": "#/$defs/RankResult"}, {"type": "null"}]
        metric = schema["$defs"]["MetricResult"]["properties"]
        assert metric["source"]["description"] == "规则来源（专业组 / 规范）"
        assert metric["score"]["anyOf"] == [
            {"minimum": 0, "maximum": 100, "type": "number"},
            {"type": "null"},
        ]

    def test_rules_and_import_nested_types(self, exported_schemas: Path) -> None:
        rules = read_schema(exported_schemas, "RulesResponse")
        assert rules["properties"]["rules"]["items"] == {"$ref": "#/$defs/RuleRead"}
        assert rules["$defs"]["RuleRead"]["properties"]["definition"]["$ref"] == "#/$defs/RuleDef"
        assert rules["properties"]["derived_quantities"]["items"] == {
            "$ref": "#/$defs/DerivedQuantityRead"
        }
        assert (
            rules["$defs"]["DerivedQuantityRead"]["properties"]["formula"]["description"]
            == "计算公式"
        )
        imported = read_schema(exported_schemas, "ImportResponse")
        assert imported["properties"]["created"]["items"] == {"$ref": "#/$defs/ImportCreatedItem"}
        assert imported["properties"]["errors"]["items"] == {"$ref": "#/$defs/ImportErrorItem"}
        error = imported["$defs"]["ImportErrorItem"]["properties"]
        assert error["message"]["description"] == "面向用户的错误说明"
        assert error["field"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
