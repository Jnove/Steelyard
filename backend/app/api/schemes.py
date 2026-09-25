"""方案 CRUD 路由。

所有路径都在项目下：``/api/projects/{project_id}/schemes``。

约定：
- 方案名必填且项目内唯一；参数整体以 JSON 存。
- ``is_whatif`` 与 ``parent_id`` 用于 T8 的假设推演副本；列表默认不返回副本，
  可通过 ``?include_whatif=true`` 拉取全部。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, or_, select

from app.db import get_session
from app.models import Project, Scheme, SchemeParams

router = APIRouter(
    prefix="/projects/{project_id}/schemes",
    tags=["schemes"],
)


class SchemeCreate(BaseModel):
    """创建方案请求体。"""

    name: str = Field(min_length=1, max_length=200, description="方案名称（项目内唯一）")
    params: SchemeParams = Field(default_factory=SchemeParams)
    is_whatif: bool = Field(False, description="是否为假设推演副本（T8 用）")
    parent_id: int | None = Field(None, description="若为 what-if，指向所基于的原方案")


class SchemeUpdate(BaseModel):
    """更新方案请求体；未提供的字段保留原值。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    params: SchemeParams | None = None
    is_whatif: bool | None = None
    parent_id: int | None = None


class SchemeRead(BaseModel):
    """方案读取响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    params: SchemeParams
    is_whatif: bool
    parent_id: int | None
    created_at: datetime
    updated_at: datetime


def _to_read(scheme: Scheme) -> SchemeRead:
    return SchemeRead(
        id=scheme.id or 0,
        project_id=scheme.project_id,
        name=scheme.name,
        params=SchemeParams.model_validate(scheme.params or {}),
        is_whatif=scheme.is_whatif,
        parent_id=scheme.parent_id,
        created_at=scheme.created_at,
        updated_at=scheme.updated_at,
    )


SessionDep = Annotated[Session, Depends(get_session)]


def _require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在"
        )
    return project


def _ensure_unique_name(
    session: Session, project_id: int, name: str, exclude_id: int | None = None
) -> None:
    """校验方案名在项目内唯一。"""
    stmt = select(Scheme).where(
        Scheme.project_id == project_id, Scheme.name == name
    )
    if exclude_id is not None:
        stmt = stmt.where(Scheme.id != exclude_id)
    if session.exec(stmt).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"项目 {project_id} 内已存在同名方案 {name!r}",
        )


@router.post(
    "",
    response_model=SchemeRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增方案",
)
def create_scheme(
    project_id: int,
    payload: SchemeCreate,
    session: SessionDep,
) -> SchemeRead:
    _require_project(session, project_id)
    _ensure_unique_name(session, project_id, payload.name)
    if payload.is_whatif and payload.parent_id is not None:
        parent = session.get(Scheme, payload.parent_id)
        if parent is None or parent.project_id != project_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"parent_id {payload.parent_id} 不属于项目 {project_id}",
            )
    scheme = Scheme(
        project_id=project_id,
        name=payload.name,
        params=payload.params.model_dump(),
        is_whatif=payload.is_whatif,
        parent_id=payload.parent_id,
    )
    session.add(scheme)
    session.commit()
    session.refresh(scheme)
    return _to_read(scheme)


@router.get("", response_model=list[SchemeRead], summary="方案列表")
def list_schemes(
    project_id: int,
    session: SessionDep,
    include_whatif: Annotated[bool, Query(description="是否包含假设推演副本")] = False,
) -> list[SchemeRead]:
    _require_project(session, project_id)
    stmt = select(Scheme).where(Scheme.project_id == project_id)
    if not include_whatif:
        stmt = stmt.where(or_(Scheme.is_whatif == False, Scheme.is_whatif.is_(False)))  # noqa: E712
    stmt = stmt.order_by(Scheme.id)
    return [_to_read(s) for s in session.exec(stmt).all()]


@router.get("/{scheme_id}", response_model=SchemeRead, summary="方案详情")
def get_scheme(
    project_id: int,
    scheme_id: int,
    session: SessionDep,
) -> SchemeRead:
    _require_project(session, project_id)
    scheme = session.get(Scheme, scheme_id)
    if scheme is None or scheme.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"方案 {scheme_id} 不属于项目 {project_id}",
        )
    return _to_read(scheme)


@router.put("/{scheme_id}", response_model=SchemeRead, summary="更新方案")
def update_scheme(
    project_id: int,
    scheme_id: int,
    payload: SchemeUpdate,
    session: SessionDep,
) -> SchemeRead:
    _require_project(session, project_id)
    scheme = session.get(Scheme, scheme_id)
    if scheme is None or scheme.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"方案 {scheme_id} 不属于项目 {project_id}",
        )
    if payload.name is not None and payload.name != scheme.name:
        _ensure_unique_name(session, project_id, payload.name, exclude_id=scheme_id)
        scheme.name = payload.name
    if payload.params is not None:
        scheme.params = payload.params.model_dump()
    if payload.is_whatif is not None:
        scheme.is_whatif = payload.is_whatif
    if payload.parent_id is not None:
        parent = session.get(Scheme, payload.parent_id)
        if parent is None or parent.project_id != project_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"parent_id {payload.parent_id} 不属于项目 {project_id}",
            )
        scheme.parent_id = payload.parent_id
    scheme.updated_at = datetime.now(UTC)
    session.add(scheme)
    session.commit()
    session.refresh(scheme)
    return _to_read(scheme)


@router.delete(
    "/{scheme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除方案",
)
def delete_scheme(
    project_id: int,
    scheme_id: int,
    session: SessionDep,
) -> None:
    _require_project(session, project_id)
    scheme = session.get(Scheme, scheme_id)
    if scheme is None or scheme.project_id != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"方案 {scheme_id} 不属于项目 {project_id}",
        )
    from app.models.orm import EvalResultRow

    for ev in session.exec(
        select(EvalResultRow).where(EvalResultRow.scheme_id == scheme_id)
    ).all():
        session.delete(ev)
    session.delete(scheme)
    session.commit()