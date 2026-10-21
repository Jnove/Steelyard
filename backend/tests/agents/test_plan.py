"""Intent previews never execute evaluation or create copies; confirmed plans use SSE."""

from __future__ import annotations

import asyncio
import json

import pytest
from app.agents.llm import FakeLLM, LLMResponse, ToolCall
from app.agents.storage import AgentResultRow, ReportCacheRow
from app.agents.tools import AgentTools
from app.api import agents
from app.custom.models import CustomField
from app.models import EvalResultRow, Project, Scheme
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from .test_api import parse_events


@pytest.fixture(autouse=True)
def fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agents, "get_llm", FakeLLM)


def snapshot(engine: Engine) -> list:
    with Session(engine) as session:
        return [
            [row.model_dump(mode="json") for row in session.exec(select(model)).all()]
            for model in (Project, Scheme, EvalResultRow, AgentResultRow, ReportCacheRow)
        ]


def test_preview_is_read_only_and_confirmed_plan_creates_one_copy(
    client: TestClient, engine: Engine, mock_project: tuple[int, list[int]],
) -> None:
    project, ids = mock_project
    before = snapshot(engine)
    request = {"message": f"方案 {ids[2]} std_floor_repeat 改为 0.6", "role": "contractor"}
    response = client.post(f"/api/projects/{project}/plan", json=request)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["plan"]["intent"] == "whatif"
    assert preview["plan"]["role"] == "contractor"
    assert preview["proposal"]["field_label"] == "标准层重复率"
    assert preview["proposal"]["after"] == 0.6
    assert snapshot(engine) == before
    events = parse_events(client.post(f"/api/projects/{project}/chat", json={
        **request, **preview["plan"], "expected_fingerprint": preview["fingerprint"],
    }).text)
    assert events[-1][0] == "done", events[-1]
    with Session(engine) as session:
        copies = session.exec(select(Scheme).where(Scheme.is_whatif == True)).all()  # noqa: E712
        assert len(copies) == 1 and copies[0].parent_id == ids[2]
        assert copies[0].params["std_floor_repeat"] == 0.6
        assert session.get(Scheme, ids[2]).params == before[1][2]["params"]


@pytest.mark.parametrize(("field", "value"), [
    ("unknown", 1), ("parent_id", 2), ("project_id", 2),
    ("custom.__class__", "evil"), ("std_floor_repeat", 82), ("floor_height", True),
    ("window_wall_ratio", {"南": 1.1}), ("unit_mix", {"一居": -1}),
    ("custom", {"unregistered": 42}),
])
def test_bad_changes_rejected_without_writes(client, engine, mock_project, field, value):
    project, ids = mock_project
    before = snapshot(engine)
    response = client.post(f"/api/projects/{project}/plan", json={
        "intent": "whatif", "change": {"scheme_id": ids[0], "field": field, "value": value},
    })
    assert response.status_code == 422, response.text
    assert snapshot(engine) == before


def test_nested_and_registered_custom_changes(client, engine, mock_project):
    project, ids = mock_project
    with Session(engine) as session:
        session.add(CustomField(key="test_ratio", label="测试比例", kind="ratio"))
        session.commit()
    before = snapshot(engine)
    for field, value in [
        ("window_wall_ratio", {"南": 0.4}), ("test_ratio", 0.4),
        ("custom", {"test_ratio": 0.4}),
    ]:
        response = client.post(f"/api/projects/{project}/plan", json={
            "intent": "whatif", "change": {"scheme_id": ids[0], "field": field, "value": value},
        })
        assert response.status_code == 200, response.text
        assert response.json()["proposal"]["after"] == value
    assert snapshot(engine) == before


def test_foreign_scheme_rejected_before_model(client, engine, mock_project, monkeypatch):
    project, ids = mock_project
    with Session(engine) as session:
        other = Project(name="另一个项目")
        session.add(other)
        session.commit()
        other_id = other.id
    for data in [
        {"message": "解释", "scheme_id": ids[0]},
        {"intent": "whatif", "change": {"scheme_id": ids[0], "field": "floor_height", "value": 3.0}},
    ]:
        before = snapshot(engine)
        response = client.post(f"/api/projects/{other_id}/plan", json=data)
        assert response.status_code == 404
        assert snapshot(engine) == before
    assert client.post("/api/projects/999999/plan", json={}).status_code == 404


@pytest.mark.parametrize("data", [
    {"message": "把方案调整一下"},
    {"intent": "reweight", "weights": [1, -1, 1, 1]},
    {"intent": "reweight", "weights": [0, 0, 0, 0]},
    {"intent": "reweight", "role": "unknown"},
])
def test_incomplete_or_invalid_plan_is_recoverable(client, engine, mock_project, data):
    project, _ = mock_project
    if "message" in data:
        data["message"] = "修改方案"
    before = snapshot(engine)
    response = client.post(f"/api/projects/{project}/plan", json=data)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert snapshot(engine) == before


