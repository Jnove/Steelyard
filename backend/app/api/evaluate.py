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

from app.custom import fields as fields_service
from app.custom.errors import CustomAddError
from app.custom.rules import ruleset_with_custom
from app.custom.signature import SIGNATURE_KEY, require_rules_signature, rules_signature
from app.db import get_session
from app.engine.rules import RuleLoadError, SchemeInput, evaluate
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
        # 内建规则 + 覆盖层的自定义规则（见 app/custom/rules.py）。
        # 没有自定义规则时返回的就是内建集合本身，行为与纯内建完全一致。
        ruleset = ruleset_with_custom(session)
    except RuleLoadError as exc:
        # 规则写错了是规则作者的问题，不是调用方的问题，用 500 并把中文原因带出来。
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "规则加载失败，请跑 scripts/check_rules.py 修正",
                "problems": exc.problems,
            },
        ) from exc
    except CustomAddError as exc:
        # 自定义规则的报错措辞与 check_rules 一致，逐条带出来让使用者在界面上改。
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "自定义规则校验失败，请在自定义页面修正或删除",
                "problems": [
                    {"code": p.code, "message": p.message, "fix": p.fix} for p in exc.problems
                ],
            },
        ) from exc

    project_params = ProjectParams.model_validate(project.params or {})
    inputs = [
        SchemeInput(
            scheme_id=str(scheme.id),
            name=scheme.name,
            params=SchemeParams.model_validate(scheme.params or {}),
        )
        for scheme in schemes
    ]

    try:
        for item in inputs:
            fields_service.validate_values(session, item.params.custom, allow_inactive=True)
    except CustomAddError as exc:
        raise HTTPException(422, detail={"message": str(exc), "problems": [
            {"code": p.code, "message": p.message, "fix": p.fix} for p in exc.problems
        ]}) from exc
    results = evaluate(project_params, inputs, ruleset, known=fields_service.known_names(session))
    signature = rules_signature(session, ruleset=ruleset)

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
                result={**result.model_dump(mode="json"), SIGNATURE_KEY: signature},
            )
        )
    session.commit()

    response = EvaluateResponse(
        project_id=project_id, rule_count=len(ruleset.rules), results=results
    )
    # T8 保存最近一次工具证据；REST 评估也必须使旧排名失效。
    from app.agents.tools import record_evaluation

    record_evaluation(session, project_id, response.model_dump(mode="json"), include_whatif, signature=signature)
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
    if not rows:
        return EvaluateResponse(project_id=project_id, rule_count=0, results=[])
    ruleset = ruleset_with_custom(session)
    signature = rules_signature(session, ruleset=ruleset)
    for row in rows:
        require_rules_signature(row.result, signature)
    results = [EvalResult.model_validate(row.result) for row in rows]
    return EvaluateResponse(project_id=project_id, rule_count=len(ruleset.rules), results=results)
