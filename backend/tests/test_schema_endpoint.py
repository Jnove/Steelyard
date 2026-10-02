"""Schema 端点与 schema 导出脚本测试。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


class TestSchemaEndpoint:
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

    def test_export_writes_three_files(self, tmp_path: Path) -> None:
        import importlib
        import sys

        # scripts/ 在项目根目录，不在 backend/ 下，需要把根目录加进 path
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from scripts import export_schema  # type: ignore[import-not-found]

        importlib.reload(export_schema)

        fake_root = tmp_path
        (fake_root / "data").mkdir()
        original_root = export_schema.ROOT
        original_out = export_schema.OUT_DIR
        export_schema.ROOT = fake_root  # type: ignore[attr-defined]
        # ROOT 改了之后，OUT_DIR 也得跟着改，否则它仍指向真实的 ROOT/data/schema
        export_schema.OUT_DIR = fake_root / "data" / "schema"  # type: ignore[attr-defined]
        try:
            rc = export_schema.main()
        finally:
            export_schema.ROOT = original_root  # type: ignore[attr-defined]
            export_schema.OUT_DIR = original_out  # type: ignore[attr-defined]
        assert rc == 0

        out = fake_root / "data" / "schema"
        assert (out / "project.schema.json").exists()
        assert (out / "scheme.schema.json").exists()
        assert (out / "eval.schema.json").exists()

        scheme = json.loads((out / "scheme.schema.json").read_text(encoding="utf-8"))
        assert scheme["title"] == "方案参数"
        by_name = {f["name"]: f for f in scheme["fields"]}
        assert by_name["gfa"]["label"] == "总建筑面积"