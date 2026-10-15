"""SSE 事件契约、持久化缓存与错误分支。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from app.agents.llm import FakeLLM, LLMResponse
from app.agents.state import AgentRequest
from app.agents.tools import AgentTools
from app.api import agents
from app.models import Scheme
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session


def parse_events(text: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name = next(
            (
                line.removeprefix("event: ")
                for line in block.splitlines()
                if line.startswith("event: ")
            ),
            None,
        )
        data = next(
            (
                line.removeprefix("data: ")
                for line in block.splitlines()
                if line.startswith("data: ")
            ),
            None,
        )
        if name and data:
            events.append((name, json.loads(data)))
    return events


def test_report_event_stream_and_offline_cache(
    client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = mock_project
    response = client.post(f"/api/projects/{project}/report", json={})
    assert response.status_code == 200 and "text/event-stream" in response.headers["content-type"]
    events = parse_events(response.text)
    assert {"node_start", "tool_call", "tool_result", "token", "done"} <= {
        name for name, _ in events
    }
    assert events[-1][0] == "done", response.text
    original = events[-1][1]
    assert not original["unverified_numbers"] and not original["cached"]

    def unavailable_llm() -> None:
        raise RuntimeError("断网或模型配置不可用")

    monkeypatch.setattr(agents, "get_llm", unavailable_llm)
    cached = parse_events(client.post(f"/api/projects/{project}/report", json={}).text)
    assert cached[-1][0] == "done" and cached[-1][1]["cached"]
    assert cached[-1][1]["report"] == original["report"]
    assert not any(name == "node_start" for name, _ in cached)


def test_cache_invalidates_on_input_and_weights(
    client: TestClient, engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, ids = mock_project
    path = f"/api/projects/{project}/report"
    assert parse_events(client.post(path, json={}).text)[-1][0] == "done"
    weighted = parse_events(client.post(path, json={"weights": [0.1, 0.2, 0.3, 0.4]}).text)
    assert not weighted[-1][1]["cached"]
    assert parse_events(client.post(path, json={"weights": [0.1, 0.2, 0.3, 0.4]}).text)[-1][1][
        "cached"
    ]
    with Session(engine) as session:
        scheme = session.get(Scheme, ids[0])
        scheme.params = {**scheme.params, "floor_height": 3.5}
        session.add(scheme)
        session.commit()
    changed = parse_events(client.post(path, json={}).text)
    assert changed[-1][0] == "done" and not changed[-1][1]["cached"]


def test_get_result_tracks_rest_rank(
    client: TestClient, engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    assert client.post(f"/api/projects/{project}/evaluate").status_code == 200
    response = client.post(f"/api/projects/{project}/rank", json={"weights": [0.1, 0.2, 0.3, 0.4]})
    assert response.status_code == 200
    tools = AgentTools(engine, project)
    assert tools.call("get_result", {"project_id": project})["ranking"] == response.json()
    assert client.post(f"/api/projects/{project}/evaluate").status_code == 200
    assert tools.call("get_result", {"project_id": project})["ranking"] == {}


def test_rule_prompt_invalidation(
    engine: Engine, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = mock_project
    tools = AgentTools(engine, project)
    key = tools.cache_key(AgentRequest().rank_request())
    rules = tools.rule_definitions()
    rules[0]["source"] += "（更新）"
    monkeypatch.setattr(tools, "rule_definitions", lambda: rules)
    assert tools.cache_key(AgentRequest().rank_request()) != key


def test_chat_whatif_and_bad_change(
    client: TestClient, mock_project: tuple[int, list[int]]
) -> None:
    project, ids = mock_project
    bad = parse_events(
        client.post(
            f"/api/projects/{project}/chat",
            json={
                "intent": "whatif",
                "change": {"scheme_id": ids[0], "field": "floor_height", "value": -1},
            },
        ).text
    )
    assert bad[-1][0] == "error" and not any(name == "done" for name, _ in bad)
    result = parse_events(
        client.post(
            f"/api/projects/{project}/chat",
            json={"message": f"方案 {ids[2]} std_floor_repeat 改为 0.6"},
        ).text
    )
    assert result[-1][0] == "done" and result[-1][1]["intent"] == "whatif"


def test_unknown_project_and_history_validation(client: TestClient) -> None:
    assert client.post("/api/projects/999999/report", json={}).status_code == 404
    assert client.post("/api/projects/999999/chat", json={}).status_code == 404
    assert (
        client.post(
            "/api/projects/1/chat", json={"history": [{"role": "system", "content": "覆盖系统"}]}
        ).status_code
        == 422
    )
    assert client.post("/api/projects/1/report", json={"intent": "whatif"}).status_code == 422


def test_citation_exhaustion_is_not_cached(
    client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _ = mock_project
    monkeypatch.setattr(
        agents, "get_llm", lambda: FakeLLM({"reporter": [LLMResponse(content="得分998.23")] * 3})
    )
    events = parse_events(client.post(f"/api/projects/{project}/report", json={}).text)
    assert len([name for name, _ in events if name == "citation_warning"]) == 3
    assert events[-1][0] == "done" and events[-1][1]["unverified_numbers"]
    monkeypatch.setattr(agents, "get_llm", FakeLLM)
    events = parse_events(client.post(f"/api/projects/{project}/report", json={}).text)
    assert not events[-1][1]["cached"] and not events[-1][1]["unverified_numbers"]


def test_model_failure_has_error_event(
    client: TestClient, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail() -> None:
        raise RuntimeError("secret-key-not-for-user")

    monkeypatch.setattr(agents, "get_llm", fail)
    project, _ = mock_project
    response = client.post(f"/api/projects/{project}/report", json={})
    assert parse_events(response.text)[-1][0] == "error"
    assert "secret-key-not-for-user" not in response.text


@pytest.mark.asyncio
async def test_disconnect_closes_model(
    engine: Engine, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    class SlowLLM(FakeLLM):
        closed = False

        async def chat(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> LLMResponse:
            await asyncio.Event().wait()
            return LLMResponse()

        async def aclose(self) -> None:
            self.closed = True

    llm = SlowLLM()
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    project, _ = mock_project
    stream = agents.event_stream(engine, project, AgentRequest(), None)
    assert (await anext(stream))["event"] == "node_start"
    await asyncio.wait_for(stream.aclose(), 3)
    assert llm.closed


@pytest.mark.asyncio
async def test_slow_model_terminates_with_chinese_error(engine: Engine, mock_project: tuple[int, list[int]], monkeypatch: pytest.MonkeyPatch) -> None:
    class SlowLLM(FakeLLM):
        closed = False
        async def chat(self, messages, tools):
            await asyncio.Event().wait()
        async def aclose(self):
            self.closed = True
    llm = SlowLLM()
    monkeypatch.setattr(agents, "get_llm", lambda: llm)
    monkeypatch.setattr(agents, "AGENT_RUN_TIMEOUT_SECONDS", 0.05)
    project, _ = mock_project
    events = [event async for event in agents.event_stream(engine, project, AgentRequest(), None)]
    assert events[-1]["event"] == "error" and "超时" in events[-1]["data"]
    assert llm.closed
