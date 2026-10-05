"""FakeLLM 验收全图、分支、副本与引用重写。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.agents.graph import AgentGraph
from app.agents.llm import FakeLLM, LLMResponse, ToolCall
from app.agents.state import AgentRequest, GraphState
from app.agents.tools import AgentTools
from app.models import Scheme
from sqlalchemy.engine import Engine
from sqlmodel import Session, select


async def run_graph(
    engine: Engine, project: int, request: AgentRequest, llm: FakeLLM | None = None
) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events = []

    async def emit(name: str, data: dict[str, Any]) -> None:
        events.append((name, data))

    output = await AgentGraph(AgentTools(engine, project), llm or FakeLLM(), emit).run(
        GraphState(project_id=project, request=request)
    )
    return output, events


@pytest.mark.asyncio
async def test_new_eval_full_path(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, _ = mock_project
    output, events = await run_graph(engine, project, AgentRequest())
    nodes = [data["node"] for name, data in events if name == "node_start"]
    assert nodes[:4] == ["coordinator", "parser", "compliance", "evaluators"]
    assert set(nodes[4:8]) == {
        f"evaluators_{d}" for d in ("quality", "structure", "construction", "green")
    }
    assert nodes[8:] == ["decision", "reporter", "citation_check"]
    assert all(trace.elapsed_ms >= 0 for trace in output.traces)
    assert not output.unverified_numbers
    for heading in ("结论", "合规问题", "各维度对比", "权衡与稳健性", "修改建议"):
        assert f"## {heading}" in output.report
    assert "C-" in output.report and "source" in output.report


@pytest.mark.asyncio
async def test_whatif_preserves_parent(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, ids = mock_project
    with Session(engine) as session:
        original = session.get(Scheme, ids[2]).model_dump()
    request = AgentRequest(
        intent="whatif", change={"scheme_id": ids[2], "field": "std_floor_repeat", "value": 0.6}
    )
    output, events = await run_graph(engine, project, request)
    with Session(engine) as session:
        assert session.get(Scheme, ids[2]).model_dump() == original
        copies = session.exec(select(Scheme).where(Scheme.is_whatif == True)).all()  # noqa: E712
        assert len(copies) == 1
        assert copies[0].parent_id == ids[2]
        assert copies[0].params["std_floor_repeat"] == 0.6
    assert output.intent == "whatif" and not output.unverified_numbers
    assert "原方案与副本对比" in output.report and "K-01" in output.report
    assert "加入副本" in output.report
    tools = [data["tool"] for name, data in events if name == "tool_call"]
    assert tools.count("update_scheme_param") == 1
    assert tools.count("evaluate") == 2 and tools.count("rank") == 2


@pytest.mark.asyncio
async def test_reweight_skips_eval(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, _ = mock_project
    await run_graph(engine, project, AgentRequest())
    output, events = await run_graph(
        engine, project, AgentRequest(message="权重改成 [0.1,0.2,0.3,0.4]")
    )
    assert output.intent == "reweight" and not output.unverified_numbers
    assert [data["node"] for name, data in events if name == "node_start"] == [
        "coordinator",
        "reweight",
        "reporter",
        "citation_check",
    ]
    assert "evaluate" not in [data["tool"] for name, data in events if name == "tool_call"]
    ranking = next(
        data["result"] for name, data in events if name == "tool_result" and data["tool"] == "rank"
    )
    assert ranking["weights_used"]["weights"] == pytest.approx([0.1, 0.2, 0.3, 0.4])


@pytest.mark.asyncio
async def test_explain_history_and_rule(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    await run_graph(engine, project, AgentRequest())
    llm = FakeLLM()
    output, events = await run_graph(
        engine,
        project,
        AgentRequest(
            message="解释 K-01",
            history=[
                {"role": "user", "content": "之前的问题"},
                {"role": "assistant", "content": "之前的回答"},
            ],
        ),
        llm,
    )
    assert output.intent == "explain" and "规则 K-01" in output.report
    assert any(message.get("content") == "之前的问题" for call in llm.calls for message in call)
    assert "evaluate" not in [data["tool"] for name, data in events if name == "tool_call"]


@pytest.mark.asyncio
async def test_bad_number_rewrites_successfully(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    llm = FakeLLM({"reporter": [LLMResponse(content="伪造得分 998.23")]})
    output, events = await run_graph(engine, project, AgentRequest(), llm)
    assert not output.unverified_numbers and "998.23" not in output.report
    warnings = [data for name, data in events if name == "citation_warning"]
    assert len(warnings) == 1 and warnings[0]["unverified_numbers"][0]["text"] == "998.23"
    assert len([data for name, data in events if name == "token" and data["replace"]]) == 2
    assert any(
        "rewrite_numbers" in message.get("content", "") and "998.23" in message.get("content", "")
        for call in llm.calls
        for message in call
        if message["role"] == "user"
    )


@pytest.mark.asyncio
async def test_continuous_failure_marks_final(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    llm = FakeLLM({"reporter": [LLMResponse(content="得分 998.23")] * 3})
    output, events = await run_graph(engine, project, AgentRequest(), llm)
    assert output.unverified_numbers[0].text == "998.23"
    assert (
        len([data for name, data in events if name == "node_start" and data["node"] == "reporter"])
        == 3
    )
    assert [data for name, data in events if name == "citation_warning"][-1]["exhausted"] is True


@pytest.mark.asyncio
async def test_reporter_function_call_roundtrip(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    llm = FakeLLM(
        {
            "reporter": [
                LLMResponse(
                    tool_calls=[
                        ToolCall(id="rule", name="explain_metric", arguments={"rule_id": "K-01"})
                    ]
                )
            ]
        }
    )
    output, events = await run_graph(engine, project, AgentRequest(), llm)
    assert not output.unverified_numbers
    assert any(name == "tool_call" and data["tool"] == "explain_metric" for name, data in events)
    assert any(
        message["role"] == "tool" and message["tool_call_id"] == "rule"
        for call in llm.calls
        for message in call
    )


@pytest.mark.asyncio
async def test_four_reviews_overlap(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    class BarrierLLM(FakeLLM):
        def __init__(self) -> None:
            super().__init__()
            self.started = 0
            self.ready = asyncio.Event()

        async def chat(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> LLMResponse:
            if messages[0]["content"].startswith("节点：evaluators"):
                self.started += 1
                if self.started == 4:
                    self.ready.set()
                await asyncio.wait_for(self.ready.wait(), 3)
            return await super().chat(messages, tools)

    project, _ = mock_project
    llm = BarrierLLM()
    output, _ = await run_graph(engine, project, AgentRequest(), llm)
    assert llm.started == 4 and not output.unverified_numbers


@pytest.mark.asyncio
async def test_standard_report_uses_requested_weights(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, _ = mock_project
    llm = FakeLLM(
        {
            "coordinator": [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="plan",
                            name="dispatch_intent",
                            arguments={"intent": "new_eval", "role": "contractor"},
                        )
                    ]
                )
            ]
        }
    )
    _, events = await run_graph(engine, project, AgentRequest(intent="new_eval"), llm)
    ranking = next(
        data["result"] for name, data in events if name == "tool_result" and data["tool"] == "rank"
    )
    assert ranking["weights_used"]["source"] == "weights"
    assert ranking["weights_used"]["weights"] == [0.25] * 4
