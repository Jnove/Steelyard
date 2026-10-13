"""读取当前字段注册表的 Excel 模板与方案导出，不改变数据库。"""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from app.db import get_session
from app.excel import write_export, write_template
from app.models import Project, Scheme

router = APIRouter(prefix="/excel", tags=["excel"])
SessionDep = Annotated[Session, Depends(get_session)]
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/template", summary="下载含当前自定义字段的方案录入模板")
def template(session: SessionDep) -> Response:
    with TemporaryDirectory(prefix="steelyard-excel-") as directory:
        path = write_template(Path(directory) / "template.xlsx", session=session)
        return _download(path.read_bytes(), "steelyard-template.xlsx")


@router.get("/projects/{project_id}/export", summary="导出项目方案及当前自定义字段")
def export_project(project_id: int, session: SessionDep) -> Response:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail=f"项目 {project_id} 不存在")
    rows = session.exec(
        select(Scheme).where(Scheme.project_id == project_id).order_by(Scheme.id)
    ).all()
    schemes = [{"name": row.name, "params": row.params} for row in rows if not row.is_whatif]
    with TemporaryDirectory(prefix="steelyard-excel-") as directory:
        path = write_export(
            Path(directory) / "export.xlsx", project.params or {}, schemes, session=session
        )
        return _download(path.read_bytes(), f"steelyard-project-{project_id}.xlsx")
