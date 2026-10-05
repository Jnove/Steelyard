"""T8 使用 T6 明示虚构数据，不使用真实模型与真实工程数据。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.models import Project, Scheme
from sqlalchemy.engine import Engine
from sqlmodel import Session


@pytest.fixture
def mock_project(engine: Engine) -> tuple[int, list[int]]:
    root = Path(__file__).resolve().parents[3] / "data" / "schemes" / "mock"
    project_data = json.loads((root / "project.json").read_text(encoding="utf-8"))
    with Session(engine) as session:
        project = Project(name=project_data["name"], params=project_data["params"])
        session.add(project)
        session.flush()
        assert project.id is not None
        ids = []
        for name in (
            "A_高品质.json",
            "B_不合规.json",
            "C_MiC高标准化.json",
            "D_均衡.json",
            "E_被支配.json",
        ):
            data = json.loads((root / name).read_text(encoding="utf-8"))
            scheme = Scheme(project_id=project.id, name=data["name"], params=data["params"])
            session.add(scheme)
            session.flush()
            assert scheme.id is not None
            ids.append(scheme.id)
        session.commit()
        return project.id, ids
