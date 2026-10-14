"""案例来源边界及导入失败的原子性：只在内存数据库验证。"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest
from app.models import Project, Scheme
from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "data" / "schemes"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

seed = importlib.import_module("scripts.seed_mock")
checker = importlib.import_module("scripts.check_demo_case")


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("params", [{"site_area": -1}, {"density_max": 22}, {"standard_packs": ["ZJ"]}])
def test_invalid_project_does_not_replace_existing(engine, tmp_path, dry_run, params):
    """非法地块不应通过dry-run，也不能删除已有同名项目和方案。"""
    with Session(engine) as session:
        project = Project(name="同名案例", params={"site_area": 20000})
        session.add(project)
        session.flush()
        project_id = project.id
        scheme = Scheme(project_id=project_id, name="保留方案", params={"floors": 18})
        session.add(scheme)
        session.commit()
        scheme_id = scheme.id

    (tmp_path / "project.json").write_text(json.dumps({"_note": "虚构数据", "name": "同名案例", "params": params}), encoding="utf-8")
    (tmp_path / "A.json").write_text(json.dumps({"_note": "演示自拟", "name": "A", "params": {"floors": 18}}), encoding="utf-8")
    argv = ["--mock-dir", str(tmp_path)] + (["--dry-run"] if dry_run else [])
    with pytest.raises(SystemExit, match="ProjectParams"):
        seed.main(argv)
    with Session(engine) as session:
        assert session.get(Project, project_id).params == {"site_area": 20000}
        assert session.get(Scheme, scheme_id).name == "保留方案"
        assert len(session.exec(select(Project)).all()) == 1


@pytest.mark.parametrize("slug", ["qiantang-real", "xiasha-real", "linping-donghu-real"])
def test_strict_real_background_has_no_unverified_planning_limits(slug):
    payload = json.loads((CASES / slug / "project_verified.json").read_text(encoding="utf-8"))
    for field in ("far_max", "density_max", "height_max", "seismic_intensity"):
        assert payload["params"][field] is None, (slug, field)
    _, schemes = checker.load_case(CASES / slug)
    assert len(schemes) == 3
    for scheme in schemes:
        assert "演示自拟" in scheme["_note"]
        assert sum(scheme["params"]["unit_mix"].values()) == scheme["params"]["units"]


@pytest.mark.parametrize("slug", ["demo-qiantang-fictional", "demo-boundaries-fictional"])
def test_whatif_classification_matches_importer(slug):
    """带whatif后缀的副本也需被检查报告正确标识，不能当第六个正式候选。"""
    _, schemes = checker.load_case(CASES / slug)
    official, whatif = seed.discover_layout(CASES / slug)
    assert whatif is not None
    assert sum(bool(scheme.get("_whatif")) for scheme in schemes) == 1
    assert len(official) + 1 == len(schemes)


def test_public_area_breakdown_does_not_turn_into_far_limit():
    """公开建筑规模含非计容部分；记录规模不应产生规划上限。"""
    facts = json.loads((CASES / "xiasha-real" / "project_verified.json").read_text(encoding="utf-8"))["_public_facts"]
    assert facts["above_ground_gfa"] + facts["non_far_stilt_gfa"] + facts["underground_gfa"] == facts["total_gfa"]
