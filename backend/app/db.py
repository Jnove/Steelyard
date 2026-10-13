"""数据库引擎与会话管理。

使用 SQLite + SQLModel，演示规模够用。生产部署可换 PostgreSQL，
仅需改 ``DATABASE_URL``，无需改业务代码。

引擎构造是 lazy 的：默认从 settings 读，测试可以通过
``app.db.override_engine_for_testing`` 注入内存 SQLite，避免依赖文件路径。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_engine: Engine | None = None


def _build_engine(url: str) -> Engine:
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # sqlite:///./relative/path.db —— 相对 CWD。
        # 生产路径 ./data/zhuheng.db 落在 backend/ 下的 data/，由本地约定保证存在；
        # 演示场景若目录缺失，自动创建父目录。
        from pathlib import Path

        # 把 ``sqlite:///./foo`` / ``sqlite:////abs/foo`` 都转成本地路径
        path_part = url.split("///", 1)[1]
        if not path_part.startswith("/"):  # 相对路径
            target = Path.cwd() / path_part
        else:  # 绝对路径
            target = Path(path_part)
        target.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, echo=False, connect_args=connect_args)


def get_engine() -> Engine:
    """获取（或首次创建）全局引擎。"""
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def override_engine_for_testing(engine: Engine) -> None:
    """测试 fixture 用：把全局引擎替换为内存 / 临时 SQLite。"""
    global _engine
    _engine = engine


def register_table_models() -> None:
    """导入所有声明了 ``table=True`` 的模块，确保 ``create_all`` 能看到它们。

    **新增表模块时必须在这里加一行。** 漏登记的表现很隐蔽：新表在测试用的内存库里
    根本不存在，报出来的是 "no such table"，而不是"忘了导入"。
    """
    from app.agents.storage import AgentResultRow, ReportCacheRow  # noqa: F401
    from app.custom.models import (  # noqa: F401
        CustomAudit,
        CustomField,
        CustomOption,
        CustomRule,
        CustomWeightTemplate,
    )
    from app.models.orm import EvalResultRow, Project, Scheme  # noqa: F401


def init_db() -> None:
    """建表（仅创建不存在的；生产应改用迁移工具如 Alembic）。"""
    register_table_models()
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：每次请求一个 Session，结束自动关闭。"""
    with Session(get_engine()) as session:
        yield session
