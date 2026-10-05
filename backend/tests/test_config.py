"""根目录 seed 与 backend 启动服务必须使用同一个默认数据库。"""

from pathlib import Path

import pytest
from app.config import BACKEND_ROOT, Settings


def test_default_database_is_independent_of_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    root_url = Settings(_env_file=None).database_url
    (tmp_path / "backend").mkdir()
    monkeypatch.chdir(tmp_path / "backend")
    backend_url = Settings(_env_file=None).database_url
    assert (
        root_url == backend_url == f"sqlite:///{(BACKEND_ROOT / 'data' / 'zhuheng.db').as_posix()}"
    )


def test_explicit_database_configuration_is_preserved() -> None:
    assert (
        Settings(_env_file=None, DATABASE_URL="sqlite:///:memory:").database_url
        == "sqlite:///:memory:"
    )
