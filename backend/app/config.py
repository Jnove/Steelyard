"""应用配置：通过 pydantic-settings 从环境变量 / .env 加载。

T1 阶段只暴露基础设施相关字段；LLM、数据库等真实接入在后续任务中加入。
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置。

    字段名遵循 AGENTS.md 中约定的环境变量命名，方便部署侧统一管理。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # —— LLM 配置（默认走 fake 桩，便于本地无 Key 启动） ——
    llm_provider: Annotated[str, Field(default="fake", alias="LLM_PROVIDER")]
    llm_base_url: Annotated[str | None, Field(default=None, alias="LLM_BASE_URL")]
    llm_api_key: Annotated[str | None, Field(default=None, alias="LLM_API_KEY")]
    llm_model: Annotated[str | None, Field(default=None, alias="LLM_MODEL")]

    # —— 数据库（SQLite 即可，演示规模足够） ——
    database_url: Annotated[
        str,
        Field(default="sqlite:///./data/zhuheng.db", alias="DATABASE_URL"),
    ]

    # —— CORS：开发环境默认放行 Vite dev server ——
    cors_origins: Annotated[
        str,
        Field(default="http://localhost:5173", alias="CORS_ORIGINS"),
    ]

    def cors_origins_list(self) -> list[str]:
        """把逗号分隔的字符串拆成列表，方便 CORSMiddleware 使用。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """单例获取 Settings，避免每次请求都读 .env。"""
    return Settings()