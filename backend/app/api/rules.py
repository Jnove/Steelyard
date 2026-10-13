"""规则查询与热重载路由。

- ``GET  /api/rules``        返回当前加载的规则与派生量定义，前端用来展示"评分依据"；
- ``POST /api/rules/reload`` 重新读 ``rules/*.yaml``，**仅开发环境可用**。

返回的是**当前生效**的规则集：内建规则（``rules/*.yaml``）在前，运行期自定义的规则
（覆盖层，见 ``app/custom/rules.py``）在后。自定义规则的 ``source_file`` 固定为
"（界面自定义）"，前端可据此打标——它们没有进入 git，也不参与 CI 校验。

为什么要暴露规则定义：报告里每个结论都要能追到规则 ID 和 ``source``，
前端点开一条评分就该看到"这条分是按哪个分段折线算的、依据是什么"。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.config import get_settings
from app.custom.errors import CustomAddError
from app.custom.rules import ruleset_with_custom
from app.db import get_session
from app.engine.metrics import DERIVED_QUANTITIES
from app.engine.rules import RuleDef, RuleLoadError, reload_ruleset

router = APIRouter(prefix="/rules", tags=["rules"])

SessionDep = Annotated[Session, Depends(get_session)]


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


def _build_response(session: Session | None) -> RulesResponse:
    ruleset = ruleset_with_custom(session)
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


def build_rules_response(session: Session | None = None) -> RulesResponse:
    """构造规则清单响应。

    ``session=None`` 表示**只要内建规则**（不带运行期自定义规则）：构建产物脚本
    （``scripts/export_frontend_fixtures.py``）走这条路，确保提交进 git 的前端快照
    只含内建规则。HTTP 路由始终传真实 session 以合并使用者的自定义规则。
    """
    return _build_response(session)


@router.get("", response_model=RulesResponse, summary="当前规则与派生量定义")
def list_rules(session: SessionDep) -> RulesResponse:
    try:
        return build_rules_response(session)
    except RuleLoadError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "规则加载失败，请跑 scripts/check_rules.py 修正", "problems": exc.problems},
        ) from exc
    except CustomAddError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "自定义规则校验失败，请在自定义页面修正或删除",
                "problems": [
                    {"code": p.code, "message": p.message, "fix": p.fix} for p in exc.problems
                ],
            },
        ) from exc


@router.post("/reload", response_model=RulesResponse, summary="重新加载规则（仅开发环境）")
def reload_rules(session: SessionDep) -> RulesResponse:
    """热重载 ``rules/*.yaml``，改完规则不用重启服务。

    生产环境返回 403：规则变更应当走 Git 提交 + CI 校验，而不是在线上悄悄改。
    加载失败时保留原有规则集，服务不会因为一次写错规则而不可用。
    运行期的自定义规则不受影响（它们不在文件里）。
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
    return _build_response(session)
