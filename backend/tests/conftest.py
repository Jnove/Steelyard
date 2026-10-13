"""测试用 fixture：内存 SQLite + 干净的表结构 + 替换全局引擎。

要点：
- ``override_engine_for_testing`` 让 FastAPI 的 lifespan 不会去碰真实文件。
- 每个测试独立的 StaticPool 内存库，结束后销毁，保证隔离。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from app.db import get_session, override_engine_for_testing, register_table_models
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def engine() -> Iterator[Any]:
    """每个测试一个新的内存 SQLite。"""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 表模块集中登记在 app.db 里，避免测试与生产两条路径漏掉同一张表。
    register_table_models()
    SQLModel.metadata.create_all(eng)
    override_engine_for_testing(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture
def client(engine: Any) -> Iterator[TestClient]:
    """把 FastAPI 的数据库依赖指向测试 engine。"""

    def _override_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()