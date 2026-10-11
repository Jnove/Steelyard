"""Project / Scheme 的 HTTP CRUD 流程测试。

用 FastAPI TestClient + 内存 SQLite，覆盖：
- 创建 / 读取 / 列表 / 更新 / 删除
- 方案名唯一性
- what-if 默认不在列表中
- 级联删除项目连带方案
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select


def _create_project(client: TestClient, name: str = "杭州项目") -> dict:
    resp = client.post(
        "/api/projects",
        json={
            "name": name,
            "params": {
                "site_area": 18000,
                "far_max": 2.2,
                "density_max": 0.28,
                "height_max": 54,
                "climate_zone": "夏热冬冷",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_scheme(
    client: TestClient,
    project_id: int,
    name: str,
    params: dict | None = None,
    is_whatif: bool = False,
    parent_id: int | None = None,
) -> dict:
    body: dict = {
        "name": name,
        "params": params or {"gfa": 12000, "floors": 18},
        "is_whatif": is_whatif,
    }
    if parent_id is not None:
        body["parent_id"] = parent_id
    resp = client.post(f"/api/projects/{project_id}/schemes", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestProjectCRUD:
    def test_create_and_read(self, client: TestClient) -> None:
        project = _create_project(client)
        assert project["id"] > 0
        assert project["name"] == "杭州项目"
        assert project["params"]["site_area"] == 18000

        resp = client.get(f"/api/projects/{project['id']}")
        assert resp.status_code == 200
        assert resp.json()["params"]["climate_zone"] == "夏热冬冷"

    def test_list_projects(self, client: TestClient) -> None:
        _create_project(client, "A 项目")
        _create_project(client, "B 项目")
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert names == ["A 项目", "B 项目"]

    def test_update_project(self, client: TestClient) -> None:
        project = _create_project(client)
        resp = client.put(
            f"/api/projects/{project['id']}",
            json={"name": "改名的项目", "params": {"site_area": 20000}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "改名的项目"
        assert body["params"]["site_area"] == 20000

    def test_get_missing_project_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/projects/9999")
        assert resp.status_code == 404

    def test_delete_project_cascades_schemes(self, client: TestClient) -> None:
        project = _create_project(client)
        _create_scheme(client, project["id"], "A 方案")
        _create_scheme(client, project["id"], "B 方案")

        resp = client.delete(f"/api/projects/{project['id']}")
        assert resp.status_code == 204

        # 方案应随项目一起消失
        resp = client.get(f"/api/projects/{project['id']}/schemes")
        assert resp.status_code == 404

    def test_delete_project_cleans_results_caches_and_whatif_without_touching_other_project(
        self, client: TestClient, engine: Engine
    ) -> None:
        from app.agents.storage import AgentResultRow, ReportCacheRow
        from app.models.orm import EvalResultRow, Project, Scheme

        projects = [_create_project(client, name) for name in ("待删除", "保留")]
        for project in projects:
            parent = _create_scheme(client, project["id"], "原方案")
            _create_scheme(
                client, project["id"], "推演副本", is_whatif=True, parent_id=parent["id"]
            )
            with Session(engine) as session:
                session.add(
                    EvalResultRow(
                        project_id=project["id"], scheme_id=parent["id"], result={"tested": True}
                    )
                )
                session.add(
                    AgentResultRow(
                        project_id=project["id"], fingerprint="测试", evaluation={"tested": True}
                    )
                )
                for version in ("a", "b"):
                    session.add(
                        ReportCacheRow(
                            key=f"{project['id']}-{version}",
                            project_id=project["id"],
                            output={"report": "测试"},
                        )
                    )
                session.commit()

        removed, retained = (project["id"] for project in projects)
        # 开启外键约束，确保评估先于方案删除，带 parent_id 的副本也能完整删除。
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert client.delete(f"/api/projects/{removed}").status_code == 204
        assert client.get(f"/api/projects/{removed}").status_code == 404
        assert client.get(f"/api/projects/{retained}").status_code == 200
        assert client.delete(f"/api/projects/{removed}").status_code == 404
        with Session(engine) as session:
            assert session.get(Project, removed) is None
            for table, expected_retained in (
                (Scheme, 2),
                (EvalResultRow, 1),
                (AgentResultRow, 1),
                (ReportCacheRow, 2),
            ):
                assert session.exec(select(table).where(table.project_id == removed)).all() == []
                assert (
                    len(session.exec(select(table).where(table.project_id == retained)).all())
                    == expected_retained
                )


class TestSchemeCRUD:
    def test_create_scheme(self, client: TestClient) -> None:
        project = _create_project(client)
        scheme = _create_scheme(client, project["id"], "方案 A", {"gfa": 15000})
        assert scheme["project_id"] == project["id"]
        assert scheme["name"] == "方案 A"
        assert scheme["is_whatif"] is False
        assert scheme["params"]["gfa"] == 15000

    def test_unique_scheme_name_within_project(self, client: TestClient) -> None:
        project = _create_project(client)
        _create_scheme(client, project["id"], "方案 A")
        resp = client.post(
            f"/api/projects/{project['id']}/schemes",
            json={"name": "方案 A", "params": {}},
        )
        assert resp.status_code == 409

    def test_whatif_hidden_by_default(self, client: TestClient) -> None:
        project = _create_project(client)
        base = _create_scheme(client, project["id"], "原方案")
        _create_scheme(
            client,
            project["id"],
            "what-if 副本",
            is_whatif=True,
            parent_id=base["id"],
        )

        resp = client.get(f"/api/projects/{project['id']}/schemes")
        names = [s["name"] for s in resp.json()]
        assert names == ["原方案"]

        resp = client.get(
            f"/api/projects/{project['id']}/schemes",
            params={"include_whatif": "true"},
        )
        names = [s["name"] for s in resp.json()]
        assert "what-if 副本" in names

    def test_update_scheme(self, client: TestClient) -> None:
        project = _create_project(client)
        scheme = _create_scheme(client, project["id"], "方案 A")
        resp = client.put(
            f"/api/projects/{project['id']}/schemes/{scheme['id']}",
            json={"name": "方案 A 改", "params": {"gfa": 20000, "floors": 20}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "方案 A 改"
        assert body["params"]["floors"] == 20

    def test_update_invalidates_scheme_not_in_project(self, client: TestClient) -> None:
        project = _create_project(client)
        scheme = _create_scheme(client, project["id"], "A")
        resp = client.put(
            f"/api/projects/{project['id']}/schemes/{scheme['id'] + 100}",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_scheme(self, client: TestClient) -> None:
        project = _create_project(client)
        scheme = _create_scheme(client, project["id"], "A")
        resp = client.delete(f"/api/projects/{project['id']}/schemes/{scheme['id']}")
        assert resp.status_code == 204

        resp = client.get(f"/api/projects/{project['id']}/schemes/{scheme['id']}")
        assert resp.status_code == 404


class TestFullCRUDFlow:
    """端到端：从建项目到删方案的完整路径。"""

    def test_happy_path(self, client: TestClient) -> None:
        # 1. 建项目
        project = _create_project(client)
        pid = project["id"]

        # 2. 在项目下建 3 个方案
        s_a = _create_scheme(client, pid, "高层 A", {"gfa": 12000, "floors": 18})
        s_b = _create_scheme(client, pid, "小高层 B", {"gfa": 9000, "floors": 12})
        s_c = _create_scheme(client, pid, "MiC 方案 C", {"gfa": 14000, "floors": 20})

        # 3. 列表应为 3 个
        resp = client.get(f"/api/projects/{pid}/schemes")
        assert len(resp.json()) == 3

        # 4. 更新其中一个
        resp = client.put(
            f"/api/projects/{pid}/schemes/{s_b['id']}",
            json={"params": {"gfa": 9500, "floors": 13}},
        )
        assert resp.status_code == 200
        assert resp.json()["params"]["floors"] == 13

        # 5. 删除其中一个
        resp = client.delete(f"/api/projects/{pid}/schemes/{s_c['id']}")
        assert resp.status_code == 204

        # 6. 列表剩 2 个
        resp = client.get(f"/api/projects/{pid}/schemes")
        assert len(resp.json()) == 2
        remaining_ids = {s["id"] for s in resp.json()}
        assert remaining_ids == {s_a["id"], s_b["id"]}

        # 7. 删项目 → 项目和方案都消失
        resp = client.delete(f"/api/projects/{pid}")
        assert resp.status_code == 204
        assert client.get(f"/api/projects/{pid}").status_code == 404
