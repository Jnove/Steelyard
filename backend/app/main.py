"""筑衡后端 FastAPI 应用入口。

T1 阶段只搭建可运行骨架：路由前缀 /api，提供 /api/health。
业务逻辑在后续任务中按 AGENTS.md 的目录结构逐步补齐。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。"""
    settings = get_settings()
    app = FastAPI(
        title="筑衡 API",
        version="0.1.0",
        description="建筑方案智能比选智能体的后端服务",
    )

    # 开发环境开启 CORS，允许前端 Vite 默认端口访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 所有业务路由统一挂在 /api 前缀下
    api_router = FastAPI()

    @api_router.get("/health")
    def health() -> dict[str, str]:
        """健康检查，供前端和编排脚本探活。"""
        return {"status": "ok", "version": app.version}

    app.mount("/api", api_router)
    return app


app = create_app()