"""报告与对话的 POST SSE 接口；缓存命中不构造模型客户端。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from app.agents import question_cache
from app.agents.graph import AgentGraph
from app.agents.llm import get_llm
from app.agents.state import AgentOutput, AgentRequest, GraphState, PlanPreview
from app.agents.storage import ReportCacheRow
from app.agents.suggestions import (
    QuestionSuggestions,
    parse_questions,
    project_context,
    question_view,
)
from app.agents.tools import AgentTools, digest
from app.config import get_settings
from app.db import get_session

router = APIRouter(prefix="/projects/{project_id}", tags=["agents"])
logger = logging.getLogger(__name__)
SessionDep = Annotated[Session, Depends(get_session)]
AGENT_RUN_TIMEOUT_SECONDS = 110
SUGGESTION_TIMEOUT_SECONDS = 45
PLAN_TIMEOUT_SECONDS = 45


@router.post("/plan", response_model=PlanPreview, summary="只读解析对话意图，预览待确认的参数调整")
async def preview_plan(project_id: int, payload: AgentRequest, session: SessionDep) -> PlanPreview:
    from app.models import Scheme

    tools = AgentTools(session.get_bind(), project_id)
    before = await asyncio.to_thread(tools.fingerprint, True)
    if payload.scheme_id is not None:
        selected = session.get(Scheme, payload.scheme_id)
        if selected is None or selected.project_id != project_id:
            raise HTTPException(404, "所选方案不属于当前项目")
    llm = None

    async def ignore_event(name: str, data: dict[str, Any]) -> None:
        pass

    try:
        llm = get_llm()
        async with asyncio.timeout(PLAN_TIMEOUT_SECONDS):
            graph = AgentGraph(tools, llm, ignore_event)
            state = GraphState(project_id=project_id, request=payload)
            plan = (await graph.coordinator(state))["plan"]
            resolved_weights = await asyncio.to_thread(tools.validate_preferences, plan.role, plan.weights)
            if plan.weights is not None:
                plan.weights = resolved_weights
            proposal = None
            if plan.intent == "whatif":
                # Validate before any evaluation, ranking or copy creation.
                selected = session.get(Scheme, plan.change.scheme_id)
                if selected is None or selected.project_id != project_id:
                    raise HTTPException(404, "待调整方案不属于当前项目，请重新选择方案")
                proposal = await asyncio.to_thread(tools.preview_scheme_change, **plan.change.model_dump())
            if before != await asyncio.to_thread(tools.fingerprint, True):
                raise HTTPException(409, "生成计划期间项目数据已变更，请重新发送请求")
            return PlanPreview(plan=plan, proposal=proposal, fingerprint=before)
    except HTTPException as exc:
        if exc.status_code == 400:
            raise HTTPException(422, exc.detail) from None
        raise
    except ValidationError:
        raise HTTPException(422, "未能形成有效计划，请明确方案、参数和目标值，并检查数值范围或权重设置") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except TimeoutError:
        raise HTTPException(503, "理解请求超时，请稍后重试，或使用方案参数调整入口") from None
    except Exception as exc:
        logger.warning("计划解析失败 (project_id=%s, error_type=%s)", project_id, type(exc).__name__)
        raise HTTPException(503, "暂时无法理解请求，请重试，或使用方案参数调整入口") from None
    finally:
        if llm is not None and hasattr(llm, "aclose"):
            await llm.aclose()


@router.post("/suggestions", response_model=QuestionSuggestions, summary="按当前项目生成建议追问")
async def suggestions(project_id: int, session: SessionDep, scheme_id: int | None = Query(None, gt=0), refresh: bool = False) -> QuestionSuggestions:
    engine = session.get_bind()
    tools = AgentTools(engine, project_id)
    before = await asyncio.to_thread(tools.fingerprint, False)
    context = await asyncio.to_thread(project_context, engine, project_id, scheme_id)
    labels = await asyncio.to_thread(tools.field_labels)
    view = question_view(context, labels)
    system = (Path(__file__).parents[1] / "agents/prompts/suggestions.md").read_text(encoding="utf-8")
    settings = get_settings()
    key = question_cache.PREFIX + digest({"project": project_id, "scheme": scheme_id, "inputs": before,
        "context": context, "view": view, "prompt": system, "provider": settings.llm_provider,
        "model": settings.llm_model, "base_url": settings.llm_base_url, "effort": settings.llm_reasoning_effort,
        "credential_signature": digest(settings.llm_api_key)})
    if not refresh:
        try:
            cached = await asyncio.to_thread(question_cache.read, engine, key)
        except SQLAlchemyError:
            cached = None
            logger.warning("建议缓存读取失败，本次重新生成")
        if cached and before == await asyncio.to_thread(tools.fingerprint, False):
            return cached
    llm = None
    started = perf_counter()
    phase = "model"
    try:
        llm = get_llm()
        async with asyncio.timeout(SUGGESTION_TIMEOUT_SECONDS):
            result = await llm.chat([
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(view, ensure_ascii=False, separators=(",", ":"))},
            ], [])
        if result.tool_calls:
            raise ValueError("建议问题不允许调用工具")
        phase = "validation"
        source = "fake" if get_settings().llm_provider.strip().lower() == "fake" else "model"
        response = parse_questions(result.content, context, source, labels)
        if before != await asyncio.to_thread(tools.fingerprint, False):
            raise HTTPException(409, "生成期间项目数据已变更，请刷新建议问题")
        try:
            await asyncio.to_thread(question_cache.write, engine, project_id, key, response)
        except SQLAlchemyError:
            logger.warning("建议缓存写入失败，本次仍返回已校验结果")
        return response
    except HTTPException:
        raise
    except TimeoutError:
        logger.warning("建议问题生成超时 (project_id=%s, elapsed_ms=%s)", project_id, int((perf_counter() - started) * 1000))
        raise HTTPException(503, "建议生成超时，请稍后重试；也可直接输入追问") from None
    except Exception as exc:
        # 不记录模型内容或 SDK 异常正文，避免凭据/项目数据进入日志。
        logger.warning("建议问题生成失败 (project_id=%s, phase=%s, error_type=%s, elapsed_ms=%s)",
                       project_id, phase, type(exc).__name__, int((perf_counter() - started) * 1000))
        raise HTTPException(503, "建议问题暂未生成，可重试或直接输入追问") from None
    finally:
        if llm is not None and hasattr(llm, "aclose"):
            await llm.aclose()


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
            async with asyncio.timeout(AGENT_RUN_TIMEOUT_SECONDS):
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
        except TimeoutError:
            await emit("error", {"message": "模型处理超时，请稍后重试，或检查模型服务响应速度与思考模式设置"})
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
            await emit("error", {
                "message": message,
                **({"status": exc.status_code} if isinstance(exc, HTTPException) else {}),
            })
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
    standard = payload.message == "生成方案比选报告" and not payload.history and not payload.rule_id and payload.scheme_id is None
    key = await asyncio.to_thread(tools.cache_key, payload.rank_request()) if standard else None
    await asyncio.to_thread(tools.fingerprint, payload.include_whatif)
    return EventSourceResponse(event_stream(session.get_bind(), project_id, payload, key), ping=15)


@router.post("/chat", summary="对话追问、假设推演与改权重（SSE）")
async def chat(project_id: int, payload: AgentRequest, session: SessionDep) -> EventSourceResponse:
    if payload.expected_fingerprint is not None:
        await asyncio.to_thread(AgentTools(session.get_bind(), project_id).require_fingerprint, payload.expected_fingerprint)
    if payload.scheme_id is not None:
        from app.models import Scheme

        selected = session.get(Scheme, payload.scheme_id)
        if selected is None or selected.project_id != project_id:
            raise HTTPException(404, "所选方案不属于当前项目")
    await asyncio.to_thread(
        AgentTools(session.get_bind(), project_id).fingerprint, payload.include_whatif
    )
    return EventSourceResponse(event_stream(session.get_bind(), project_id, payload, None), ping=15)
