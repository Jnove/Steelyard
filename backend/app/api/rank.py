"""方案排序路由。

``POST /api/projects/{project_id}/rank`` 读取最近一次 ``evaluate`` 的维度得分，
按给定权重跑 TOPSIS，并一并给出敏感性、翻转点、帕累托与名次概率。

**不经过大模型**，也不重跑规则引擎：它只吃 ``eval_results`` 里已经算好的维度得分。
前端的权重滑杆会频繁调这条接口，所以整条链路都走 :mod:`app.engine.mcdm` 的批量路径，
5 个方案时远快于 100 ms 的预算（见 ``tests/test_rank_endpoint.py`` 的计时断言）。

权重三选一：``role``（先查 ``rules/weights.yaml`` 的角色模板，再查运行期自定义的角色模板）、
``weights``（直接给四个数）、``pairwise_matrix``（现场给一个 4×4 两两比较矩阵，走 AHP 解）。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import Session, select

from app.custom.errors import CustomAddError
from app.custom.signature import require_rules_signature, rules_signature
from app.custom.templates import list_templates, resolve_template, to_engine_template
from app.db import get_session
from app.engine.mcdm import (
    CRITERION_ORDER,
    AhpResult,
    McdmInputError,
    ParetoResult,
    RankAcceptabilityResult,
    SensitivityResult,
    TopsisResult,
    ahp_weights,
    normalize_weights,
    pareto_front,
    rank_acceptability,
    sensitivity,
    topsis,
)
from app.engine.weights import (
    RoleWeightTemplate,
    WeightsLoadError,
    get_role_templates,
)
from app.models import EvalResult, EvalResultRow, Project, Scheme

router = APIRouter(prefix="/projects/{project_id}", tags=["rank"])

SessionDep = Annotated[Session, Depends(get_session)]

#: 敏感性分析默认的扰动比例。
DEFAULT_DELTAS: tuple[float, ...] = (-0.2, -0.1, 0.1, 0.2)


# —— 请求 —— #


class RankRequest(BaseModel):
    """排序请求。``role`` / ``weights`` / ``pairwise_matrix`` **三选一**。"""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        json_schema_extra={
            "title": "排序请求",
            "description": "role、weights、pairwise_matrix 必须且只能提供一项",
        },
    )

    role: str | None = Field(
        None,
        description=(
            "角色键，先查 rules/weights.yaml（government / developer / contractor / resident），"
            "再查运行期自定义的权重模板（可用 custom:<id> 或模板名）"
        ),
    )
    weights: list[float] | None = Field(
        None,
        description=f"直接给权重，{len(CRITERION_ORDER)} 个非负数，顺序是 {' / '.join(CRITERION_ORDER)}；会自动归一化",
    )
    pairwise_matrix: list[list[float]] | None = Field(
        None,
        description=f"{len(CRITERION_ORDER)}×{len(CRITERION_ORDER)} 两两比较矩阵，走 AHP 解权重",
    )
    include_noncompliant: bool = Field(
        False,
        description=(
            "是否让存在 error 级硬约束未通过的方案参与排名。"
            "默认 false：它们不参与排序，但会在 excluded 里列出并注明原因"
        ),
    )
    include_whatif: bool = Field(
        False, description="是否把 what-if 副本一并纳入排序（需要 evaluate 时也带上了它们）"
    )
    monte_carlo_samples: int = Field(1000, gt=0, le=20000, description="名次概率的抽样组数")
    monte_carlo_concentration: float = Field(
        50.0, gt=0, description="Dirichlet 集中度；越大越贴近基准权重"
    )
    seed: int = Field(0, ge=0, description="蒙特卡洛随机种子；同 seed 结果完全可复现")

    @model_validator(mode="after")
    def _exactly_one_weight_source(self) -> RankRequest:
        given = [
            name
            for name, value in (
                ("role", self.role),
                ("weights", self.weights),
                ("pairwise_matrix", self.pairwise_matrix),
            )
            if value is not None
        ]
        if len(given) != 1:
            raise ValueError("role / weights / pairwise_matrix 必须且只能提供一项")
        return self


# —— 响应 —— #


class WeightsUsed(BaseModel):
    """本次排序用的权重，以及它是怎么来的。报告要写清"凭什么这么排"。"""

    model_config = ConfigDict(json_schema_extra={"title": "使用的权重"})

    source: Literal["role", "weights", "pairwise_matrix"] = Field(description="权重来源")
    criteria: list[str] = Field(description="准则顺序，固定为四个维度")
    weights: list[float] = Field(description="归一化后的权重，和为 1")
    role: str | None = Field(None, description="来源是 role 时的角色键")
    role_name: str | None = Field(None, description="来源是 role 时的角色中文名")
    is_custom: bool = Field(
        False,
        description=(
            "该角色模板是否来自运行期自定义（未进入 git、不参与 CI 校验）；"
            "报告里应据此提示读者"
        ),
    )
    note: str = Field("", description="角色模板的说明；自定义权重时为空")
    ahp: AhpResult | None = Field(
        None, description="有两两比较矩阵时的一致性检验结果；直接给权重时为 null"
    )
    consistency_warning: str | None = Field(
        None, description="CR ≥ 0.1 时的中文提示；通过时为 null"
    )


class RankedScheme(BaseModel):
    """参与排序的一个方案。"""

    model_config = ConfigDict(json_schema_extra={"title": "排序结果项"})

    scheme_id: str = Field(description="方案 id")
    scheme_name: str = Field(description="方案名称")
    dimension_scores: list[float] = Field(description="四个维度得分，顺序同 criteria")
    closeness: float = Field(description="TOPSIS 贴近度，0–1")
    rank: int = Field(description="名次，从 1 开始；并列时名次相同")
    is_non_dominated: bool = Field(description="是否为帕累托非劣方案")
    dominated_by: list[str] = Field(
        default_factory=list, description="支配它的方案 id；非劣方案为空"
    )
    first_place_probability: float = Field(description="蒙特卡洛下排第一的概率")


class ExcludedScheme(BaseModel):
    """未参与排序的方案，以及原因。"""

    model_config = ConfigDict(json_schema_extra={"title": "未参与排序的方案"})

    scheme_id: str = Field(description="方案 id")
    scheme_name: str = Field(description="方案名称")
    reason: str = Field(description="为什么没参与排序")
    failed_rules: list[str] = Field(
        default_factory=list, description="导致被排除的 error 级规则 ID"
    )


class RankResponse(BaseModel):
    """排序响应。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "排序结果",
            "description": "权重与一致性、名次、敏感性、翻转点、帕累托、名次概率",
        }
    )

    project_id: int = Field(description="项目 id")
    scheme_order: list[str] = Field(
        description="所有分析数组的方案 ID 顺序；下标对应此列表，ranking 按名次展示"
    )
    criteria: list[str] = Field(description="准则（维度）顺序")
    weights_used: WeightsUsed = Field(description="本次使用的权重及其出处")
    ranking: list[RankedScheme] = Field(description="参与排序的方案，按名次升序")
    excluded: list[ExcludedScheme] = Field(description="未参与排序的方案及原因")
    topsis: TopsisResult = Field(description="TOPSIS 原始结果，含正负理想解")
    sensitivity: SensitivityResult = Field(description="敏感性表与翻转点")
    pareto: ParetoResult = Field(description="帕累托筛选（下标对应 scheme_order）")
    rank_acceptability: RankAcceptabilityResult = Field(description="名次概率矩阵")
    elapsed_ms: float = Field(description="服务端计算耗时（毫秒），用于盯住滑杆的响应预算")


