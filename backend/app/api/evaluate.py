"""方案评估路由。

``POST /api/projects/{project_id}/evaluate`` 跑一遍规则 + 指标 + 评分，
把每个方案的完整结果写进 ``eval_results`` 表并返回。

这条接口 **不经过大模型**：同样的输入必然得到同样的输出，演示现场断网也能跑。
排序（TOPSIS / AHP）是 T4 的 ``/rank``，本接口只产出维度得分，``topsis`` 字段留空。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.db import get_session
from app.engine.regions import GB_PACK
from app.engine.rules import RuleLoadError, SchemeInput, evaluate, get_ruleset
from app.models import EvalResult, EvalResultRow, Project, ProjectParams, Scheme, SchemeParams

router = APIRouter(prefix="/projects/{project_id}", tags=["evaluate"])

SessionDep = Annotated[Session, Depends(get_session)]


class EvaluateResponse(BaseModel):
    """评估响应。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "评估结果集",
            "description": "按方案顺序给出的完整评估结果，同时已落库到 eval_results",
        }
    )

    project_id: int = Field(description="项目 id")
    rule_count: int = Field(description="本次参与评估的规则条数")
    results: list[EvalResult] = Field(description="每个方案一条结果")


def _require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在")
    return project


@router.post(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="评估项目下的全部方案（规则 + 指标 + 评分）",
)
def evaluate_project(
    project_id: int,
    session: SessionDep,
    include_whatif: Annotated[
        bool,
        Query(description="是否把 what-if 副本也一起评估；默认只评估正式方案"),
    ] = False,
) -> EvaluateResponse:
    """跑一遍确定性引擎并把结果落库。

    重复调用是幂等的：同一项目的旧结果会先删掉再写新的，不会越评越多行。
    """
    project = _require_project(session, project_id)

    statement = select(Scheme).where(Scheme.project_id == project_id)
    if not include_whatif:
        statement = statement.where(Scheme.is_whatif == False)  # noqa: E712
    schemes = session.exec(statement.order_by(Scheme.id)).all()

    if not schemes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"项目 {project_id} 下还没有方案，请先新增或导入方案再评估",
        )

    try:
        ruleset = get_ruleset()
    except RuleLoadError as exc:
        # 规则写错了是规则作者的问题，不是调用方的问题，用 500 并把中文原因带出来。
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "规则加载失败，请跑 scripts/check_rules.py 修正",
                "problems": exc.problems,
            },
        ) from exc

    project_params = ProjectParams.model_validate(project.params or {})

    # 按项目选中的**册**筛选规则：留空＝只用国家标准（GB）。
    # GB 永远在内；省级册只有项目显式开启才参与——地方条例的适用范围就是那一省，
    # 不该顺手影响别的项目。见 app/engine/regions.py 与 docs/design-regional-packs.md。
    ruleset = ruleset.select_packs(project_params.standard_packs or [GB_PACK])
    inputs = [
        SchemeInput(
            scheme_id=str(scheme.id),
            name=scheme.name,
            params=SchemeParams.model_validate(scheme.params or {}),
        )
        for scheme in schemes
    ]

    results = evaluate(project_params, inputs, ruleset)

    # 先清掉本项目的旧结果，保证同一方案只有一行最新结果。
    for stale in session.exec(
        select(EvalResultRow).where(EvalResultRow.project_id == project_id)
    ).all():
        session.delete(stale)
    for scheme, result in zip(schemes, results, strict=True):
        session.add(
            EvalResultRow(
                project_id=project_id,
                scheme_id=scheme.id or 0,
                result=result.model_dump(mode="json"),
            )
        )
    session.commit()

    response = EvaluateResponse(
        project_id=project_id, rule_count=len(ruleset.rules), results=results
    )
    # T8 保存最近一次工具证据；REST 评估也必须使旧排名失效。
    from app.agents.tools import record_evaluation

    record_evaluation(session, project_id, response.model_dump(mode="json"), include_whatif)
    return response


@router.get(
    "/evaluate",
    response_model=EvaluateResponse,
    summary="读取上一次的评估结果（不重新计算）",
)
def get_last_evaluation(project_id: int, session: SessionDep) -> EvaluateResponse:
    """取已落库的评估结果。没评估过就返回空列表，由前端提示"请先评估"。"""
    _require_project(session, project_id)
    rows = session.exec(
        select(EvalResultRow)
        .where(EvalResultRow.project_id == project_id)
        .order_by(EvalResultRow.scheme_id)
    ).all()
    results = [EvalResult.model_validate(row.result) for row in rows]
    return EvaluateResponse(project_id=project_id, rule_count=0, results=results)
