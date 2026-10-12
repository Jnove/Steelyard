"""自定义内容的持久化表（覆盖层）。

与 ``app/models/orm.py`` 的分工：那边存业务数据（项目 / 方案 / 评估结果），
这里存**使用者自己加的东西**。两者都挂在同一个 SQLite 上，但语义完全不同：
删掉这里的记录，系统应当回到与"纯内建"完全一致的行为。

新增表的模块必须在 ``app.db.register_table_models()`` 里登记，
否则 ``create_all`` 看不见它（测试用的是内存库，漏登记会表现为"表不存在"）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, UniqueConstraint
from sqlmodel import JSON, Field, SQLModel


def _utcnow() -> datetime:
    """统一 UTC 时间，便于跨时区对齐。"""
    return datetime.now(UTC)


class CustomOption(SQLModel, table=True):
    """自定义枚举选项：给**开放枚举**字段追加候选值。

    只允许挂在模型里标记了 ``extensible=True`` 的字段上（当前是 ``risk_features``
    与 ``irregularity_items``）。``structure_type`` 这类**封闭枚举**一律拒绝——
    规则会按它的取值分支，多一个规则不认识的取值会让那些规则静默失效。
    """

    __tablename__ = "custom_options"
    __table_args__ = (UniqueConstraint("field", "value", name="uq_custom_option_field_value"),)

    id: int | None = Field(default=None, primary_key=True)
    field: str = Field(index=True, description="挂在哪个字段上，如 risk_features")
    value: str = Field(description="选项文本，展示与存储都用它")
    sort: int = Field(default=0, description="展示顺序，越小越靠前")
    created_at: datetime = Field(default_factory=_utcnow)
    created_by: str | None = Field(default=None, description="创建者标识；接入登录后替换")


class CustomWeightTemplate(SQLModel, table=True):
    """自定义角色权重模板：与 ``rules/weights.yaml`` 的四个角色**并列**可选。

    ``weights`` 与 ``matrix`` 至少有一个：直接给权重时后者为 null，
    给两两比较矩阵时两者都有（``weights`` 存解出来的归一化权重，便于直接展示）。
    """

    __tablename__ = "custom_weight_templates"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(
        index=True,
        unique=True,
        description="模板名，前端下拉框显示；不得与内建角色键重名",
    )
    note: str = Field(default="", description="这个立场为什么这么排；报告里可直接引用")
    source: str = Field(default="", description="数值出处；含 TODO 表示尚未核定")
    weights: list[float] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="四个维度的归一化权重，顺序同 CRITERION_ORDER",
    )
    matrix: list[list[Any]] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="两两比较矩阵（原样存，读取时重算以保证与校验器一致）；直接给权重时为 null",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    created_by: str | None = Field(default=None, description="创建者标识；接入登录后替换")
