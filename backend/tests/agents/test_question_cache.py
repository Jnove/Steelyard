from __future__ import annotations

import json

from app.agents import question_cache
from app.agents.llm import FakeLLM
from app.agents.storage import ReportCacheRow
from app.api import agents
from app.models import Project
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select


def counted_model(monkeypatch):
    models = []
    def create():
        model = FakeLLM()
        models.append(model)
        return model
    monkeypatch.setattr(agents, "get_llm", create)
    return models


def test_same_state_uses_cache_refresh_and_input_changes_generate_again(client, engine, mock_project, monkeypatch):
    project, ids = mock_project
    models = counted_model(monkeypatch)
    path = f"/api/projects/{project}/suggestions?scheme_id={ids[0]}"
    first = client.post(path)
    assert first.status_code == 200
    assert client.post(path).json() == first.json() and len(models) == 1
    assert client.post(path + "&refresh=true").status_code == 200 and len(models) == 2
    with Session(engine) as session:
        row = session.get(Project, project)
        row.name = "输入已改变"
        session.add(row)
        session.commit()
    assert client.post(path).status_code == 200 and len(models) == 3


def test_rank_settings_model_and_credentials_are_part_of_cache_identity(client, engine, mock_project, monkeypatch):
    project, _ = mock_project
    client.post(f"/api/projects/{project}/evaluate")
    client.post(f"/api/projects/{project}/rank", json={"role": "government"})
    models = counted_model(monkeypatch)
    path = f"/api/projects/{project}/suggestions"
    assert client.post(path).status_code == 200
    client.post(f"/api/projects/{project}/rank", json={"role": "contractor"})
    assert client.post(path).status_code == 200 and len(models) == 2
    settings = agents.get_settings().model_copy(update={"llm_model": "another-model", "llm_api_key": "private-test-credential"})
    monkeypatch.setattr(agents, "get_settings", lambda: settings)
    assert client.post(path).status_code == 200 and len(models) == 3
    with Session(engine) as session:
        rows = session.exec(select(ReportCacheRow)).all()
        assert all("private-test-credential" not in row.key + json.dumps(row.output) for row in rows)


def test_expired_suggestions_regenerate_instead_of_becoming_stale(client, mock_project, monkeypatch):
    project, _ = mock_project
    now = [1000.0]
    monkeypatch.setattr(question_cache, "time", lambda: now[0])
    models = counted_model(monkeypatch)
    path = f"/api/projects/{project}/suggestions"
    assert client.post(path).status_code == 200
    now[0] += question_cache.TTL_SECONDS + 1
    assert client.post(path).status_code == 200 and len(models) == 2
    assert client.post(path).status_code == 200 and len(models) == 2


def test_cache_storage_failure_does_not_fail_successful_model_output(client, mock_project, monkeypatch, caplog):
    project, _ = mock_project
    counted_model(monkeypatch)
    def unavailable(*args):
        raise SQLAlchemyError("private-database-details")
    monkeypatch.setattr(question_cache, "read", unavailable)
    monkeypatch.setattr(question_cache, "write", unavailable)
    response = client.post(f"/api/projects/{project}/suggestions")
    assert response.status_code == 200 and "缓存" in caplog.text
    assert "private-database-details" not in caplog.text + response.text
