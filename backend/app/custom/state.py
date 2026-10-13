"""Invalidate derived evidence in the same transaction as overlay changes."""

from sqlalchemy import delete
from sqlmodel import Session


def invalidate_results(session: Session, *, evaluation: bool = True) -> None:
    """Global overlays affect every project; leave source inputs and audit intact."""
    from app.agents.storage import AgentResultRow, ReportCacheRow
    from app.models import EvalResultRow

    if evaluation:
        session.exec(delete(EvalResultRow))
    session.exec(delete(AgentResultRow))
    session.exec(delete(ReportCacheRow))
