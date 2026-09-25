"""筑衡后端 FastAPI 应用入口。

T1 阶段只搭建可运行骨架：路由前缀 /api，提供 /api/health。
T2 阶段接入项目 / 方案 CRUD 与字段 Schema 查询；业务逻辑继续按 AGENTS.md 推进。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import projects as projects_api
from app.api import schema as schema_api
from app.api import schemes as schemes_api
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时建表，关闭时无需特别清理。"""
    init_db()
    yield


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。"""
    settings = get_settings()
    app = FastAPI(
        title="筑衡 API",
        version="0.1.0",
        description="建筑方案智能比选智能体的后端服务",
        lifespan=lifespan,
    )

    # 开发环境开启 CORS，允许前端 Vite 默认端口访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 所有业务路由统一挂在 /api 前缀下，并合并到根 OpenAPI（/docs）里
    app.include_router(projects_api.router, prefix="/api")
    app.include_router(schemes_api.router, prefix="/api")
    app.include_router(schema_api.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """健康检查，供前端和编排脚本探活。"""
        return {"status": "ok", "version": app.version}

    return app


app = create_app()