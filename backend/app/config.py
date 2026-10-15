"""应用配置：通过 pydantic-settings 从环境变量 / .env 加载。

根目录与 backend/.env 均可配置；默认数据库固定在当前工作树的 backend/data。
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """运行时配置。

    字段名遵循 Agent.md 中约定的环境变量命名，方便部署侧统一管理。
    """

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # —— 运行环境：dev / prod。仅开发环境开放规则热重载等调试接口 ——
    app_env: Annotated[str, Field(default="dev", alias="APP_ENV")]

    # —— LLM 配置（默认走 fake 桩，便于本地无 Key 启动） ——
    llm_provider: Annotated[str, Field(default="fake", alias="LLM_PROVIDER")]
    llm_base_url: Annotated[str | None, Field(default=None, alias="LLM_BASE_URL")]
    llm_api_key: Annotated[str | None, Field(default=None, alias="LLM_API_KEY")]
    llm_model: Annotated[str | None, Field(default=None, alias="LLM_MODEL")]
    llm_reasoning_effort: Annotated[str, Field(default="", alias="LLM_REASONING_EFFORT")]

    # —— 数据库（SQLite 即可，演示规模足够） ——
    database_url: Annotated[
        str,
        Field(
            default=f"sqlite:///{(BACKEND_ROOT / 'data' / 'zhuheng.db').as_posix()}",
            alias="DATABASE_URL",
        ),
    ]

    # —— CORS：开发环境默认放行 Vite dev server ——
    cors_origins: Annotated[
        str,
        Field(default="http://localhost:5173", alias="CORS_ORIGINS"),
    ]

    @property
    def is_dev(self) -> bool:
        """是否开发环境。``POST /api/rules/reload`` 等调试接口只在这里放开。"""
        return self.app_env.strip().lower() in ("dev", "development", "local", "test")

    def cors_origins_list(self) -> list[str]:
        """把逗号分隔的字符串拆成列表，方便 CORSMiddleware 使用。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例获取 Settings，避免每次请求都读 .env。"""
    return Settings()
