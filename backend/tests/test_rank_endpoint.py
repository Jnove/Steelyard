"""排序接口的取数、筛选、数组映射和完整请求耗时。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter

import numpy as np
import pytest
from app.custom.signature import SIGNATURE_KEY, rules_signature
from app.engine.mcdm import CRITERION_ORDER
from app.models import ComplianceItem, DimensionScores, EvalResult, EvalResultRow, Project, Scheme
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

SCORES = [[30, 40, 50, 60], [60, 40, 30, 50], [40, 80, 50, 30], [60, 70, 80, 40], [90, 90, 90, 90]]


def _seed(
    engine: Engine, *, failed: bool = False, all_failed: bool = False, whatif: bool = False
) -> tuple[int, list[int]]:
    """输入序最后一个方案全面占优，用来发现响应重排导致的下标错配。"""
    with Session(engine) as session:
        project = Project(name="排序测试")
        session.add(project)
        session.flush()
        assert project.id is not None
        ids: list[int] = []
        for i, values in enumerate(SCORES):
            scheme = Scheme(project_id=project.id, name=f"测试方案{i}", is_whatif=whatif and i == 4)
            session.add(scheme)
            session.flush()
            assert scheme.id is not None
            ids.append(scheme.id)
            compliance: list[ComplianceItem] = []
            if all_failed or (failed and i == 0):
                compliance.append(
                    ComplianceItem(
                        rule_id="C-01",
                        name="测试约束",
                        status="failed",
                        severity="error",
                        source="测试",
                        message="测试失败",
                    )
                )
            elif failed and i == 1:
                compliance.append(
                    ComplianceItem(
                        rule_id="C-02",
                        name="测试提示",
                        status="failed",
                        severity="warning",
                        source="测试",
                        message="仅提示",
                    )
                )
            elif failed and i == 2:
                compliance.append(
                    ComplianceItem(
                        rule_id="C-03",
                        name="测试缺数据",
                        status="insufficient_data",
                        severity="error",
                        source="测试",
                        message="数据不足",
                    )
                )
            result = EvalResult(
                scheme_id=str(scheme.id),
                scheme_name=scheme.name,
                compliance=compliance,
                dimension_scores=DimensionScores(**dict(zip(CRITERION_ORDER, values, strict=True))),
            )
            session.add(
                EvalResultRow(
                    project_id=project.id, scheme_id=scheme.id,
                    result={**result.model_dump(), SIGNATURE_KEY: rules_signature(session)},
                )
            )
        session.commit()
        return project.id, ids


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "government"},
        {"role": "developer"},
        {"role": "contractor"},
        {"role": "resident"},
        {"weights": [4, 3, 2, 1]},
        {"pairwise_matrix": [[1] * 4] * 4},
    ],
)
def test_weight_sources_and_index_mapping(
    client: TestClient, engine: Engine, payload: dict[str, object]
) -> None:
    project, ids = _seed(engine)
    response = client.post(f"/api/projects/{project}/rank", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["criteria"] == list(CRITERION_ORDER)
    assert body["scheme_order"] == list(map(str, ids))
    assert body["ranking"][0]["scheme_id"] == str(ids[4])
    assert body["ranking"][0]["rank"] == 1
    assert body["sensitivity"]["baseline_top_index"] == 4
    assert body["pareto"]["non_dominated"] == [4]
    assert body["rank_acceptability"]["first_place_probability"][4] == 1
    assert len(body["sensitivity"]["cells"]) == 16
    assert len(body["sensitivity"]["flip_points"]) == 4
    assert sum(body["weights_used"]["weights"]) == pytest.approx(1)
    ahp = body["weights_used"]["ahp"]
    if "pairwise_matrix" in payload:
        assert ahp is not None and ahp["cr"] < 0.1
    elif "weights" in payload:
        assert ahp is None
    else:
        # 角色模板：矩阵写法才有 CR；weights 写法（rules-guide 认可的另一种写法）为 None。
        assert ahp is None or ahp["cr"] < 0.1


def test_compliance_filter_and_override(client: TestClient, engine: Engine) -> None:
    project, ids = _seed(engine, failed=True)
    url = f"/api/projects/{project}/rank"
    body = client.post(url, json={"weights": [1] * 4}).json()
    assert body["excluded"][0]["scheme_id"] == str(ids[0])
    assert body["excluded"][0]["failed_rules"] == ["C-01"]
    assert "error" in body["excluded"][0]["reason"]
    assert body["scheme_order"] == list(map(str, ids[1:]))
    # warning 不拦排名，insufficient_data 与 failed 是不同状态。
    overridden = client.post(url, json={"weights": [1] * 4, "include_noncompliant": True}).json()
    assert len(overridden["ranking"]) == 5
    assert overridden["excluded"] == []


def test_all_excluded_is_valid_empty_response(client: TestClient, engine: Engine) -> None:
    project, _ = _seed(engine, all_failed=True)
    response = client.post(f"/api/projects/{project}/rank", json={"weights": [1] * 4})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["excluded"]) == 5
    assert body["ranking"] == body["scheme_order"] == []
    assert body["rank_acceptability"]["probabilities"] == []
    assert body["sensitivity"]["baseline_top_index"] is None


def test_no_evaluation_and_missing_project(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "尚未评估"}).json()["id"]
    response = client.post(f"/api/projects/{project}/rank", json={"role": "resident"})
    assert response.status_code == 409
    assert "evaluate" in response.json()["detail"]
    assert client.post("/api/projects/99999/rank", json={"weights": [1] * 4}).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"weights": [1] * 4, "role": "resident"},
        {"weights": [1] * 4, "pairwise_matrix": [[1] * 4] * 4},
        {"role": "resident", "unknown": True},
        {"weights": [1] * 4, "seed": -1},
        {"weights": [1] * 4, "monte_carlo_samples": 0},
    ],
)
def test_request_validation(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/api/projects/1/rank", json=payload).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"weights": [1, 1]},
        {"weights": [0] * 4},
        {"weights": [-1, 1, 1, 1]},
        {"role": "不存在"},
        {"pairwise_matrix": [[1, 2], [2, 1]]},
    ],
)
def test_algorithm_input_errors(
    client: TestClient, engine: Engine, payload: dict[str, object]
) -> None:
    project, _ = _seed(engine)
    assert client.post(f"/api/projects/{project}/rank", json=payload).status_code == 400


def test_inconsistent_matrix_returns_warning(client: TestClient, engine: Engine) -> None:
    project, _ = _seed(engine)
    a = [[1, 9, 1 / 9, 1], [1 / 9, 1, 9, 1], [9, 1 / 9, 1, 1], [1, 1, 1, 1]]
    response = client.post(f"/api/projects/{project}/rank", json={"pairwise_matrix": a})
    assert response.status_code == 200
    weights = response.json()["weights_used"]
    assert weights["ahp"]["cr"] >= 0.1
    assert weights["consistency_warning"]


def test_reads_latest_without_mutating_evaluation(client: TestClient, engine: Engine) -> None:
    project, ids = _seed(engine)
    with Session(engine) as session:
        row = session.exec(select(EvalResultRow).where(EvalResultRow.scheme_id == ids[0])).one()
        data = EvalResult.model_validate(row.result)
        data.dimension_scores = DimensionScores(
            quality=100, structure=100, construction=100, green=100
        )
        session.add(
            EvalResultRow(
                project_id=project,
                scheme_id=ids[0],
                result={**data.model_dump(), SIGNATURE_KEY: rules_signature(session)},
                created_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        )
        session.commit()
        before = [(r.id, r.result) for r in session.exec(select(EvalResultRow)).all()]
    body = client.post(f"/api/projects/{project}/rank", json={"weights": [1] * 4}).json()
    assert len(body["ranking"]) == 5
    assert body["ranking"][0]["scheme_id"] == str(ids[0])
    with Session(engine) as session:
        after = [(r.id, r.result) for r in session.exec(select(EvalResultRow)).all()]
    assert after == before


def test_whatif_filter_and_seed_reproducibility(client: TestClient, engine: Engine) -> None:
    project, ids = _seed(engine, whatif=True)
    url = f"/api/projects/{project}/rank"
    base = client.post(url, json={"weights": [1] * 4}).json()
    assert str(ids[4]) not in base["scheme_order"]
    payload = {"weights": [0.4, 0.3, 0.2, 0.1], "include_whatif": True, "seed": 73}
    first, second = (client.post(url, json=payload).json() for _ in range(2))
    first.pop("elapsed_ms")
    second.pop("elapsed_ms")
    assert first == second
    assert len(first["ranking"]) == 5


def test_single_active_criterion(client: TestClient, engine: Engine) -> None:
    project, _ = _seed(engine)
    response = client.post(f"/api/projects/{project}/rank", json={"weights": [1, 0, 0, 0]})
    assert response.status_code == 200, response.text
    assert response.json()["rank_acceptability"]["first_place_probability"][-1] == 1


def test_evaluate_then_rank_workflow(client: TestClient) -> None:
    project = client.post(
        "/api/projects", json={"name": "联调", "params": {"site_area": 10000}}
    ).json()["id"]
    for i in range(2):
        response = client.post(
            f"/api/projects/{project}/schemes",
            json={
                "name": f"联调方案{i}",
                "params": {
                    "floor_height": 3.2,
                    "floors": 8,
                    "std_floor_repeat": 0.8 + i * 0.1,
                    "risk_features": [],
                },
            },
        )
        assert response.status_code == 201, response.text
    assert client.post(f"/api/projects/{project}/evaluate").status_code == 200
    response = client.post(f"/api/projects/{project}/rank", json={"role": "resident"})
    assert response.status_code == 200, response.text
    assert len(response.json()["ranking"]) == 2


def test_five_schemes_full_request_under_100ms(client: TestClient, engine: Engine) -> None:
    """计时覆盖数据库读取、1000 次抽样、响应序列化和 TestClient 往返。"""
    project, _ = _seed(engine)
    elapsed: list[float] = []
    for payload in (
        {"role": "resident"},
        {"weights": [0.4, 0.3, 0.2, 0.1]},
        {"pairwise_matrix": [[1] * 4] * 4},
    ):
        start = perf_counter()
        response = client.post(f"/api/projects/{project}/rank", json=payload)
        elapsed.append((perf_counter() - start) * 1000)
        assert response.status_code == 200, response.text
        assert len(response.json()["ranking"]) == 5
    print(f"五方案完整请求耗时（毫秒）：{elapsed}")
    assert max(elapsed) < 100, f"完整请求耗时 {elapsed} ms，超过 100 ms"
    np.testing.assert_allclose(
        np.sum(response.json()["rank_acceptability"]["probabilities"], axis=1), 1
    )
