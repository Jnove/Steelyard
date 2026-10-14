"""自定义角色权重模板（覆盖层第一片）。

守住三条：
1. **校验同源**：界面里新增的模板必须过引擎自己的校验器，报错措辞与 ``check_rules`` 一致；
2. 自定义模板与内建四个角色**并列可选**，排序结果要标明它来自覆盖层（``is_custom``）；
3. 矩阵一致性 CR ≥ 0.1 在文件里只警告，但在界面里新增时**直接拒绝**。
"""

from __future__ import annotations

import pytest
from app.config import get_settings
from app.custom.signature import SIGNATURE_KEY, project_rules_signature
from app.engine.mcdm import CRITERION_ORDER
from app.models import DimensionScores, EvalResult, EvalResultRow, Project, ProjectParams, Scheme
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

#: 两个维度得分不同的方案，够 rank 跑起来；自定义权重本身与方案内容无关。
SCORES = [[60, 40, 30, 50], [40, 80, 50, 30]]

#: 完全一致的矩阵（各行互为倍数），CR 应当为 0；权重比例 4:2:1:2。
CONSISTENT_MATRIX = [
    [1, 2, 4, 2],
    ["1/2", 1, 2, 1],
    ["1/4", "1/2", 1, "1/2"],
    ["1/2", 1, 2, 1],
]

#: 刻意自相矛盾的矩阵（A 比 B 重要 9 倍，B 与 C 同重，但 A 比 C 只写 1/9）。
INCONSISTENT_MATRIX = [
    [1, 9, "1/9", 1],
    ["1/9", 1, "1/9", 1],
    [9, 9, 1, 9],
    [1, 1, "1/9", 1],
]


def _seed(engine: Engine) -> tuple[int, list[int]]:
    """建一个项目 + 两个带评估结果的方案。"""
    with Session(engine) as session:
        project = Project(name="自定义模板测试")
        session.add(project)
        session.flush()
        assert project.id is not None
        ids: list[int] = []
        for index, values in enumerate(SCORES):
            scheme = Scheme(project_id=project.id, name=f"方案{index}")
            session.add(scheme)
            session.flush()
            assert scheme.id is not None
            ids.append(scheme.id)
            result = EvalResult(
                scheme_id=str(scheme.id),
                scheme_name=scheme.name,
                compliance=[],
                dimension_scores=DimensionScores(**dict(zip(CRITERION_ORDER, values, strict=True))),
            )
            session.add(
                EvalResultRow(project_id=project.id, scheme_id=scheme.id, result={**result.model_dump(), SIGNATURE_KEY: project_rules_signature(session, ProjectParams())})
            )
        session.commit()
        return project.id, ids


