"""筑衡后端 FastAPI 应用入口。

T1 阶段只搭建可运行骨架：路由前缀 /api，提供 /api/health。
T2 阶段接入项目 / 方案 CRUD 与字段 Schema 查询。
T3 阶段接入确定性引擎：启动时加载 rules/*.yaml，提供 /api/projects/{id}/evaluate
与 /api/rules[/reload]。
T4 阶段接入多准则决策：启动时加载 rules/weights.yaml 的角色模板，
提供 /api/projects/{id}/rank（TOPSIS + 敏感性 + 帕累托 + 名次概率）。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import evaluate as evaluate_api
from app.api import projects as projects_api
from app.api import rank as rank_api
from app.api import rules as rules_api
from app.api import schema as schema_api
from app.api import schemes as schemes_api
from app.config import get_settings
from app.db import init_db
from app.engine.rules import RuleLoadError, get_ruleset
from app.engine.weights import WeightsLoadError, get_role_templates


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时建表并加载规则，关闭时无需特别清理。"""
    init_db()
    # 规则在启动时加载一次，之后由 POST /api/rules/reload 热重载（仅开发环境）。
    # 这里刻意**不让加载失败阻断启动**：规则由非程序员维护，写错一条不该让整个演示起不来；
    # 真正的闸门是 CI 里的 scripts/check_rules.py，而 /api/rules 会把失败原因原样返回。
    try:
        get_ruleset()
    except RuleLoadError as exc:
        print("⚠️ 规则加载失败，涉及规则的接口会返回错误。请跑 scripts/check_rules.py：")
        for problem in exc.problems:
            print(f"   - {problem}")
    # 角色权重模板同理：加载失败只警告，不阻断启动。
    try:
        get_role_templates()
    except WeightsLoadError as exc:
        print("⚠️ 角色权重模板加载失败，按角色排序会返回错误。请跑 scripts/check_rules.py：")
        for problem in exc.problems:
            print(f"   - {problem.message}")
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
    app.include_router(evaluate_api.router, prefix="/api")
    app.include_router(rules_api.router, prefix="/api")
    app.include_router(rank_api.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """健康检查，供前端和编排脚本探活。"""
        return {"status": "ok", "version": app.version}

    return app


app = create_app()
