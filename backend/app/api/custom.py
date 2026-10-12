"""自定义添加的路由（覆盖层）。

分工与铁律见 ``docs/design-custom-add.md``：

- **读接口放开**：``GET`` 在生产也要能用，否则前端渲染不出使用者加的选项与模板；
- **写接口只在开发环境开放**：与 ``POST /api/rules/reload`` 同一口径——生产环境的规则
  与字段变更应当走 Git 提交 + CI 校验，而不是在线上悄悄改；
- 任何冲突（字段不允许扩展、重名、校验不过）都返回 **422 + 中文原因与改法**，
  措辞与 ``check_rules`` 保持一致，专业组看到的报错是同一套话。

``created_by`` 目前从可选的 ``X-Operator`` 头取，接入登录后替换成真实身份
（见 ``docs/open-items.md`` 的待办）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session

from app.config import get_settings
from app.custom import options as options_service
from app.custom import templates as templates_service
from app.custom.errors import CustomAddError
from app.custom.models import CustomOption, CustomWeightTemplate
from app.db import get_session
from app.engine.mcdm import AhpResult

router = APIRouter(prefix="/custom", tags=["custom"])

#: 422 的语义名在 Starlette 各版本间改过（UNPROCESSABLE_ENTITY → UNPROCESSABLE_CONTENT），
#: 直接写数字：既不会跟着依赖版本抖动，也不会触发弃用警告。
HTTP_422_UNPROCESSABLE = 422

SessionDep = Annotated[Session, Depends(get_session)]
OperatorDep = Annotated[str | None, Header(alias="X-Operator")]


def _require_dev() -> None:
    """写接口的环境闸门：生产环境一律 403。"""
    if not get_settings().is_dev:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=(
                "自定义添加只在开发环境可用（APP_ENV=dev）；"
                "生产环境请把定稿内容导出后走 Git 提交与 CI 校验"
            ),
        )


def _raise_custom(exc: CustomAddError) -> None:
    """把覆盖层的校验失败转成 422，并把中文改法一并返回。"""
    raise HTTPException(
        HTTP_422_UNPROCESSABLE,
        detail={
            "message": str(exc),
            "problems": [
                {"code": p.code, "message": p.message, "fix": p.fix} for p in exc.problems
            ],
        },
    ) from exc


# —— 读模型 —— #


class CustomOptionRead(BaseModel):
    """一个自定义枚举选项。"""

    model_config = ConfigDict(json_schema_extra={"title": "自定义枚举选项"})

    id: int = Field(description="选项 id，删除时用")
    field: str = Field(description="挂在哪个字段上")
    value: str = Field(description="选项文本")
    sort: int = Field(description="展示顺序")
    created_at: datetime = Field(description="创建时间（UTC）")
    created_by: str | None = Field(None, description="创建者标识；未接入登录时可能为空")


class ExtensibleFieldRead(BaseModel):
    """一个开放枚举字段，以及它当前的全部候选值。"""

    model_config = ConfigDict(json_schema_extra={"title": "开放枚举字段"})

    name: str = Field(description="字段名")
    label: str = Field(description="中文名")
    group: str = Field(description="所属表单分组")
    builtin: list[str] = Field(description="内建候选值；不可删除")
    custom: list[CustomOptionRead] = Field(description="使用者添加的候选值，可删除")


class OptionsResponse(BaseModel):
    """``GET /api/custom/options`` 响应。"""

    model_config = ConfigDict(
        json_schema_extra={
            "title": "自定义选项清单",
            "description": "只有开放枚举字段会出现在这里；封闭枚举不允许扩展",
        }
    )

    fields: list[ExtensibleFieldRead] = Field(description="全部开放枚举字段")


class WeightTemplateRead(BaseModel):
    """一个自定义角色权重模板。"""

    model_config = ConfigDict(json_schema_extra={"title": "自定义权重模板"})

    id: int = Field(description="模板 id，删除时用")
    key: str = Field(description="排序接口里引用它的键，形如 custom:3")
    name: str = Field(description="模板名，前端下拉框显示")
    note: str = Field("", description="这个立场为什么这么排")
    source: str = Field("", description="数值出处")
    weights: list[float] = Field(description="四个维度的归一化权重")
    matrix: list[list[float]] | None = Field(None, description="两两比较矩阵；直接给权重时为 null")
    ahp: AhpResult | None = Field(
        None, description="矩阵来源才有的一致性检验结果；直接给权重时为 null"
    )
    consistency_warning: str | None = Field(
        None, description="CR 超限时的中文提示；新增时已拒绝超限矩阵，故通常为空"
    )
    created_at: datetime = Field(description="创建时间（UTC）")
    created_by: str | None = Field(None, description="创建者标识")


class WeightTemplateCreate(BaseModel):
    """新增自定义模板的请求体。``weights`` / ``matrix`` 二选一。"""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "title": "新增自定义权重模板",
            "description": "weights 与 matrix 必须且只能提供一项；矩阵元素可写 1/3 这样的分数",
        },
    )

    name: str = Field(description="模板名；不得与内建角色键或已有模板重名")
    note: str = Field("", description="这个立场为什么这么排")
    source: str = Field("", description="数值出处；写上规范编号或「经验规则（…组）：理由」")
    weights: list[Any] | None = Field(
        None, description="四个维度的相对权重（会自动归一化），顺序同 CRITERION_ORDER"
    )
    matrix: list[list[Any]] | None = Field(
        None, description="4×4 两两比较矩阵；分数写成 1/3，不要写 0.33"
    )


class OptionsCreate(BaseModel):
    """新增自定义枚举选项的请求体。"""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"title": "新增自定义选项"})

    field: str = Field(description="开放枚举字段名，当前支持 risk_features / irregularity_items")
    value: str = Field(description="选项文本")


# —— 组装 —— #


def _option_read(row: CustomOption) -> CustomOptionRead:
    return CustomOptionRead(
        id=row.id or 0,
        field=row.field,
        value=row.value,
        sort=row.sort,
        created_at=row.created_at,
        created_by=row.created_by,
    )


def _template_read(row: CustomWeightTemplate) -> WeightTemplateRead:
    """读出模板并重算一次（引擎的校验器是唯一权威）。"""
    engine_template = templates_service.to_engine_template(row)
    return WeightTemplateRead(
        id=row.id or 0,
        key=engine_template.key,
        name=engine_template.name,
        note=engine_template.note,
        source=engine_template.source,
        weights=engine_template.weights,
        matrix=engine_template.matrix,
        ahp=engine_template.ahp,
        consistency_warning=None,
        created_at=row.created_at,
        created_by=row.created_by,
    )


# —— 枚举选项 —— #


@router.get("/options", response_model=OptionsResponse, summary="开放枚举字段与自定义选项")
def list_custom_options(session: SessionDep) -> OptionsResponse:
    fields = options_service.extensible_fields()
    rows = options_service.list_options(session)
    grouped: dict[str, list[CustomOptionRead]] = {}
    for row in rows:
        grouped.setdefault(row.field, []).append(_option_read(row))
    return OptionsResponse(
        fields=[
            ExtensibleFieldRead(
                name=name,
                label=info["label"],
                group=info["group"],
                builtin=info["builtin"],
                custom=grouped.get(name, []),
            )
            for name, info in sorted(fields.items())
        ]
    )


@router.post(
    "/options",
    response_model=CustomOptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增自定义枚举选项（仅开发环境）",
)
def create_custom_option(
    payload: OptionsCreate,
    session: SessionDep,
    operator: OperatorDep = None,
    _: None = Depends(_require_dev),
) -> CustomOptionRead:
    try:
        row = options_service.add_option(
            session, field=payload.field, value=payload.value, created_by=operator
        )
    except CustomAddError as exc:
        _raise_custom(exc)
    return _option_read(row)


@router.delete(
    "/options/{option_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自定义枚举选项（仅开发环境）",
)
def delete_custom_option(
    option_id: int,
    session: SessionDep,
    _: None = Depends(_require_dev),
) -> Response:
    try:
        options_service.delete_option(session, option_id)
    except CustomAddError as exc:
        _raise_custom(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# —— 角色权重模板 —— #


@router.get(
    "/weight-templates",
    response_model=list[WeightTemplateRead],
    summary="自定义角色权重模板清单",
)
def list_custom_templates(session: SessionDep) -> list[WeightTemplateRead]:
    return [_template_read(row) for row in templates_service.list_templates(session)]


@router.post(
    "/weight-templates",
    response_model=WeightTemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="新增自定义角色权重模板（仅开发环境）",
)
def create_custom_template(
    payload: WeightTemplateCreate,
    session: SessionDep,
    operator: OperatorDep = None,
    _: None = Depends(_require_dev),
) -> WeightTemplateRead:
    try:
        row = templates_service.add_template(
            session,
            name=payload.name,
            note=payload.note,
            source=payload.source,
            weights=payload.weights,
            matrix=payload.matrix,
            created_by=operator,
        )
    except CustomAddError as exc:
        _raise_custom(exc)
    return _template_read(row)


@router.delete(
    "/weight-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除自定义角色权重模板（仅开发环境）",
)
def delete_custom_template(
    template_id: int,
    session: SessionDep,
    _: None = Depends(_require_dev),
) -> Response:
    try:
        templates_service.delete_template(session, template_id)
    except CustomAddError as exc:
        _raise_custom(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
