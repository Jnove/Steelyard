"""Schema 路由：返回项目与方案的字段元信息。"""

from __future__ import annotations

from fastapi import APIRouter

from app.models import EvalResult, ProjectParams, SchemeParams
from app.schemas.meta import enriched_schema

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get(
    "",
    summary="返回项目与方案的字段 Schema（含中文 label / 单位 / 分组）",
)
def get_all_schemas() -> dict[str, dict]:
    """一次返回三种 schema：

    - ``project_params``：项目层参数
    - ``scheme_params``：方案层参数
    - ``eval_result``：评估结果（前端可在报告页用其渲染条目）
    """
    return {
        "project_params": enriched_schema(ProjectParams),
        "scheme_params": enriched_schema(SchemeParams),
        "eval_result": enriched_schema(EvalResult),
    }


@router.get("/project", summary="项目参数 schema")
def get_project_schema() -> dict:
    return enriched_schema(ProjectParams)


@router.get("/scheme", summary="方案参数 schema")
def get_scheme_schema() -> dict:
    return enriched_schema(SchemeParams)


@router.get("/eval", summary="评估结果 schema")
def get_eval_schema() -> dict:
    return enriched_schema(EvalResult)