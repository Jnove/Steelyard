"""报告缓存与最近一次智能体工具结果，SQLite 持久化支持离线与重启。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column
from sqlmodel import JSON, Field, SQLModel


class ReportCacheRow(SQLModel, table=True):
    __tablename__ = "agent_report_cache"
    key: str = Field(primary_key=True)
    project_id: int = Field(index=True)
    output: dict[str, Any] = Field(sa_column=Column(JSON))


class AgentResultRow(SQLModel, table=True):
    __tablename__ = "agent_results"
    project_id: int = Field(primary_key=True)
    fingerprint: str
    include_whatif: bool = False
    evaluation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ranking: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
