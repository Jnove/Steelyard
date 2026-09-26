"""scripts/make_template.py / import_schemes.py / export_schemes.py 行为测试。

脚本运行不依赖 FastAPI lifespan；测试用临时 DB 覆盖全局 engine。
"""

from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

import pytest
from sqlalchemy import StaticPool
from sqlmodel import Session, SQLModel, create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _reload_with_engine(engine):
    """把脚本的全局 engine 换成测试用的内存 SQLite，并 import_or_reload。"""
    from app.db import override_engine_for_testing

    override_engine_for_testing(engine)
    # 重新 import 脚本，确保它们用最新的引擎
    for name in ("scripts.make_template", "scripts.import_schemes", "scripts.export_schemes"):
        if name in sys.modules:
            importlib.reload(sys.modules[name])


@pytest.fixture
def scripts_engine(monkeypatch):
    """临时 SQLite + 重定向 CWD 到 tmp，让脚本写到临时目录。"""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models.orm import EvalResultRow, Project, Scheme  # noqa: F401

    SQLModel.metadata.create_all(eng)
    _reload_with_engine(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


class TestMakeTemplateScript:
    def test_writes_to_data_schemes_default(self, scripts_engine, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        # 直接调 main()，传空 list 避免 argparse 误读 pytest argv
        from scripts import make_template

        rc = make_template.main([])
        assert rc == 0
        out = tmp_path / "data" / "schemes" / "方案录入模板.xlsx"
        assert out.exists()

    def test_out_argument_overrides_default(
        self, scripts_engine, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import make_template

        custom = tmp_path / "my.xlsx"
        rc = make_template.main(["--out", str(custom)])
        assert rc == 0
        assert custom.exists()


class TestImportSchemesScript:
    def _add_project(self, scripts_engine) -> int:
        from app.models import Project

        with Session(scripts_engine) as session:
            p = Project(name="脚本测试", params={"site_area": 18000})
            session.add(p)
            session.commit()
            session.refresh(p)
            return p.id or 0

    def _good_template_bytes(self) -> bytes:
        """构造一个含 1 个有效方案的 xlsx。"""
        import tempfile

        from app.excel import write_template
        from openpyxl import load_workbook

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp = Path(f.name)
        try:
            write_template(tmp)
            wb = load_workbook(tmp)
            ws = wb["方案参数"]
            sname_col = next(c.column for c in ws[1] if c.value == "__name__")
            for r in range(2, ws.max_row + 1):
                name = ws.cell(row=r, column=sname_col).value
                if name == "gfa":
                    ws.cell(row=r, column=3, value=15000)
                elif name == "structure_type":
                    ws.cell(row=r, column=3, value="剪力墙")
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()
        finally:
            tmp.unlink(missing_ok=True)

    def _bad_template_bytes(self) -> bytes:
        import tempfile

        from app.excel import write_template
        from openpyxl import load_workbook

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp = Path(f.name)
        try:
            write_template(tmp)
            wb = load_workbook(tmp)
            ws = wb["方案参数"]
            sname_col = next(c.column for c in ws[1] if c.value == "__name__")
            for r in range(2, ws.max_row + 1):
                if ws.cell(row=r, column=sname_col).value == "floor_height":
                    ws.cell(row=r, column=3, value="三米")
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()
        finally:
            tmp.unlink(missing_ok=True)

    def test_happy_path(self, scripts_engine, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import import_schemes

        pid = self._add_project(scripts_engine)
        xlsx = tmp_path / "good.xlsx"
        xlsx.write_bytes(self._good_template_bytes())

        rc = import_schemes.main([str(pid), str(xlsx)])
        assert rc == 0

        from app.models import Scheme

        with Session(scripts_engine) as session:
            rows = session.exec(
                __import__("sqlmodel").select(Scheme).where(Scheme.project_id == pid)
            ).all()
            assert len(rows) == 1
            assert rows[0].name == "方案A"
            assert rows[0].params["gfa"] == 15000

    def test_default_rejects_on_error(
        self, scripts_engine, tmp_path, monkeypatch, capsys
    ) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import import_schemes

        pid = self._add_project(scripts_engine)
        xlsx = tmp_path / "bad.xlsx"
        xlsx.write_bytes(self._bad_template_bytes())

        rc = import_schemes.main([str(pid), str(xlsx)])
        assert rc == 1  # 拒绝

        from app.models import Scheme

        with Session(scripts_engine) as session:
            rows = session.exec(
                __import__("sqlmodel").select(Scheme).where(Scheme.project_id == pid)
            ).all()
            assert len(rows) == 0

    def test_missing_file(self, scripts_engine, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import import_schemes

        rc = import_schemes.main(["1", str(tmp_path / "missing.xlsx")])
        assert rc == 2


class TestExportSchemesScript:
    def _add_project_with_schemes(self, scripts_engine) -> int:
        from app.models import Project, Scheme

        with Session(scripts_engine) as session:
            p = Project(name="导出测试", params={"site_area": 18000})
            session.add(p)
            session.commit()
            session.refresh(p)
            pid = p.id or 0
            session.add(
                Scheme(
                    project_id=pid,
                    name="方案 A",
                    params={"gfa": 15000, "structure_type": "剪力墙"},
                )
            )
            session.commit()
            return pid

    def test_writes_export_file(self, scripts_engine, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import export_schemes

        pid = self._add_project_with_schemes(scripts_engine)
        out = tmp_path / "out.xlsx"
        rc = export_schemes.main([str(pid), "--out", str(out)])
        assert rc == 0
        assert out.exists()

        # 用 parse_workbook 反向校验
        from app.excel import parse_workbook

        result = parse_workbook(out)
        assert result.errors == []
        assert result.project_params["site_area"] == 18000
        assert len(result.schemes) == 1
        assert result.schemes[0]["params"]["gfa"] == 15000

    def test_project_not_found(self, scripts_engine, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts import export_schemes

        rc = export_schemes.main(["9999"])
        assert rc == 2