def test_weights_template_is_usable_by_key_and_by_name(
    client: TestClient, engine: Engine
) -> None:
    created = client.post(
        "/api/custom/weight-templates",
        json={
            "name": "代建单位（重工期）",
            "note": "代建单位最怕拖工期，施工友好给得高。",
            "source": "经验规则（专业组）：代建单位访谈口径，待 AHP 校准",
            "weights": [2, 2, 5, 1],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    template_id = body["id"]
    assert body["key"] == f"custom:{template_id}"
    assert body["matrix"] is None
    assert body["ahp"] is None
    assert body["weights"] == pytest.approx([0.2, 0.2, 0.5, 0.1])

    project_id, _ = _seed(engine)

    listed = client.get(f"/api/projects/{project_id}/rank/roles").json()
    assert {role["role_name"] for role in listed["custom_roles"]} == {"代建单位（重工期）"}
    # 内建角色照旧：main 侧新增了"设计单位"，现在是五个（government / developer /
    # contractor / resident / design）。自定义模板不改变内建角色的数量与顺序。
    assert len(listed["roles"]) == 5

    for role_ref in (body["key"], "代建单位（重工期）"):
        ranked = client.post(f"/api/projects/{project_id}/rank", json={"role": role_ref})
        assert ranked.status_code == 200, ranked.text
        used = ranked.json()["weights_used"]
        assert used["weights"] == pytest.approx(body["weights"])
        assert used["is_custom"] is True
        assert used["role_name"] == "代建单位（重工期）"
        # 报告里必须能看出它没进 git、不参与 CI 校验
        assert "未进入 git" in used["note"]

    # 内建角色不受影响：is_custom 为 false
    builtin = client.post(f"/api/projects/{project_id}/rank", json={"role": "government"})
    assert builtin.json()["weights_used"]["is_custom"] is False


def test_matrix_template_gets_consistency_check(client: TestClient) -> None:
    created = client.post(
        "/api/custom/weight-templates",
        json={"name": "矩阵口径", "matrix": CONSISTENT_MATRIX},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["ahp"] is not None
    assert body["ahp"]["consistent"] is True
    assert body["ahp"]["cr"] == pytest.approx(0.0, abs=1e-6)
    assert body["weights"] == pytest.approx([4 / 9, 2 / 9, 1 / 9, 2 / 9])
    assert body["consistency_warning"] is None


def test_inconsistent_matrix_is_rejected(client: TestClient) -> None:
    """文件里 CR 超标只警告；界面里新增直接拒绝，避免把矛盾判断固化进模板库。"""
    response = client.post(
        "/api/custom/weight-templates",
        json={"name": "自相矛盾", "matrix": INCONSISTENT_MATRIX},
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    problem = detail["problems"][0]
    assert problem["code"] == "MATRIX_INCONSISTENT"
    assert "一致性比率" in problem["message"]
    assert problem["fix"]


def test_draft_problems_are_reported_in_chinese(client: TestClient) -> None:
    both = client.post(
        "/api/custom/weight-templates",
        json={"name": "两个来源", "weights": [1, 1, 1, 1], "matrix": CONSISTENT_MATRIX},
    )
    assert both.status_code == 422
    assert both.json()["detail"]["problems"][0]["code"] == "BOTH_SOURCES"

    neither = client.post("/api/custom/weight-templates", json={"name": "没有来源"})
    assert neither.status_code == 422
    assert neither.json()["detail"]["problems"][0]["code"] == "NO_SOURCE"

    # 引擎自己的报错原样透出（这里长度不对）
    short = client.post(
        "/api/custom/weight-templates", json={"name": "数目不对", "weights": [1, 2, 3]}
    )
    assert short.status_code == 422
    assert short.json()["detail"]["problems"][0]["code"] == "WEIGHTS_BAD_LENGTH"

    # 矩阵形状不对
    bad_shape = client.post(
        "/api/custom/weight-templates", json={"name": "形状不对", "matrix": [[1, 2], [3, 4]]}
    )
    assert bad_shape.status_code == 422
    assert bad_shape.json()["detail"]["problems"][0]["code"] == "MATRIX_BAD_SHAPE"

    # 分数写法：0.33 会顶穿互反检查，引擎的提示要说清该写 1/3
    rounded = client.post(
        "/api/custom/weight-templates",
        json={"name": "四舍五入", "matrix": [[1, 3, 3, 3], [0.33, 1, 1, 1], [0.33, 1, 1, 1], [0.33, 1, 1, 1]]},
    )
    assert rounded.status_code == 422
    assert "必须写 1/3" in rounded.json()["detail"]["problems"][0]["fix"]


def test_name_conflicts_are_rejected(client: TestClient) -> None:
    reserved = client.post(
        "/api/custom/weight-templates", json={"name": "government", "weights": [1, 1, 1, 1]}
    )
    assert reserved.status_code == 422
    assert reserved.json()["detail"]["problems"][0]["code"] == "NAME_RESERVED"

    blank = client.post(
        "/api/custom/weight-templates", json={"name": "   ", "weights": [1, 1, 1, 1]}
    )
    assert blank.status_code == 422
    assert blank.json()["detail"]["problems"][0]["code"] in {"NAME_EMPTY", "ROLE_MISSING_NAME"}

    payload = {"name": "重名测试", "weights": [1, 1, 1, 1]}
    assert client.post("/api/custom/weight-templates", json=payload).status_code == 201
    duplicate = client.post("/api/custom/weight-templates", json=payload)
    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["problems"][0]["code"] == "NAME_DUPLICATE"


def test_delete_makes_the_role_unavailable_again(
    client: TestClient, engine: Engine
) -> None:
    created = client.post(
        "/api/custom/weight-templates", json={"name": "临时口径", "weights": [1, 2, 3, 4]}
    ).json()
    project_id, _ = _seed(engine)

    assert client.post(
        f"/api/projects/{project_id}/rank", json={"role": created["key"]}
    ).status_code == 200

    assert client.delete(f"/api/custom/weight-templates/{created['id']}").status_code == 204

    gone = client.post(f"/api/projects/{project_id}/rank", json={"role": created["key"]})
    assert gone.status_code == 400
    assert "没有角色" in gone.json()["detail"]
    assert client.get(f"/api/projects/{project_id}/rank/roles").json()["custom_roles"] == []

    missing = client.delete("/api/custom/weight-templates/9999")
    assert missing.status_code == 422
    assert missing.json()["detail"]["problems"][0]["code"] == "TEMPLATE_NOT_FOUND"


def test_writes_are_closed_outside_dev(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        blocked = client.post(
            "/api/custom/weight-templates", json={"name": "生产环境", "weights": [1, 1, 1, 1]}
        )
        assert blocked.status_code == 403, blocked.text
        assert client.get("/api/custom/weight-templates").status_code == 200
    finally:
        get_settings.cache_clear()
