"""按项目状态缓存已校验的建议问题；复用项目派生结果的清理生命周期。"""
from __future__ import annotations

from time import time

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.agents.storage import ReportCacheRow
from app.agents.suggestions import QuestionSuggestions

TTL_SECONDS = 300
PREFIX = "questions:"


def read(engine: Engine, key: str) -> QuestionSuggestions | None:
    with Session(engine) as session:
        row = session.get(ReportCacheRow, key)
        if row and row.output.get("expires_at", 0) > time():
            try:
                return QuestionSuggestions.model_validate(row.output["suggestions"])
            except (ValueError, KeyError):
                pass
    return None


def write(engine: Engine, project_id: int, key: str, result: QuestionSuggestions) -> None:
    with Session(engine) as session:
        rows = session.exec(select(ReportCacheRow).where(ReportCacheRow.project_id == project_id,
                                                       ReportCacheRow.key.startswith(PREFIX))).all()
        for row in rows:
            if row.key != key and row.output.get("expires_at", 0) <= time():
                session.delete(row)
        row = session.get(ReportCacheRow, key) or ReportCacheRow(key=key, project_id=project_id, output={})
        output = {"expires_at": time() + TTL_SECONDS, "suggestions": result.model_dump()}
        row.output = output
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            row = session.get(ReportCacheRow, key)
            if row is None:
                raise
            row.output = output
            session.add(row)
            session.commit()
