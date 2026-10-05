"""规则查询与热重载路由。

- ``GET  /api/rules``        返回当前加载的规则与派生量定义，前端用来展示"评分依据"；
- ``POST /api/rules/reload`` 重新读 ``rules/*.yaml``，**仅开发环境可用**。

为什么要暴露规则定义：报告里每个结论都要能追到规则 ID 和 ``source``，
前端点开一条评分就该看到"这条分是按哪个分段折线算的、依据是什么"。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.engine.metrics import DERIVED_QUANTITIES
from app.engine.rules import RuleDef, RuleLoadError, get_ruleset, reload_ruleset

router = APIRouter(prefix="/rules", tags=["rules"])


class DerivedQuantityRead(BaseModel):
    """派生量的对外描述。"""

    name: str = Field(description="字段名，规则里直接引用")
    label: str = Field(description="中文名")
    unit: str = Field(description="单位；无量纲为 —")
    formula: str = Field(description="计算公式")
    deps: list[str] = Field(description="依赖的原始字段")
    note: str = Field("", description="说明")


class RuleRead(BaseModel):
    """一条规则的对外描述：规则本体 + 它来自哪个文件。"""

    model_config = ConfigDict(json_schema_extra={"title": "规则定义"})

    definition: RuleDef = Field(description="规则定义，字段含义见 rules/_template.yaml")
    source_file: str = Field(description="来自 rules/ 下的哪个文件")


class RulesResponse(BaseModel):
    """``GET /api/rules`` 响应。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "规则清单",
            "description": "当前加载的全部规则与派生量定义",
        }
    )

    rule_count: int = Field(description="规则总条数")
    hard_count: int = Field(description="硬约束条数")
    metric_count: int = Field(description="评分指标条数")
    rules: list[RuleRead] = Field(description="全部规则")
    derived_quantities: list[DerivedQuantityRead] = Field(description="全部派生量定义")
    todo_source_ids: list[str] = Field(
        description="source 里仍含 TODO 的规则 ID；这些规则的出处尚未落实，报告里应提示"
    )


def _build_response() -> RulesResponse:
    ruleset = get_ruleset()
    return RulesResponse(
        rule_count=len(ruleset.rules),
        hard_count=len(ruleset.hard_rules),
        metric_count=len(ruleset.metric_rules),
        rules=[
            RuleRead(definition=rule, source_file=ruleset.origins.get(rule.id, ""))
            for rule in ruleset.rules
        ],
        derived_quantities=[
            DerivedQuantityRead(
                name=q.name,
                label=q.label,
                unit=q.unit,
                formula=q.formula,
                deps=list(q.deps),
                note=q.note,
            )
            for q in DERIVED_QUANTITIES
        ],
        todo_source_ids=list(ruleset.todo_source_ids),
    )


@router.get("", response_model=RulesResponse, summary="当前规则与派生量定义")
def list_rules() -> RulesResponse:
    try:
        return _build_response()
    except RuleLoadError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "规则加载失败，请跑 scripts/check_rules.py 修正", "problems": exc.problems},
        ) from exc


@router.post("/reload", response_model=RulesResponse, summary="重新加载规则（仅开发环境）")
def reload_rules() -> RulesResponse:
    """热重载 ``rules/*.yaml``，改完规则不用重启服务。

    生产环境返回 403：规则变更应当走 Git 提交 + CI 校验，而不是在线上悄悄改。
    加载失败时保留原有规则集，服务不会因为一次写错规则而不可用。
    """
    if not get_settings().is_dev:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="规则热重载仅在开发环境可用（APP_ENV=dev）；生产环境请走 Git 提交与 CI 校验",
        )
    try:
        reload_ruleset()
    except RuleLoadError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "规则加载失败，已保留上一次成功加载的规则",
                "problems": exc.problems,
            },
        ) from exc
    return _build_response()
