"""Schema 路由：返回项目与方案的字段元信息。"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.models import EvalResult, ProjectParams, SchemeParams
from app.schemas.merged import merged_schema
from app.schemas.meta import enriched_schema

router = APIRouter(prefix="/schema", tags=["schema"])

SessionDep = Annotated[Session, Depends(get_session)]


def _merged(session: Session | None, model: type[BaseModel]) -> dict[str, Any]:
    """内建基线 + 覆盖层（自定义选项、方案层的自定义字段）。

    实现在 ``app/schemas/merged.py``：Excel 的模板/导出/导入也走同一份，
    这样"界面上能填的字段"与"Excel 里能填的列"永远一致。
    ``session=None`` 表示只用内建基线（提交进仓库的产物必须走这条路）。
    """
    return merged_schema(session, model)


def build_all_schemas(session: Session | None = None) -> dict[str, dict]:
    """一次构造三种 schema。

    - ``project_params``：项目层参数
    - ``scheme_params``：方案层参数
    - ``eval_result``：评估结果（前端可在报告页用其渲染条目）

    开放枚举字段的候选值 = 内建候选值 + 使用者自定义选项（见 ``app/custom/``）。

    **为什么单独留一个不依赖请求的函数**：`scripts/export_frontend_fixtures.py` 与
    其它构建产物脚本要的是**只有内建基线**的 schema（`session=None`）——
    覆盖层内容是使用者运行期加的草稿，绝不能混进提交进 git 的前端产物，
    否则 CI 的 `git diff --exit-code` 就失去意义。HTTP 路由则始终传真实 session。
    """
    return {
        "project_params": _merged(session, ProjectParams),
        "scheme_params": _merged(session, SchemeParams),
        "eval_result": enriched_schema(EvalResult),
    }


@router.get(
    "",
    summary="返回项目与方案的字段 Schema（含中文 label / 单位 / 分组）",
)
def get_all_schemas(session: SessionDep) -> dict[str, dict]:
    """HTTP 入口：始终带 session，因此包含使用者的自定义内容。"""
    return build_all_schemas(session)


@router.get("/project", summary="项目参数 schema")
def get_project_schema(session: SessionDep) -> dict:
    return _merged(session, ProjectParams)


@router.get("/scheme", summary="方案参数 schema")
def get_scheme_schema(session: SessionDep) -> dict:
    return _merged(session, SchemeParams)


@router.get("/eval", summary="评估结果 schema")
def get_eval_schema() -> dict:
    return enriched_schema(EvalResult)