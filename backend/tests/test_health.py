"""健康检查接口测试。

T1 阶段确保 /api/health 返回约定的 status / version 字段，
后续可扩展到鉴权、依赖可用性等更全面的探活。
"""

from app.main import app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    """健康检查应返回 200 与约定的 status 字段。"""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok", "version": "0.1.0"}