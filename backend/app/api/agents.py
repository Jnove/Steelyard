"""报告与对话的 POST SSE 接口；缓存命中不构造模型客户端。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import AgentGraph
from app.agents.llm import get_llm
from app.agents.state import AgentOutput, AgentRequest, GraphState
from app.agents.storage import ReportCacheRow
from app.agents.tools import AgentTools
from app.db import get_session

router = APIRouter(prefix="/projects/{project_id}", tags=["agents"])
logger = logging.getLogger(__name__)
SessionDep = Annotated[Session, Depends(get_session)]


async def event_stream(
    engine: Engine, project_id: int, payload: AgentRequest, cache_key: str | None
) -> AsyncIterator[dict[str, str]]:
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue(maxsize=128)

    async def emit(name: str, data: dict[str, Any]) -> None:
        await queue.put((name, data))

    async def produce() -> None:
        llm = None
        try:
            if cache_key:
                with Session(engine) as session:
                    row = session.get(ReportCacheRow, cache_key)
                    output = AgentOutput.model_validate(row.output) if row else None
                if output:
                    output.cached = True
                    await emit(
                        "token",
                        {"node": "reporter", "attempt": 0, "text": output.report, "replace": True},
                    )
                    await emit("done", output.model_dump(mode="json"))
                    return
            llm = get_llm()
            tools = AgentTools(engine, project_id)
            fingerprint = await asyncio.to_thread(tools.fingerprint, payload.include_whatif)
            output = await AgentGraph(tools, llm, emit).run(
                GraphState(project_id=project_id, request=payload)
            )
            if output.intent != "whatif" and fingerprint != await asyncio.to_thread(
                tools.fingerprint, payload.include_whatif
            ):
                raise HTTPException(409, "生成期间项目数据或规则已变更，请重新请求")
            # 只缓存通过校验的标准报告，且生成期间输入未改变。
            if (
                cache_key
                and not output.unverified_numbers
                and cache_key == await asyncio.to_thread(tools.cache_key, payload.rank_request())
            ):
                with Session(engine) as session:
                    row = session.get(ReportCacheRow, cache_key) or ReportCacheRow(
                        key=cache_key, project_id=project_id, output={}
                    )
                    row.output = output.model_dump(mode="json")
                    session.add(row)
                    session.commit()
            await emit("done", output.model_dump(mode="json"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("智能体请求失败")
            # SDK 异常可能含服务地址等信息，网络失败只给中文通用说明。
            message = (
                str(exc.detail)
                if isinstance(exc, HTTPException)
                else str(exc)
                if isinstance(exc, ValueError)
                else "智能体执行失败，请检查服务日志与模型配置"
            )
            await emit("error", {"message": message})
        finally:
            try:
                if llm is not None and hasattr(llm, "aclose"):
                    await llm.aclose()
            finally:
                if not asyncio.current_task().cancelling():
                    await queue.put(None)

    task = asyncio.create_task(produce())
    try:
        while (item := await queue.get()) is not None:
            name, data = item
            yield {"event": name, "data": json.dumps(data, ensure_ascii=False)}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@router.post("/report", summary="生成比选报告（SSE）")
async def report(
    project_id: int, session: SessionDep, payload: AgentRequest | None = None
) -> EventSourceResponse:
    payload = payload or AgentRequest()
    if payload.intent not in (None, "new_eval") or payload.change:
        raise HTTPException(422, "报告接口只接受新评估；追问与假设推演请使用 chat")
    payload = payload.model_copy(update={"intent": "new_eval"})
    tools = AgentTools(session.get_bind(), project_id)
    # 非标准对话/追问不命中标准报告缓存，避免忽略用户要求。
    standard = payload.message == "生成方案比选报告" and not payload.history and not payload.rule_id
    key = await asyncio.to_thread(tools.cache_key, payload.rank_request()) if standard else None
    await asyncio.to_thread(tools.fingerprint, payload.include_whatif)
    return EventSourceResponse(event_stream(session.get_bind(), project_id, payload, key), ping=15)


@router.post("/chat", summary="对话追问、假设推演与改权重（SSE）")
async def chat(project_id: int, payload: AgentRequest, session: SessionDep) -> EventSourceResponse:
    await asyncio.to_thread(
        AgentTools(session.get_bind(), project_id).fingerprint, payload.include_whatif
    )
    return EventSourceResponse(event_stream(session.get_bind(), project_id, payload, None), ping=15)
