"""Schema 路由：返回项目与方案的字段元信息。"""

from __future__ import annotations

import copy
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.custom.options import merge_into_schema
from app.db import get_session
from app.models import EvalResult, ProjectParams, SchemeParams
from app.schemas.meta import enriched_schema

router = APIRouter(prefix="/schema", tags=["schema"])

SessionDep = Annotated[Session, Depends(get_session)]


def _merged(session: Session, model: type[BaseModel]) -> dict[str, Any]:
    """内建增强 schema + 覆盖层的自定义选项。

    深拷贝一层再合并：``enriched_schema`` 的返回值不应该被就地改写，
    否则"内建基线"会被悄悄带上使用者加的值。
    """
    return merge_into_schema(session, copy.deepcopy(enriched_schema(model)))


@router.get(
    "",
    summary="返回项目与方案的字段 Schema（含中文 label / 单位 / 分组）",
)
def get_all_schemas(session: SessionDep) -> dict[str, dict]:
    """一次返回三种 schema：

    - ``project_params``：项目层参数
    - ``scheme_params``：方案层参数
    - ``eval_result``：评估结果（前端可在报告页用其渲染条目）

    开放枚举字段的候选值 = 内建候选值 + 使用者自定义选项（见 ``app/custom/``）。
    """
    return {
        "project_params": _merged(session, ProjectParams),
        "scheme_params": _merged(session, SchemeParams),
        "eval_result": enriched_schema(EvalResult),
    }


@router.get("/project", summary="项目参数 schema")
def get_project_schema(session: SessionDep) -> dict:
    return _merged(session, ProjectParams)


@router.get("/scheme", summary="方案参数 schema")
def get_scheme_schema(session: SessionDep) -> dict:
    return _merged(session, SchemeParams)


@router.get("/eval", summary="评估结果 schema")
def get_eval_schema() -> dict:
    return enriched_schema(EvalResult)