"""可替换的异步模型客户端；FakeLLM 脚本只搬运工具数值。"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import Settings, get_settings

Messages = list[dict[str, Any]]
Tools = list[dict[str, Any]]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMChunk(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMClient(Protocol):
    async def chat(self, messages: Messages, tools: Tools) -> LLMResponse: ...

    def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]: ...


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        if not settings.llm_api_key or not settings.llm_model:
            raise ValueError("openai 模式需要配置 LLM_API_KEY 和 LLM_MODEL")
        self.model = settings.llm_model
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
            timeout=60.0,
            max_retries=2,
        )

    async def chat(self, messages: Messages, tools: Tools) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, **({"tools": tools} if tools else {})
        )
        message = response.choices[0].message
        return LLMResponse(
            content=message.content or "",
            tool_calls=[
                ToolCall(id=c.id, name=c.function.name, arguments=json.loads(c.function.arguments))
                for c in (message.tool_calls or [])
            ],
        )

    async def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **({"tools": tools} if tools else {}),
        )
        calls: dict[int, dict[str, str]] = {}
        try:
            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    yield LLMChunk(text=delta.content)
                for call in delta.tool_calls or []:
                    item = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                    if call.id:
                        item["id"] = call.id
                    if call.function:
                        item["name"] += call.function.name or ""
                        item["arguments"] += call.function.arguments or ""
            if calls:
                yield LLMChunk(
                    tool_calls=[
                        ToolCall(id=c["id"], name=c["name"], arguments=json.loads(c["arguments"]))
                        for _, c in sorted(calls.items())
                    ]
                )
        finally:
            await response.close()

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
            return LLMResponse(content=render_fake_report(context))
        return LLMResponse(content="依据工具结果解释；缺项与待专业组确认的规则仍需核实。")

    async def stream(self, messages: Messages, tools: Tools) -> AsyncIterator[LLMChunk]:
        response = await self.chat(messages, tools)
        for offset in range(0, len(response.content), 48):
            yield LLMChunk(text=response.content[offset : offset + 48])
        if response.tool_calls:
            yield LLMChunk(tool_calls=response.tool_calls)


def render_fake_report(context: dict[str, Any]) -> str:
    """逐项复制引擎结果，不估算、不生成派生数字。"""
    evidence = context.get("evidence", {})
    ranking = evidence.get("ranking", {}).get("ranking", [])
    results = evidence.get("evaluation", {}).get("results", [])
    lines = ["## 结论", "离线脚本演示；虚构样例不能用作工程依据。"]
    lines.append("按工具返回的权重排序；未指定角色或权重时使用等权演示。")
    labels = {"quality": "居住品质", "structure": "结构", "construction": "施工", "green": "绿色"}
    for item in ranking:
        lines.append(
            f"{item['scheme_name']}：名次 {item['rank']}，贴近度 {item['closeness']:.2f}。"
        )
    lines += ["## 合规问题", "按规则引擎判定；规则出处含 TODO 的内容仍待专业组确认。"]
    for result in results:
        for item in result["compliance"]:
            if item["status"] in ("failed", "insufficient_data"):
                lines.append(
                    f"{result['scheme_name']}：{item['rule_id']}，{item['message']}；source：{item['source']}。"
                )
    lines += ["## 各维度对比"]
    for result in results:
        lines.append(
            f"{result['scheme_name']}："
            + "，".join(
                f"{labels[key]} {value:.2f}" for key, value in result["dimension_scores"].items()
            )
            + "。"
        )
        for item in result["metrics"].values():
            if item["score"] is not None:
                lines.append(
                    f"{item['rule_id']}：取值 {item['value']:.2f}，得分 {item['score']:.2f}；source：{item['source']}。"
                )
    if context.get("comparison"):
        comparison = context["comparison"]
        lines.append("原方案与副本对比：")
        for item in comparison.get("changed_metrics", []):
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
    lines += [
        "## 权衡与稳健性",
        "请结合工具提供的敏感性、帕累托与名次概率结果理解权衡；数据覆盖不足时结论不确定。",
    ]
    if evidence.get("ranking"):
        lines.append("工具返回权重：" + str(evidence["ranking"]["weights_used"]["weights"]) + "。")
        for item in ranking:
            lines.append(
                f"{item['scheme_name']}：首位概率 {item['first_place_probability']:.2f}；非劣方案：{'是' if item['is_non_dominated'] else '否'}。"
            )
    lines += [
        "## 修改建议",
        "优先补齐缺失输入并核对合规问题；TODO(专业组)：确认规则出处、阈值与角色权重。",
    ]
    return "\n\n".join(lines)


def get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLM()
    if settings.llm_provider == "openai":
        return OpenAILLM(settings)
    raise ValueError("LLM_PROVIDER 仅支持 fake / openai")
