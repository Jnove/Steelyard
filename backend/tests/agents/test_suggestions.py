from __future__ import annotations

import json

import pytest
from app.agents.llm import FakeLLM, LLMResponse
from app.agents.suggestions import parse_questions, project_context
from app.api import agents
from app.models import Project, Scheme
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select


def test_contextual_suggestions_are_read_only(client: TestClient, engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, ids = mock_project
    client.post(f"/api/projects/{project}/evaluate")
    client.post(f"/api/projects/{project}/rank", json={"role": "government"})
    with Session(engine) as session:
        before = [row.model_dump() for row in session.exec(select(Scheme)).all()]
    response = client.post(f"/api/projects/{project}/suggestions?scheme_id={ids[1]}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "fake" and 1 <= len(body["questions"]) <= 3
    context = project_context(engine, project, ids[1])
    assert context["selected_scheme"]["name"] in " ".join(body["questions"])
    assert context["evaluation_status"] == "current"
    different = client.post(f"/api/projects/{project}/suggestions?scheme_id={ids[0]}").json()
    assert body["questions"] != different["questions"]
    with Session(engine) as session:
        assert [row.model_dump() for row in session.exec(select(Scheme)).all()] == before


def test_stale_and_missing_results_do_not_claim_a_ranking(client: TestClient, engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, ids = mock_project
    path = f"/api/projects/{project}/suggestions"
    assert client.post(path).status_code == 200
    assert project_context(engine, project, None)["evaluation_status"] == "not_evaluated"
    client.post(f"/api/projects/{project}/evaluate")
    with Session(engine) as session:
        scheme = session.get(Scheme, ids[0])
        scheme.params = {**scheme.params, "floor_height": 3.6}
        session.add(scheme)
        session.commit()
    context = project_context(engine, project, None)
    assert context["evaluation_status"] == "stale" and "ranking" not in context
    assert client.post(path).status_code == 200


def test_scope_checked_before_calling_model(client: TestClient, engine: Engine, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ids = mock_project
    with Session(engine) as session:
        other = Project(name="另一个项目")
        session.add(other)
        session.commit()
        other_id = other.id
    def forbidden():
        raise AssertionError("越界请求不应调用模型")
    monkeypatch.setattr(agents, "get_llm", forbidden)
    assert client.post("/api/projects/99999/suggestions").status_code == 404
    assert client.post(f"/api/projects/{other_id}/suggestions?scheme_id={ids[0]}").status_code == 404
    assert client.post(f"/api/projects/{project}/suggestions?scheme_id=0").status_code == 422
    assert client.post(f"/api/projects/{other_id}/chat", json={"message": "解释方案", "scheme_id": ids[0]}).status_code == 404


def test_model_receives_actual_context_and_is_closed(client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    project, ids = mock_project
    class Model(FakeLLM):
        closed = False
        async def aclose(self):
            self.closed = True
    llm = Model({"suggestions": [LLMResponse(content='```json\n{"questions":["当前方案评估前应优先核对哪些输入？"]}\n```')]})
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    response = client.post(f"/api/projects/{project}/suggestions?scheme_id={ids[2]}")
    assert response.status_code == 200, response.text
    assert llm.closed
    context = json.loads(llm.calls[0][-1]["content"])
    assert context["selected_scheme"]["id"] == ids[2]
    assert "selected_scheme" in llm.calls[0][0]["content"]


@pytest.mark.parametrize("content", ["not-json", '{"questions":[]}', '{"questions":["方案得分达到998.23了吗？"]}', '{"questions":["重复的问题是什么？","重复的问题是什么？"]}'])
def test_invalid_model_output_fails_without_fixed_fallback(content: str, client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = mock_project
    monkeypatch.setattr(agents, "get_llm", lambda: FakeLLM({"suggestions": [LLMResponse(content=content)]}))
    response = client.post(f"/api/projects/{project}/suggestions")
    assert response.status_code == 503 and "重试" in response.json()["detail"]


def test_unavailable_key_is_sanitized(client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = mock_project
    def unavailable():
        raise ValueError("private-provider-key")
    monkeypatch.setattr(agents, "get_llm", unavailable)
    response = client.post(f"/api/projects/{project}/suggestions")
    assert response.status_code == 503 and "private-provider-key" not in response.text


def test_parse_questions_enforces_length():
    with pytest.raises(ValueError):
        parse_questions(json.dumps({"questions": ["长" * 121 + "？"]}), {"schemes": []}, "model")


def test_context_change_while_generating_is_rejected(client: TestClient, engine: Engine, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = mock_project
    class ChangingModel(FakeLLM):
        async def chat(self, messages, tools):
            with Session(engine) as session:
                row = session.get(Project, project)
                row.name = "生成期间改名"
                session.add(row)
                session.commit()
            return LLMResponse(content='{"questions":["当前方案有哪些资料需要核实？"]}')
    monkeypatch.setattr(agents, "get_llm", ChangingModel)
    assert client.post(f"/api/projects/{project}/suggestions").status_code == 409
