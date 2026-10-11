"""项目 CRUD 路由。

POST/GET/PUT/DELETE /api/projects[/{id}]
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, delete, select

from app.db import get_session
from app.models import Project, ProjectParams

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    """创建项目请求体。"""

    name: str = Field(min_length=1, max_length=200, description="项目名称")
    params: ProjectParams = Field(default_factory=ProjectParams)


class ProjectUpdate(BaseModel):
    """更新项目请求体；所有字段可选，未提供则保留原值。"""

    name: str | None = Field(None, min_length=1, max_length=200)
    params: ProjectParams | None = None


class ProjectRead(BaseModel):
    """项目读取响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    params: ProjectParams
    created_at: datetime
    updated_at: datetime


def _to_read(project: Project) -> ProjectRead:
    """ORM → 响应模型；``params`` 走 ``ProjectParams`` 重新校验，未来加字段更稳。"""
    return ProjectRead(
        id=project.id or 0,
        name=project.name,
        params=ProjectParams.model_validate(project.params or {}),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建项目",
)
def create_project(payload: ProjectCreate, session: SessionDep) -> Project:
    project = Project(name=payload.name, params=payload.params.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return _to_read(project)  # type: ignore[return-value]


@router.get("", response_model=list[ProjectRead], summary="项目列表")
def list_projects(session: SessionDep) -> list[ProjectRead]:
    rows = session.exec(select(Project).order_by(Project.id)).all()
    return [_to_read(p) for p in rows]


@router.get("/{project_id}", response_model=ProjectRead, summary="项目详情")
def get_project(project_id: int, session: SessionDep) -> ProjectRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在")
    return _to_read(project)


@router.put("/{project_id}", response_model=ProjectRead, summary="更新项目")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: SessionDep,
) -> ProjectRead:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在")
    if payload.name is not None:
        project.name = payload.name
    if payload.params is not None:
        project.params = payload.params.model_dump()
    project.updated_at = datetime.now(UTC)
    session.add(project)
    session.commit()
    session.refresh(project)
    return _to_read(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除项目（含方案、评估与报告缓存）",
)
def delete_project(project_id: int, session: SessionDep) -> None:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"项目 {project_id} 不存在")
    # 同一事务内先清缓存与评估，再删方案和项目；避免项目 id 复用读到旧结果。
    from app.agents.storage import AgentResultRow, ReportCacheRow
    from app.models.orm import EvalResultRow, Scheme

    for table in (ReportCacheRow, AgentResultRow, EvalResultRow, Scheme):
        session.exec(delete(table).where(table.project_id == project_id))
    session.delete(project)
    session.commit()
