"""LangGraph 固定工具链、并行专业评语与引用重写回环。"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.citation import check_citations
from app.agents.llm import LLMClient, Messages
from app.agents.presentation import compact_evidence
from app.agents.readable import detailed_request, humanize, reader_evidence
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
    history = []
    remaining = 6000
    for item in reversed(state.request.history[-8:]):
        content = item.content[:min(1600, remaining)]
        if content:
            history.append({"role": item.role, "content": content})
            remaining -= len(content)
        if not remaining:
            break
    return [
        {"role": "system", "content": prompt(name)},
        *reversed(history),
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, separators=(",", ":"))},
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
        if state.request.intent is not None:
            plan = Plan(**{field: getattr(state.request, field) for field in (
                "intent", "change", "role", "weights", "rule_id"
            )})
        else:
            plan = await self.parse_intent(state)
        return {"plan": self.validate_plan(state, plan)}

    async def parse_intent(self, state: GraphState) -> Plan:
        response = await self.llm.chat(
            messages_for("coordinator", state, {"request": state.request.model_dump(exclude={"history"})}),
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
        if not response.tool_calls and not response.content.strip():
            raise ValueError("模型未返回有效的意图计划，请重试或使用报告、建议问题及假设推演入口")
        if response.tool_calls:
            if len(response.tool_calls) != 1 or response.tool_calls[0].name != "dispatch_intent":
                raise ValueError("协调节点只允许返回一个 dispatch_intent")
            plan = Plan.model_validate(response.tool_calls[0].arguments)
        else:
            plan = Plan.model_validate_json(response.content)
        return plan

    def validate_plan(self, state: GraphState, plan: Plan) -> Plan:
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
        return plan

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
        clauses = await self.call("compliance", "search_clause", query=state.request.message[:2000], k=5)
        return {"evidence": {"evaluation": result, "clauses": clauses}}

    async def evaluators(self, state: GraphState) -> dict[str, Any]:
        return {}

    def dimension_node(self, dimension: str) -> Node:
        async def evaluate_dimension(state: GraphState) -> dict[str, Any]:
            if state.request.intent == "new_eval" and state.request.message == "生成方案比选报告" and not state.request.history:
                # 精简报告直接解释确定性得分，不额外发起四次重复的模型评语请求。
                return {"comments": [{"dimension": dimension, "source": "engine-summary",
                                      "text": "本次精简报告直接使用工具中的维度得分与数据覆盖，不单独生成模型评语。"}]}
            context = {
                "dimension": dimension,
                "results": [
                    {
                        "scheme_name": item["scheme_name"],
                        "score": item["dimension_scores"][dimension],
                        "coverage": item["dimension_coverage"][dimension],
                        "metrics": dict([
                            (k, v) for k, v in item["metrics"].items() if v["dimension"] == dimension
                        ][:3]),
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
        evidence["clauses"] = await self.call("explain", "search_clause", query=state.request.message[:2000], k=5)
        evidence["clause_search_note"] = "本次检索未返回条文时，不得据此编造条文依据或宣称问题已获规范核实。"
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
            "request": state.request.model_dump(exclude={"history"}),
            "response_mode": "brief_report" if state.request.message == "生成方案比选报告" else "answer",
            "intent": state.plan.intent,
            "evidence": state.evidence,
            "baseline": state.baseline,
            "comparison": state.comparison,
            "comments": state.comments,
            "rewrite_numbers": [item.model_dump() for item in state.unverified_numbers],
        }
        # 改权重路径只在此读取已有评估，不运行 evaluate。
        if state.plan.intent == "reweight":
            previous = await self.call("reporter", "get_result", project_id=state.project_id)
            context["evidence"] = {**previous, "ranking": state.evidence["ranking"]}
        labels = await asyncio.to_thread(self.tools.field_labels)
        rule_names = {item["rule_id"]: item["name"] for row in context["evidence"].get("evaluation", {}).get("results", [])
                      for item in [*row.get("compliance", []), *row.get("metrics", {}).values()]}
        details = detailed_request(state.request.message) or state.request.rule_id is not None
        view = {
            "request": {"message": state.request.message}, "response_mode": context["response_mode"],
            "reader_view": reader_evidence(context["evidence"], state.request.scheme_id, state.request.message, labels, details=details),
            "rewrite_numbers": context["rewrite_numbers"],
        }
        if state.comparison:
            field = labels.get(state.comparison.get("field", ""), "设计参数")
            view["comparison_view"] = f"本次调整{field}，比较原方案与副本；加入副本会改变候选集合，不能仅据名次断言因果。"
            if details:
                view["按需查看的调整结果"] = state.comparison
        messages = messages_for("reporter", state, view)
        messages[0]["content"] += ("\n本次按用户要求解释具体依据，参数一律使用中文名称。" if details else
            "\n本次面向普通读者：先说影响和下一步，不抄分数、字段名、检查编号或公式。")
        if view["response_mode"] == "answer" and not details:
            messages[0]["content"] += "只写一段约一百字的简短答复，不用报告章节。"
        brief = state.request.intent == "new_eval" and state.request.message == "生成方案比选报告" and not state.request.history
        # 解释路径已经固定读取评估并检索条文，避免模型重复取相同证据。
        allowed = [] if brief or state.plan.intent == "explain" and not details else ["explain_metric"] if state.plan.intent == "explain" else ["get_result", "explain_metric", "search_clause"]
        for round_index in range(3):
            text = ""
            reasoning = ""
            calls = []
            # 最后一轮只组织正文，不再继续开启工具回合。
            round_allowed = allowed if round_index < 2 else []
            async for chunk in self.llm.stream(messages, tool_schemas(round_allowed)):
                text += chunk.text
                reasoning += getattr(chunk, "reasoning_content", "")
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
                protected_names = tuple(row["scheme_name"] for row in context["evidence"].get("evaluation", {}).get("results", []))
                readable = text if re.search(r"字段名|英文参数|原始参数|来源原文", state.request.message) else humanize(text, labels, protected_names)
                if not details:
                    readable = re.sub(r"\b(?:[A-Z]+-)+\d{2}\b", lambda match: rule_names.get(match[0], match[0]), readable)
                if readable != text:
                    await self.emit("token", {"node": "reporter", "attempt": attempt, "text": readable, "replace": True})
                return {"report": readable, "attempt": attempt, "evidence": context["evidence"]}
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
            if reasoning:
                messages[-1]["reasoning_content"] = reasoning
            for call in calls:
                if call.name not in round_allowed:
                    raise ValueError("报告节点只允许查询证据，不能修改或计算数据")
                result = await self.call("reporter", call.name, **call.arguments)
                context["evidence"].setdefault("tool_queries", []).append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(compact_evidence(result, state.plan.rule_id), ensure_ascii=False, separators=(",", ":")),
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
