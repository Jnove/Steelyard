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

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, or_, select

from app.db import get_session
from app.excel import ParseError, parse_workbook
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


# —— 批量导入（从 xlsx）—— #


class ImportErrorItem(BaseModel):
    """单条导入错误（与 ``app.excel.ParseError`` 对应的 API 形态）。"""

    scheme: str | None = Field(None, description="出错方案名；项目层错误为 null")
    field: str | None = Field(None, description="出错字段的英文名")
    label: str = Field(description="字段中文名")
    message: str = Field(description="面向用户的错误说明")


class ImportCreatedItem(BaseModel):
    """成功创建的方案记录。"""

    id: int
    name: str = Field(description="实际写入的方案名（已做项目内唯一化）")


class ImportResponse(BaseModel):
    """导入结果。"""

    created: list[ImportCreatedItem] = Field(default_factory=list)
    errors: list[ImportErrorItem] = Field(default_factory=list)
    project_params_updated: bool = Field(
        False, description="是否顺便把 xlsx 里的项目参数写入了空项目"
    )


def _to_error_item(err: ParseError) -> ImportErrorItem:
    return ImportErrorItem(
        scheme=err.scheme, field=err.field, label=err.label, message=err.message
    )


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="从 xlsx 批量导入方案（multipart/form-data，字段名 file）",
)
def import_schemes(
    project_id: int,
    file: Annotated[UploadFile, File(description="xlsx 文件")],
    allow_partial: Annotated[
        bool, Query(description="是否允许部分成功（失败的方案跳过）")
    ] = False,
    session: SessionDep = None,  # type: ignore[assignment]
) -> ImportResponse:
    """从 Excel 模板导入项目参数与方案。

    - 默认行为：xlsx 里有任何错误就整个拒绝，不写数据库；返回 422。
    - ``?allow_partial=true``：把能成功创建的方案写入数据库，跳过有错误的方案；
      返回 200，并在 ``errors`` 字段给出被跳过的清单。
    """
    _require_project(session, project_id)  # type: ignore[arg-type]
    project = session.get(Project, project_id)  # type: ignore[arg-type]
    assert project is not None  # _require_project 已经检查过

    content = file.file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="上传的文件为空",
        )
    try:
        result = parse_workbook(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"无法解析 xlsx：{exc}",
        ) from exc

    if result.errors and not allow_partial:
        # 整文件拒绝
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "errors": [_to_error_item(e).model_dump() for e in result.errors],
            },
        )

    if not result.schemes:
        # 没有任何方案列
        if result.errors:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "errors": [_to_error_item(e).model_dump() for e in result.errors],
                },
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="xlsx 里没有任何方案列（方案A-方案F 都为空）",
        )

    # 若项目层原本为空，把 xlsx 里的项目参数顺带写入
    project_params_updated = False
    if result.project_params and not project.params:
        project.params = result.project_params
        project.updated_at = datetime.now(UTC)
        session.add(project)
        project_params_updated = True

    errors_by_scheme: dict[str, list[ParseError]] = {}
    for e in result.errors:
        if e.scheme is None:
            continue
        errors_by_scheme.setdefault(e.scheme, []).append(e)

    created_items: list[ImportCreatedItem] = []
    skipped_errors: list[ImportErrorItem] = []

    for scheme_data in result.schemes:
        name = scheme_data["name"]
        scheme_errors = errors_by_scheme.get(name, [])
        if scheme_errors:
            for e in scheme_errors:
                skipped_errors.append(_to_error_item(e))
            continue
        # 项目内唯一化
        unique = name
        existing_names = {
            s.name
            for s in session.exec(
                select(Scheme).where(Scheme.project_id == project_id)
            ).all()
        }
        if unique in existing_names:
            n = 2
            while f"{unique} ({n})" in existing_names:
                n += 1
            unique = f"{unique} ({n})"
        try:
            params = SchemeParams.model_validate(scheme_data["params"])
        except Exception as exc:  # noqa: BLE001
            skipped_errors.append(
                ImportErrorItem(
                    scheme=name,
                    field=None,
                    label="方案参数",
                    message=f"参数校验失败：{exc}",
                )
            )
            continue
        scheme = Scheme(
            project_id=project_id,
            name=unique,
            params=params.model_dump(),
        )
        session.add(scheme)
        session.flush()  # 拿到 id
        created_items.append(ImportCreatedItem(id=scheme.id or 0, name=unique))

    session.commit()

    return ImportResponse(
        created=created_items,
        errors=skipped_errors,
        project_params_updated=project_params_updated,
    )