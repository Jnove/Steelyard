"""SDK 兼容接口、重试与流式工具调用拼接，均用本地 HTTP 假响应。"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.agents.llm import OpenAILLM
from app.config import Settings
from openai import AsyncOpenAI


def settings() -> Settings:
    return Settings(
        LLM_PROVIDER="openai",
        LLM_API_KEY="test",
        LLM_MODEL="test-model",
        LLM_BASE_URL="https://model.test/v1",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_chat_and_retry() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        if len(calls) < 3:
            return httpx.Response(500, json={"error": {"message": "测试暂时失败"}})
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "测试文本",
                            "tool_calls": [
                                {
                                    "id": "call",
                                    "type": "function",
                                    "function": {
                                        "name": "search_clause",
                                        "arguments": '{"query":"规则"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            },
        )

    llm = OpenAILLM(settings())
    assert llm.client.timeout == 60 and llm.client.max_retries == 2
    await llm.client.close()
    llm.client = AsyncOpenAI(
        api_key="test",
        base_url="https://model.test/v1",
        timeout=60,
        max_retries=2,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await llm.chat([{"role": "user", "content": "测试"}], [])
    assert len(calls) == 3 and calls[0]["model"] == "test-model"
    assert "tools" not in calls[0]
    assert result.content == "测试文本" and result.tool_calls[0].arguments == {"query": "规则"}
    await llm.aclose()


@pytest.mark.asyncio
async def test_stream_fragments() -> None:
    deltas: list[dict[str, Any]] = [
        {"content": "报告"},
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call",
                    "type": "function",
                    "function": {"name": "explain_metric", "arguments": '{"rule_'},
                }
            ]
        },
        {"tool_calls": [{"index": 0, "function": {"arguments": 'id":"K-01"}'}}]},
    ]
    body = (
        "".join(
            "data: "
            + json.dumps(
                {
                    "id": "test",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "test-model",
                    "choices": [{"index": 0, "delta": delta}],
                }
            )
            + "\n\n"
            for delta in deltas
        )
        + "data: [DONE]\n\n"
    )
    llm = OpenAILLM(settings())
    await llm.client.close()
    llm.client = AsyncOpenAI(
        api_key="test",
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, headers={"content-type": "text/event-stream"}, content=body
                )
            )
        ),
    )
    chunks = [chunk async for chunk in llm.stream([{"role": "user", "content": "测试"}], [])]
    assert chunks[0].text == "报告"
    assert chunks[-1].tool_calls[0].arguments == {"rule_id": "K-01"}
    await llm.aclose()


def test_config_requires_model_and_key() -> None:
    with pytest.raises(ValueError):
        OpenAILLM(Settings(LLM_PROVIDER="openai", _env_file=None))


@pytest.mark.asyncio
async def test_reasoning_effort_and_private_stream_reasoning() -> None:
    configured = settings()
    configured.llm_reasoning_effort = "low"
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            deltas = [{"reasoning_content": "private reasoning"}, {"content": "简短正文"}]
            content = "".join("data: " + json.dumps({"id": "test", "object": "chat.completion.chunk", "created": 0,
                "model": "test-model", "choices": [{"index": 0, "delta": delta}]}) + "\n\n" for delta in deltas)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=content + "data: [DONE]\n\n")
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "简短正文"}, "finish_reason": "stop"}]})
    llm = OpenAILLM(configured)
    await llm.client.close()
    llm.client = AsyncOpenAI(api_key="test", base_url="https://model.test/v1",
                            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert (await llm.chat([{"role": "user", "content": "测试"}], [])).content == "简短正文"
    chunks = [chunk async for chunk in llm.stream([{"role": "user", "content": "测试"}], [])]
    assert chunks[0].reasoning_content == "private reasoning" and not chunks[0].text
    assert "".join(chunk.text for chunk in chunks) == "简短正文"
    assert all(call["reasoning_effort"] == "low" for call in calls)
    await llm.aclose()