# —— 取数 —— #


def _require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在")
    return project


def _load_latest_results(
    session: Session, project_id: int, include_whatif: bool
) -> list[tuple[Scheme, EvalResult]]:
    """读最近一次 evaluate 落库的结果，并配上方案记录。

    Raises:
        HTTPException: 409，还没评估过。排序依赖维度得分，没有得分无从排起。
    """
    rows = session.exec(
        select(Scheme, EvalResultRow)
        .join(EvalResultRow, Scheme.id == EvalResultRow.scheme_id)
        .where(EvalResultRow.project_id == project_id)
        .where(Scheme.project_id == project_id)
        .order_by(EvalResultRow.scheme_id, EvalResultRow.created_at.desc(), EvalResultRow.id.desc())
    ).all()
    if not rows:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"项目 {project_id} 还没有评估结果，无法排序。"
                f"请先调 POST /api/projects/{project_id}/evaluate"
            ),
        )

    out: list[tuple[Scheme, EvalResult]] = []
    seen: set[int] = set()
    project = _require_project(session, project_id)
    signature = rules_signature(session)
    for scheme, row in rows:
        if row.scheme_id in seen:
            continue
        seen.add(row.scheme_id)
        if scheme.is_whatif and not include_whatif:
            continue
        require_rules_signature(row.result, signature)
        if max(scheme.updated_at.replace(tzinfo=None), project.updated_at.replace(tzinfo=None)) > row.created_at.replace(tzinfo=None):
            raise HTTPException(409, detail="项目或方案参数已变更，请先重新评估再排序")
        out.append((scheme, EvalResult.model_validate(row.result)))
    return out


