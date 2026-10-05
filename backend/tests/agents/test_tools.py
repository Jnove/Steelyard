"""变更校验、项目隔离与结果过期防护。"""

from __future__ import annotations

import pytest
from app.agents.tools import AgentTools
from app.models import Project, Scheme
from fastapi import HTTPException
from sqlalchemy.engine import Engine
from sqlmodel import Session, select


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("is_whatif", True),
        ("parent_id", 1),
        ("unknown", 3),
        ("std_floor_repeat", 82),
        ("std_floor_repeat", True),
        ("std_floor_repeat", float("nan")),
        ("window_wall_ratio", {"南": 2}),
        ("window_wall_ratio", {"南": -0.2}),
        ("window_wall_ratio", {"南": 101}),
        ("unit_mix", {"一居": -1}),
        ("floor_height", -1),
    ],
)
def test_invalid_change_has_no_side_effect(
    engine: Engine, mock_project: tuple[int, list[int]], field: str, value: object
) -> None:
    project, ids = mock_project
    with pytest.raises(ValueError):
        AgentTools(engine, project).call(
            "update_scheme_param", {"scheme_id": ids[0], "field": field, "value": value}
        )
    with Session(engine) as session:
        assert not session.exec(select(Scheme).where(Scheme.is_whatif == True)).all()  # noqa: E712


def test_cross_project_blocked(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, ids = mock_project
    with Session(engine) as session:
        other = Project(name="另一个项目")
        session.add(other)
        session.commit()
        assert other.id is not None
        tools = AgentTools(engine, other.id)
        with pytest.raises(ValueError, match="当前项目"):
            tools.call(
                "update_scheme_param", {"scheme_id": ids[0], "field": "floor_height", "value": 3.0}
            )
        with pytest.raises(ValueError, match="当前项目"):
            tools.call("get_result", {"project_id": project})


def test_read_latest_rank_and_stale_result(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, ids = mock_project
    tools = AgentTools(engine, project)
    tools.call("evaluate", {"project_id": project})
    ranking = tools.call("rank", {"project_id": project, "weights": [0.25] * 4})
    assert tools.call("get_result", {"project_id": project})["ranking"] == ranking
    with Session(engine) as session:
        scheme = session.get(Scheme, ids[0])
        scheme.params = {**scheme.params, "floor_height": 3.5}
        session.add(scheme)
        session.commit()
    with pytest.raises(HTTPException) as error:
        tools.call("get_result", {"project_id": project})
    assert error.value.status_code == 409
    tools.call("evaluate", {"project_id": project})
    assert tools.call("get_result", {"project_id": project})["evaluation"]["results"]


def test_rules_and_stub(engine: Engine, mock_project: tuple[int, list[int]]) -> None:
    project, _ = mock_project
    tools = AgentTools(engine, project)
    rule = tools.call("explain_metric", {"rule_id": "K-01"})
    assert rule["formula"] and rule["source"]
    assert tools.call("search_clause", {"query": "条文", "k": 3}) == []
    with pytest.raises(ValueError):
        tools.call("search_clause", {"query": "条文", "k": 100})


def test_rank_requires_evaluated_candidate_set(
    engine: Engine, mock_project: tuple[int, list[int]]
) -> None:
    project, ids = mock_project
    tools = AgentTools(engine, project)
    tools.call("evaluate", {"project_id": project})
    tools.call("update_scheme_param", {"scheme_id": ids[0], "field": "floor_height", "value": 3.5})
    with pytest.raises(HTTPException) as error:
        tools.call("rank", {"project_id": project, "weights": [0.25] * 4, "include_whatif": True})
    assert error.value.status_code == 409
