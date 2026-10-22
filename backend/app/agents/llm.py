"""可替换的异步模型客户端；FakeLLM 脚本只搬运工具数值。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

Messages = list[dict[str, Any]]
Tools = list[dict[str, Any]]
logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMChunk(BaseModel):
    text: str = ""
    reasoning_content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMClient(Protocol):
    async def chat(self, messages: Messages, tools: Tools) -> LLMResponse: ...

    def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]: ...


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key or not settings.llm_model:
            raise ValueError("openai 模式需要配置 LLM_API_KEY 和 LLM_MODEL")
        self.model = settings.llm_model
        effort = settings.llm_reasoning_effort.strip().lower()
        if effort and effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("LLM_REASONING_EFFORT 配置无效")
        self.request_options: dict[str, Any] = {"reasoning_effort": effort} if effort else {}
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
            timeout=60.0,
            max_retries=2,
        )

    async def chat(self, messages: Messages, tools: Tools) -> LLMResponse:
        # 部分兼容网关仅正确支持流式请求；统一传输方式，复用工具拼接与完整性校验。
        content: list[str] = []
        calls: list[ToolCall] = []
        async for chunk in self.stream(messages, tools):
            content.append(chunk.text)
            calls.extend(chunk.tool_calls)
        return LLMResponse(content="".join(content), tool_calls=calls)

    @staticmethod
    def check_finish_reason(reason: str | None) -> None:
        if reason == "length":
            raise ValueError("模型输出被服务截断，请检查输出额度与思考模式设置后重试")
        if reason == "content_filter":
            raise ValueError("模型服务未能回答此问题，请调整问题后重试")

    async def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]:
        for attempt in range(2):
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, stream=True,
                **self.request_options, **({"tools": tools} if tools else {}),
            )
            calls: dict[int, dict[str, str]] = {}
            pending_reasoning = ""
            has_text = False
            finish_reason = None
            try:
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    finish_reason = choice.finish_reason or finish_reason
                    delta = choice.delta
                    pending_reasoning += getattr(delta, "reasoning_content", None) or ""
                    if delta.content and (has_text or delta.content.strip()):
                        if pending_reasoning:
                            # 空响应重试的思考不续接；有效回合的思考只回传模型。
                            yield LLMChunk(reasoning_content=pending_reasoning)
                            pending_reasoning = ""
                        has_text |= bool(delta.content.strip())
                        yield LLMChunk(text=delta.content)
                    for call in delta.tool_calls or []:
                        item = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                        if call.id:
                            item["id"] = call.id
                        if call.function:
                            item["name"] += call.function.name or ""
                            item["arguments"] += call.function.arguments or ""
                self.check_finish_reason(finish_reason)
                if calls:
                    yield LLMChunk(
                        reasoning_content=pending_reasoning,
                        tool_calls=[
                            ToolCall(id=c["id"], name=c["name"], arguments=json.loads(c["arguments"]))
                            for _, c in sorted(calls.items())
                        ],
                    )
                if has_text or calls:
                    return
            finally:
                await response.close()
            logger.warning("模型返回空响应 (mode=stream, attempt=%s)", attempt + 1)
        raise ValueError("模型服务连续返回空响应，请稍后重试或检查模型服务状态")

    async def aclose(self) -> None:
        await self.client.close()


class FakeLLM:
    """按节点消费预设回复；默认脚本支持离线完整图和简单自然语言演示。"""

    def __init__(self, scripts: dict[str, list[LLMResponse]] | None = None) -> None:
        self.scripts = {key: list(value) for key, value in (scripts or {}).items()}
        self.calls: list[Messages] = []

    async def chat(self, messages: Messages, tools: Tools) -> LLMResponse:
        self.calls.append(messages)
        node = messages[0]["content"].splitlines()[0].removeprefix("节点：")
        if self.scripts.get(node):
            return self.scripts[node].pop(0)
        context = json.loads(next(m["content"] for m in reversed(messages) if m["role"] == "user"))
        if node == "coordinator":
            request = context["request"]
            text = request["message"]
            intent = request.get("intent")
            change = request.get("change")
            if not intent:
                if re.search(r"权重|重新排序", text):
                    intent = "reweight"
                elif change or re.search(r"what.?if|假设|修改|改为|改成", text, re.I):
                    intent = "whatif"
                elif re.search(r"解释|为什么|依据|说明", text):
                    intent = "explain"
                else:
                    intent = "new_eval"
            if intent == "whatif" and not change:
                match = re.search(
                    r"方案\s*(\d+).*?([a-z_]+)\s*(?:改为|改成|=|到)\s*(\d+(?:\.\d+)?)", text
                )
                if match:
                    change = {
                        "scheme_id": int(match[1]),
                        "field": match[2],
                        "value": json.loads(match[3]),
                    }
            weights = request.get("weights")
            if intent == "reweight" and not weights:
                match = re.search(r"\[([^\]]+)\]", text)
                if match:
                    weights = [float(v.strip()) for v in match[1].split(",")]
            rule = request.get("rule_id")
            match = re.search(r"[CQSKG]-\d{2}", text)
            rule = rule or (match[0] if match else None)
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="plan",
                        name="dispatch_intent",
                        arguments={
                            "intent": intent,
                            "change": change,
                            "role": request.get("role"),
                            "weights": weights,
                            "rule_id": rule,
                        },
                    )
                ]
            )
        if node == "reporter":
            if "reader_view" in context:
                from app.agents.readable import render_reader_demo
                return LLMResponse(content=render_reader_demo(context))
            return LLMResponse(content=render_fake_report(context))
        if node == "suggestions":
            from app.agents.suggestions import local_questions

            return LLMResponse(content=json.dumps({"questions": local_questions(context)}, ensure_ascii=False))
        return LLMResponse(content="依据工具结果解释；缺项与待专业组确认的规则仍需核实。")

    async def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]:
        response = await self.chat(messages, tools)
        for offset in range(0, len(response.content), 48):
            yield LLMChunk(text=response.content[offset : offset + 48])
        if response.tool_calls:
            yield LLMChunk(tool_calls=response.tool_calls)


def render_fake_report(context: dict[str, Any]) -> str:
    """只摘录关键引擎证据，不罗列整份规则目录。"""
    evidence = context.get("evidence", {})
    ranking = evidence.get("ranking", {}).get("ranking", [])
    results = evidence.get("evaluation", {}).get("results", [])
    request = context.get("request", {})
    selected = next((item for item in results if item["scheme_id"] == str(request.get("scheme_id"))), None)
    selected = selected or next((item for item in results if ranking and item["scheme_id"] == ranking[0]["scheme_id"]), None)
    selected = selected or next(iter(results), None)
    brief_report = context.get("response_mode", "brief_report") == "brief_report"
    lines = ["## 结论"] if brief_report else []
    lines.append("FakeLLM 演示；以下仅摘录当前工具结果。")
    if any(item["status"] == "insufficient_data" for row in results for item in row["compliance"]):
        lines.append("仍有检查数据不足；排名仅展示已知条件下的评分与取舍，不能认定全部合规或确定最优方案。")
    labels = {"quality": "居住品质", "structure": "结构", "construction": "施工", "green": "绿色"}
    for item in ranking[:1]:
        lines.append(
            f"{item['scheme_name']}：名次 {item['rank']}，贴近度 {item['closeness']:.2f}。"
        )
    if selected:
        lines.append(
            f"{selected['scheme_name']}："
            + "，".join(
                f"{labels[key]} {value:.2f}" for key, value in selected["dimension_scores"].items()
            )
            + "。"
        )
    if brief_report:
        lines.append("## 关键问题")
    problems = [(result, item) for result in (results if brief_report else [selected] if selected else [])
                for item in result["compliance"] if item["status"] in ("failed", "insufficient_data")]
    problems.sort(key=lambda pair: pair[1]["status"] != "failed")
    for result, item in problems[:2]:
        lines.append(f"{result['scheme_name']}：{item['rule_id']}，{item['message']}；source：{item['source']}。")
    if not problems:
        lines.append("此摘要未列出硬约束问题；是否可判断合规仍须结合资料覆盖与完整结果。")
    if context.get("comparison"):
        comparison = context["comparison"]
        lines.append("原方案与副本对比：")
        for item in comparison.get("changed_metrics", [])[:3]:
            lines.append(
                f"{item['rule_id']}：取值 {item['before_value']} → {item['after_value']}，得分 {item['before_score']} → {item['after_score']}；source：{item['source']}。"
            )

        def rank_text(key: str) -> str:
            value = comparison.get(key)
            return str(value) if value is not None else "未参与排名"

        lines.append(
            f"原方案原名次：{rank_text('baseline_rank')}；加入副本后原方案名次：{rank_text('parent_rank')}；副本名次：{rank_text('copy_rank')}。"
        )
        lines.append(
            "指标变化经维度评分与 TOPSIS 影响排序；加入副本也改变候选集合和归一化基准，不能仅据名次断言因果。未变化的指标不作为改善证据。"
        )
    if evidence.get("explanation"):
        rule = evidence["explanation"]
        lines.append(
            f"规则 {rule['id']}：{rule['name']}；公式：{rule['formula']}；source：{rule['source']}。"
        )
    if brief_report:
        lines.append("## 下一步")
    lines.append("先核实上述问题与缺失资料；完整规则和计算依据见看板及溯源。TODO(专业组)：核定出处、阈值与权重。")
    return "\n\n".join(lines)


def get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLM()
    if settings.llm_provider == "openai":
        return OpenAILLM(settings)
    raise ValueError("LLM_PROVIDER 仅支持 fake / openai")