def _resolve_weights(payload: RankRequest, session: Session) -> WeightsUsed:
    """把三种入参解析成一份归一化权重。

    调用方必须明确提供一种来源，避免无意采用某个角色的立场。
    ``role`` 的解析顺序：先内建（``rules/weights.yaml``），再运行期自定义模板（覆盖层）。
    """
    n = len(CRITERION_ORDER)

    if payload.weights is not None:
        if len(payload.weights) != n:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"weights 需要 {n} 个数，顺序是 {' / '.join(CRITERION_ORDER)}",
            )
        try:
            resolved = normalize_weights(payload.weights)
        except McdmInputError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return WeightsUsed(
            source="weights",
            criteria=list(CRITERION_ORDER),
            weights=resolved.tolist(),
        )

    if payload.pairwise_matrix is not None:
        try:
            result = ahp_weights(payload.pairwise_matrix)
        except McdmInputError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if len(result.weights) != n:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"pairwise_matrix 必须是 {n}×{n}，对应 {' / '.join(CRITERION_ORDER)}",
            )
        return WeightsUsed(
            source="pairwise_matrix",
            criteria=list(CRITERION_ORDER),
            weights=result.weights,
            ahp=result,
            consistency_warning=_consistency_warning(result),
        )

    role_key = payload.role
    if role_key is None:  # 到不了这里：RankRequest 已保证三选一
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="请提供 role / weights / pairwise_matrix 之一"
        )
    try:
        templates = get_role_templates()
    except WeightsLoadError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "角色权重模板加载失败，请跑 scripts/check_rules.py 修正",
                "problems": [p.message for p in exc.problems],
            },
        ) from exc
    template = templates.get(role_key)
    if template is not None:
        return _weights_from_template(template)

    # 内建里没有，再看运行期添加的自定义模板（覆盖层）。
    try:
        custom = resolve_template(session, role_key)
    except CustomAddError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"自定义权重模板「{role_key}」校验失败",
                "problems": [
                    {"code": p.code, "message": p.message, "fix": p.fix} for p in exc.problems
                ],
            },
        ) from exc
    if custom is not None:
        return _weights_from_template(custom, is_custom=True)

    known = sorted(templates) + [f"{row.name}（自定义）" for row in list_templates(session)]
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail=f"没有角色 {role_key!r}，可选：{'、'.join(known)}",
    )


def _weights_from_template(
    template: RoleWeightTemplate, *, is_custom: bool = False
) -> WeightsUsed:
    note = template.note
    if is_custom:
        marker = "自定义权重模板（运行期添加，未进入 git、不参与 CI 校验）"
        note = f"{marker}：{note}" if note else marker
    return WeightsUsed(
        source="role",
        criteria=list(CRITERION_ORDER),
        weights=template.weights,
        role=template.key,
        role_name=template.name,
        is_custom=is_custom,
        note=note,
        ahp=template.ahp,
        consistency_warning=_consistency_warning(template.ahp),
    )


def _consistency_warning(result: AhpResult | None) -> str | None:
    """CR 超标时给一句中文提示，让前端能显式标出来而不是静默采用。"""
    if result is None or result.consistent:
        return None
    return (
        f"两两比较矩阵的一致性比率 CR = {result.cr:.3f}，超过 0.1 的上限，"
        "说明判断之间自相矛盾；权重仍按它算出来了，但结论应当谨慎使用"
    )


def _blocking_rules(result: EvalResult) -> list[str]:
    """导致方案被踢出排名的 error 级未通过规则。"""
    return [
        item.rule_id
        for item in result.compliance
        if item.status == "failed" and item.severity == "error"
    ]


# —— 路由 —— #