def test_plain_explanation_carries_selection_context(client, engine, mock_project, monkeypatch):
    project, ids = mock_project
    llm = FakeLLM()
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    before = snapshot(engine)
    result = client.post(f"/api/projects/{project}/plan", json={
        "message": "解释当前方案", "scheme_id": ids[0], "weights": [0.1, 0.2, 0.3, 0.4],
    })
    assert result.status_code == 200, result.text
    assert result.json()["proposal"] is None
    assert result.json()["plan"]["weights"] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert snapshot(engine) == before
    context = json.loads(llm.calls[0][-1]["content"])
    assert context["request"]["scheme_id"] == ids[0]
    assert context["project_context"]["schemes"][0]["scheme_id"] == ids[0]
    assert context["project_context"]["fields"]["std_floor_repeat"]["label"] == "标准层重复率"


def test_model_error_and_timeout_close_client(client, mock_project, monkeypatch):
    project, _ = mock_project

    class BrokenLLM(FakeLLM):
        closed = False
        async def chat(self, messages, tools):
            raise RuntimeError("secret-not-for-user")
        async def aclose(self):
            self.closed = True

    llm = BrokenLLM()
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    response = client.post(f"/api/projects/{project}/plan", json={"message": "解释"})
    assert response.status_code == 503 and "secret-not-for-user" not in response.text
    assert llm.closed

    class SlowLLM(BrokenLLM):
        async def chat(self, messages, tools):
            await asyncio.Event().wait()

    llm = SlowLLM()
    monkeypatch.setattr(agents, "PLAN_TIMEOUT_SECONDS", 0.01)
    response = client.post(f"/api/projects/{project}/plan", json={"message": "解释"})
    assert response.status_code == 503 and "超时" in response.text
    assert llm.closed


def test_hallucinated_change_is_validated(client, mock_project, monkeypatch):
    project, ids = mock_project
    llm = FakeLLM({"coordinator": [LLMResponse(tool_calls=[ToolCall(
        id="plan", name="dispatch_intent",
        arguments={"intent": "whatif", "change": {"scheme_id": ids[0], "field": "is_whatif", "value": True}},
    )])]})
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    response = client.post(f"/api/projects/{project}/plan", json={"message": "修改方案"})
    assert response.status_code == 422


@pytest.mark.parametrize(("request_context", "planned"), [
    ({"role": "government"}, {"role": "resident"}),
    ({"role": "government"}, {"weights": [0.1, 0.2, 0.3, 0.4]}),
    ({"weights": [0.25] * 4}, {"role": "contractor"}),
])
def test_natural_reweight_replaces_current_view(client, mock_project, monkeypatch, request_context, planned):
    project, _ = mock_project
    llm = FakeLLM({"coordinator": [LLMResponse(tool_calls=[ToolCall(
        id="plan", name="dispatch_intent", arguments={"intent": "reweight", **planned},
    )])]})
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    response = client.post(f"/api/projects/{project}/plan", json={
        "message": "切换决策偏好", **request_context,
    })
    assert response.status_code == 200, response.text
    assert response.json()["plan"]["role"] == planned.get("role")
    assert response.json()["plan"]["weights"] == (pytest.approx(planned["weights"]) if "weights" in planned else None)
    assert response.json()["proposal"] is None


def test_plan_normalizes_relative_weights(client, mock_project):
    project, _ = mock_project
    response = client.post(f"/api/projects/{project}/plan", json={"intent": "reweight", "weights": [1, 2, 3, 4]})
    assert response.status_code == 200
    assert response.json()["plan"]["weights"] == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_stale_confirmation_rejected_before_any_write(client, engine, mock_project):
    project, ids = mock_project
    request = {"intent": "whatif", "change": {"scheme_id": ids[0], "field": "floor_height", "value": 3.5}}
    preview = client.post(f"/api/projects/{project}/plan", json=request).json()
    with Session(engine) as session:
        parent = session.get(Scheme, ids[0])
        parent.params = {**parent.params, "floor_height": 3.2}
        session.add(parent)
        session.commit()
    before = snapshot(engine)
    response = client.post(f"/api/projects/{project}/chat", json={**request, "expected_fingerprint": preview["fingerprint"]})
    assert response.status_code == 409 and "重新预览" in response.text
    assert snapshot(engine) == before


def test_change_during_baseline_cannot_create_copy(client, engine, mock_project, monkeypatch):
    project, ids = mock_project
    request = {"intent": "whatif", "change": {"scheme_id": ids[0], "field": "floor_height", "value": 3.5}}
    preview = client.post(f"/api/projects/{project}/plan", json=request).json()
    rank = AgentTools.rank

    def rank_then_edit(self, *args, **kwargs):
        result = rank(self, *args, **kwargs)
        with Session(engine) as session:
            parent = session.get(Scheme, ids[0])
            parent.params = {**parent.params, "floor_height": 3.2}
            session.add(parent)
            session.commit()
        return result

    monkeypatch.setattr(AgentTools, "rank", rank_then_edit)
    response = client.post(f"/api/projects/{project}/chat", json={**request, "expected_fingerprint": preview["fingerprint"]})
    events = parse_events(response.text)
    assert events[-1][0] == "error" and "重新预览" in events[-1][1]["message"]
    assert events[-1][1]["status"] == 409
    with Session(engine) as session:
        assert not session.exec(select(Scheme).where(Scheme.is_whatif == True)).all()  # noqa: E712
