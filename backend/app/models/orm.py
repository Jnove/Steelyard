"""SQLModel 持久化表。

设计要点：
- 项目名 / 方案名各自独立（``Project.name`` / ``Scheme.name``），不混入 ``params``。
- 方案参数整体以 JSON 列存储，字段频繁调整时无需改表结构；
  读取时用 ``SchemeParams`` 重新校验。
- 方案的 what-if 元信息（``is_whatif`` / ``parent_id``）放在表顶层，
  方便按是否副本过滤。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


def _utcnow() -> datetime:
    """统一 UTC 时间，便于跨时区对齐。"""
    return datetime.now(UTC)


class Project(SQLModel, table=True):
    """项目记录（地块条件）。"""

    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(description="项目名称", max_length=200)
    params: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="ProjectParams 序列化后的 JSON 对象",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Scheme(SQLModel, table=True):
    """方案记录（一个候选方案）。"""

    __tablename__ = "schemes"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(
        foreign_key="projects.id",
        index=True,
        description="所属项目 id",
    )
    name: str = Field(description="方案名称", max_length=200)
    params: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="SchemeParams 序列化后的 JSON 对象",
    )
    is_whatif: bool = Field(
        default=False,
        index=True,
        description="是否为假设推演副本（T8 用），默认 false",
    )
    parent_id: int | None = Field(
        default=None,
        foreign_key="schemes.id",
        description="若为 what-if，指向所基于的原方案",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class EvalResultRow(SQLModel, table=True):
    """评估结果记录。

    当前阶段只把 ``EvalResult`` 序列化为 JSON 整体存；后续若要按指标检索，
    再考虑拆出独立的指标 / 合规明细表。
    """

    __tablename__ = "eval_results"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    scheme_id: int = Field(foreign_key="schemes.id", index=True)
    result: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="EvalResult 序列化后的 JSON 对象",
    )
    created_at: datetime = Field(default_factory=_utcnow)