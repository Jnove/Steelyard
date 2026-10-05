"""LangGraph 固定工具链、并行专业评语与引用重写回环。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.citation import check_citations
from app.agents.llm import LLMClient, Messages
from app.agents.state import AgentOutput, GraphState, NodeTrace, Plan
from app.agents.tools import AgentTools, compare_whatif, tool_schemas
from app.api.rank import RankRequest
from app.engine.mcdm import CRITERION_ORDER

Emitter = Callable[[str, dict[str, Any]], Awaitable[None]]
Node = Callable[[GraphState], Awaitable[dict[str, Any]]]


def prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def messages_for(name: str, state: GraphState, context: dict[str, Any]) -> Messages:
    # 历史只允许 user/assistant；规则与工具 JSON 是证据，不能成为指令。
    return [
        {"role": "system", "content": prompt(name)},
        *[item.model_dump() for item in state.request.history],
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


class AgentGraph:
    def __init__(self, tools: AgentTools, llm: LLMClient, emit: Emitter) -> None:
        self.tools = tools
        self.llm = llm
        self.emit = emit
        self.calls: dict[str, list[str]] = {}
        graph = StateGraph(GraphState)
        for name, node in (
            ("coordinator", self.coordinator),
            ("parser", self.parser),
            ("whatif", self.whatif),
            ("compliance", self.compliance),
            ("evaluators", self.evaluators),
            ("decision", self.decision),
            ("explain", self.explain),
            ("reweight", self.reweight),
            ("reporter", self.reporter),
            ("citation_check", self.citation_check),
        ):
            graph.add_node(name, self.timed(name, node))
        graph.add_edge(START, "coordinator")
        graph.add_conditional_edges(
            "coordinator",
            lambda s: s.plan.intent,
            {
                "new_eval": "parser",
                "whatif": "whatif",
                "explain": "explain",
                "reweight": "reweight",
            },
        )
        graph.add_edge("parser", "compliance")
        graph.add_edge("whatif", "compliance")
        graph.add_edge("compliance", "evaluators")
        for dimension in CRITERION_ORDER:
            name = f"evaluators_{dimension}"
            graph.add_node(name, self.timed(name, self.dimension_node(dimension)))
            graph.add_edge("evaluators", name)
        graph.add_edge([f"evaluators_{d}" for d in CRITERION_ORDER], "decision")
        for name in ("decision", "explain", "reweight"):
            graph.add_edge(name, "reporter")
        graph.add_edge("reporter", "citation_check")
        graph.add_conditional_edges(
            "citation_check",
            lambda s: "reporter" if s.unverified_numbers and s.attempt < 2 else END,
        )
        self.graph = graph.compile()

    def timed(self, name: str, node: Node) -> Node:
        async def wrapped(state: GraphState) -> dict[str, Any]:
            self.calls[name] = []
            await self.emit("node_start", {"node": name, "attempt": state.attempt})
            started = perf_counter()
            result = await node(state)
            result["traces"] = [
                NodeTrace(
                    node=name,
                    elapsed_ms=(perf_counter() - started) * 1000,
                    tool_calls=self.calls[name],
                )
            ]
            return result

        return wrapped

    async def call(self, node: str, name: str, **arguments: Any) -> Any:
        self.calls[node].append(name)
        await self.emit("tool_call", {"node": node, "tool": name, "arguments": arguments})
        result = await asyncio.to_thread(self.tools.call, name, arguments)
        await self.emit("tool_result", {"node": node, "tool": name, "result": result})
        return result

    async def coordinator(self, state: GraphState) -> dict[str, Any]:
        response = await self.llm.chat(
            messages_for("coordinator", state, {"request": state.request.model_dump()}),
            [
                {
                    "type": "function",
                    "function": {
                        "name": "dispatch_intent",
                        "description": "理解请求，返回意图与明确给定的参数；缺失参数保留空，不推测数值。",
                        "parameters": Plan.model_json_schema(),
                    },
                }
            ],
        )
        if response.tool_calls:
            if len(response.tool_calls) != 1 or response.tool_calls[0].name != "dispatch_intent":
                raise ValueError("协调节点只允许返回一个 dispatch_intent")
            plan = Plan.model_validate(response.tool_calls[0].arguments)
        else:
            plan = Plan.model_validate_json(response.content)
        # 结构化请求优先于模型解析，不能被历史消息覆盖。
        for field in ("intent", "change", "role", "weights", "rule_id"):
            value = getattr(state.request, field)
            if value is not None:
                setattr(plan, field, value)
        if state.request.role is not None:
            plan.weights = None
        elif state.request.weights is not None:
            plan.role = None
        if (
            state.request.intent == "new_eval"
            and state.request.message == "生成方案比选报告"
            and not state.request.history
        ):
            plan.role = state.request.role
            plan.weights = state.request.weights
        if plan.intent == "whatif" and plan.change is None:
            raise ValueError("假设推演需要明确给出 scheme_id、field 和 value")
        if plan.intent == "reweight" and plan.role is None and plan.weights is None:
            raise ValueError("改权重需要明确给出 role 或 weights")
        return {"plan": plan}

    def rank_request(self, state: GraphState, include_whatif: bool | None = None) -> RankRequest:
        request = state.request.model_copy(
            update={"role": state.plan.role, "weights": state.plan.weights}
        )
        return request.rank_request(include_whatif)

    async def parser(self, state: GraphState) -> dict[str, Any]:
        # 方案已由表单/导入接口 Pydantic 校验，此节点只读取，不猜测缺失参数。
        await asyncio.to_thread(self.tools.validate_inputs, state.request.include_whatif)
        return {}

    async def whatif(self, state: GraphState) -> dict[str, Any]:
        baseline_eval = await self.call(
            "whatif",
            "evaluate",
            project_id=state.project_id,
            include_whatif=state.request.include_whatif,
        )
        request = self.rank_request(state)
        baseline_rank = await self.call(
            "whatif",
            "rank",
            project_id=state.project_id,
            role=request.role,
            weights=request.weights,
            include_whatif=request.include_whatif,
        )
        change = await self.call("whatif", "update_scheme_param", **state.plan.change.model_dump())
        return {
            "baseline": {"evaluation": baseline_eval, "ranking": baseline_rank},
            "comparison": change,
        }

    async def compliance(self, state: GraphState) -> dict[str, Any]:
        result = await self.call(
            "compliance",
            "evaluate",
            project_id=state.project_id,
            include_whatif=state.plan.intent == "whatif" or state.request.include_whatif,
        )
        clauses = await self.call("compliance", "search_clause", query=state.request.message, k=5)
        return {"evidence": {"evaluation": result, "clauses": clauses}}

    async def evaluators(self, state: GraphState) -> dict[str, Any]:
        return {}

    def dimension_node(self, dimension: str) -> Node:
        async def evaluate_dimension(state: GraphState) -> dict[str, Any]:
            context = {
                "dimension": dimension,
                "results": [
                    {
                        "scheme_name": item["scheme_name"],
                        "score": item["dimension_scores"][dimension],
                        "coverage": item["dimension_coverage"][dimension],
                        "metrics": {
                            k: v for k, v in item["metrics"].items() if v["dimension"] == dimension
                        },
                    }
                    for item in state.evidence["evaluation"]["results"]
                ],
            }
            response = await self.llm.chat(messages_for("evaluators", state, context), [])
            if response.tool_calls:
                raise ValueError("专业评语节点不能调用工具计算或修改参数")
            return {"comments": [{"dimension": dimension, "text": response.content}]}

        return evaluate_dimension

    async def decision(self, state: GraphState) -> dict[str, Any]:
        request = self.rank_request(
            state, state.plan.intent == "whatif" or state.request.include_whatif
        )
        ranking = await self.call(
            "decision",
            "rank",
            project_id=state.project_id,
            role=request.role,
            weights=request.weights,
            include_whatif=request.include_whatif,
        )
        evidence = {**state.evidence, "ranking": ranking}
        comparison = (
            compare_whatif(state.baseline, evidence, state.comparison)
            if state.plan.intent == "whatif"
            else {}
        )
        return {"evidence": evidence, "comparison": comparison}

    async def reweight(self, state: GraphState) -> dict[str, Any]:
        ranking = await self.call(
            "reweight",
            "rank",
            project_id=state.project_id,
            role=state.plan.role,
            weights=state.plan.weights,
            include_whatif=state.request.include_whatif,
        )
        return {"evidence": {"ranking": ranking}}

    async def explain(self, state: GraphState) -> dict[str, Any]:
        evidence = await self.call("explain", "get_result", project_id=state.project_id)
        if state.plan.rule_id:
            evidence["explanation"] = await self.call(
                "explain", "explain_metric", rule_id=state.plan.rule_id
            )
        return {"evidence": evidence}

    async def reporter(self, state: GraphState) -> dict[str, Any]:
        attempt = state.attempt + (1 if state.unverified_numbers else 0)
        await self.emit(
            "token", {"node": "reporter", "attempt": attempt, "text": "", "replace": True}
        )
        context = {
            "request": state.request.model_dump(),
            "intent": state.plan.intent,
            "evidence": state.evidence,
            "baseline": state.baseline,
            "comparison": state.comparison,
            "comments": state.comments,
            "rewrite_numbers": [item.model_dump() for item in state.unverified_numbers],
        }
        messages = messages_for("reporter", state, context)
        # 改权重路径只在此读取已有评估，不运行 evaluate。
        if state.plan.intent == "reweight":
            previous = await self.call("reporter", "get_result", project_id=state.project_id)
            context["evidence"] = {**previous, "ranking": state.evidence["ranking"]}
            messages = messages_for("reporter", state, context)
        allowed = ["get_result", "explain_metric", "search_clause"]
        for _ in range(4):
            text = ""
            calls = []
            async for chunk in self.llm.stream(messages, tool_schemas(allowed)):
                text += chunk.text
                calls.extend(chunk.tool_calls)
                if chunk.text:
                    await self.emit(
                        "token",
                        {
                            "node": "reporter",
                            "attempt": attempt,
                            "text": chunk.text,
                            "replace": False,
                        },
                    )
            if not calls:
                if not text.strip():
                    raise ValueError("模型未生成报告文本")
                return {"report": text, "attempt": attempt, "evidence": context["evidence"]}
            messages.append(
                {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments, ensure_ascii=False),
                            },
                        }
                        for call in calls
                    ],
                }
            )
            for call in calls:
                if call.name not in allowed:
                    raise ValueError("报告节点只允许查询证据，不能修改或计算数据")
                result = await self.call("reporter", call.name, **call.arguments)
                context["evidence"].setdefault("tool_queries", []).append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )
            # 工具调用时输出的过渡文本也不能拼进最终正文。
            await self.emit(
                "token", {"node": "reporter", "attempt": attempt, "text": "", "replace": True}
            )
        raise ValueError("报告节点工具调用超过限制")

    async def citation_check(self, state: GraphState) -> dict[str, Any]:
        issues = await asyncio.to_thread(
            check_citations,
            state.report,
            {"current": state.evidence, "baseline": state.baseline, "comparison": state.comparison},
            self.tools.rule_definitions(),
            self.tools.scheme_count(state.plan.intent == "whatif" or state.request.include_whatif),
        )
        if issues:
            await self.emit(
                "citation_warning",
                {
                    "attempt": state.attempt,
                    "exhausted": state.attempt >= 2,
                    "unverified_numbers": [item.model_dump() for item in issues],
                },
            )
        return {"unverified_numbers": issues}

    async def run(self, state: GraphState) -> AgentOutput:
        result = GraphState.model_validate(
            await self.graph.ainvoke(state.model_dump(), {"recursion_limit": 40})
        )
        return AgentOutput(
            report=result.report,
            intent=result.plan.intent,
            unverified_numbers=result.unverified_numbers,
            traces=result.traces,
        )