@router.post(
    "/rank",
    response_model=RankResponse,
    summary="按权重排序（TOPSIS + 敏感性 + 帕累托 + 名次概率）",
)
def rank_project(
    project_id: int,
    payload: RankRequest,
    session: SessionDep,
) -> RankResponse:
    """按给定权重对方案排序，并给出稳健性分析。

    权重三选一：``role`` / ``weights`` / ``pairwise_matrix``。
    默认把 error 级硬约束未通过的方案排除在排序之外，但会在 ``excluded`` 里列出原因。
    """
    import time

    started = time.perf_counter()

    _require_project(session, project_id)
    pairs = _load_latest_results(session, project_id, payload.include_whatif)
    weights_used = _resolve_weights(payload, session)

    participants: list[tuple[Scheme, EvalResult]] = []
    excluded: list[ExcludedScheme] = []
    for scheme, result in pairs:
        blocking = _blocking_rules(result)
        if blocking and not payload.include_noncompliant:
            excluded.append(
                ExcludedScheme(
                    scheme_id=str(scheme.id),
                    scheme_name=scheme.name,
                    reason=(
                        f"有 {len(blocking)} 条 error 级硬约束未通过（{'、'.join(blocking)}），"
                        "默认不参与排名；想让它参与请传 include_noncompliant=true"
                    ),
                    failed_rules=blocking,
                )
            )
            continue
        participants.append((scheme, result))

    scores = np.asarray(
        [
            [getattr(result.dimension_scores, key) for key in CRITERION_ORDER]
            for _, result in participants
        ],
        dtype=float,
    ).reshape((-1, len(CRITERION_ORDER)))

    try:
        topsis_result = topsis(scores, weights_used.weights)
        sensitivity_result = sensitivity(
            scores, weights_used.weights, deltas=DEFAULT_DELTAS, criterion_names=CRITERION_ORDER
        )
        pareto_result = pareto_front(scores)
        acceptability = rank_acceptability(
            scores,
            weights_used.weights,
            n=payload.monte_carlo_samples,
            concentration=payload.monte_carlo_concentration,
            seed=payload.seed,
        )
    except McdmInputError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ranking = _build_ranking(participants, topsis_result, pareto_result, acceptability)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    response = RankResponse(
        project_id=project_id,
        scheme_order=[str(scheme.id) for scheme, _ in participants],
        criteria=list(CRITERION_ORDER),
        weights_used=weights_used,
        ranking=ranking,
        excluded=excluded,
        topsis=topsis_result,
        sensitivity=sensitivity_result,
        pareto=pareto_result,
        rank_acceptability=acceptability,
        elapsed_ms=elapsed_ms,
    )
    # T8 对话需要读取权重滑杆经 REST 生成的最近一次排名。
    from app.agents.tools import record_ranking

    record_ranking(
        session, project_id, response.model_dump(mode="json"), payload.include_whatif, pairs
    )
    return response


def _build_ranking(
    participants: list[tuple[Scheme, EvalResult]],
    topsis_result: TopsisResult,
    pareto_result: ParetoResult,
    acceptability: RankAcceptabilityResult,
) -> list[RankedScheme]:
    """把各路结果按方案拼起来，并按名次升序返回。"""
    ids = [str(scheme.id) for scheme, _ in participants]
    out: list[RankedScheme] = []
    for position, (scheme, result) in enumerate(participants):
        item = topsis_result.schemes[position]
        dominators = pareto_result.dominated_by.get(position, [])
        out.append(
            RankedScheme(
                scheme_id=str(scheme.id),
                scheme_name=scheme.name,
                dimension_scores=[getattr(result.dimension_scores, key) for key in CRITERION_ORDER],
                closeness=item.closeness,
                rank=item.rank,
                is_non_dominated=position in pareto_result.non_dominated,
                dominated_by=[ids[d] for d in dominators],
                first_place_probability=acceptability.first_place_probability[position],
            )
        )
    # 名次升序；同名次时按贴近度降序，再按方案 id 稳定排。
    out.sort(key=lambda s: (s.rank, -s.closeness, s.scheme_id))
    return out


@router.get(
    "/rank/roles",
    summary="可用的角色权重模板",
)
def list_roles(project_id: int, session: SessionDep) -> dict[str, Any]:
    """列出可用的角色权重模板，供前端下拉框展示。

    ``roles`` 是 ``rules/weights.yaml`` 的内建四个角色；``custom_roles`` 是运行期
    添加的自定义模板（见 ``app/custom/``），两者并列可选。``project_id`` 只用于
    校验项目存在，模板本身是全局的。
    """
    _require_project(session, project_id)
    try:
        templates = get_role_templates()
    except WeightsLoadError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "角色权重模板加载失败，请跑 scripts/check_rules.py 修正",
                "problems": [p.message for p in exc.problems],
            },
        ) from exc
    custom_roles: list[dict[str, Any]] = []
    for row in list_templates(session):
        try:
            custom_roles.append(
                _weights_from_template(to_engine_template(row), is_custom=True).model_dump()
            )
        except CustomAddError:
            # 存量模板校验不过：不静默丢弃，标出来让使用者去删。
            custom_roles.append(
                {
                    "source": "role",
                    "criteria": list(CRITERION_ORDER),
                    "weights": [],
                    "role": f"custom:{row.id}",
                    "role_name": row.name,
                    "is_custom": True,
                    "note": "该自定义模板未通过引擎校验，请删除后重建",
                }
            )
    return {
        "criteria": list(CRITERION_ORDER),
        "roles": [_weights_from_template(t).model_dump() for t in templates.values()],
        "custom_roles": custom_roles,
        "needs_review": [key for key, t in templates.items() if t.needs_review],
    }
