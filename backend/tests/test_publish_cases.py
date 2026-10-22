"""演示发布只追加明确标识的案例，重复运行不得覆盖或删改原项目。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from publish_demo_cases import build_plan, publish  # noqa: E402


class ClientApi:
    def __init__(self, client):
        self.client = client

    def call(self, path, method="GET", body=None):
        response = self.client.request(method, "/api" + path, json=body)
        assert response.is_success, response.text
        return response.json() if response.content else None


def test_public_case_plan_keeps_unknowns_and_teaching_labels():
    plan = build_plan()
    assert len(plan) == 5
    assert sum(len(item["schemes"]) for item in plan) == 22
    for item in plan[:3]:
        assert "教学" in item["name"]
        assert item["params"]["far_max"] is None
        assert item["params"]["density_max"] == (0.22 if item["case_id"] == "xiasha-real" else None)
        assert item["params"]["height_max"] is None
        assert item["params"]["seismic_intensity"] is None
        assert all("教学" in scheme["name"] and scheme["params"]["scheme_notes"] for scheme in item["schemes"])


def test_publish_is_idempotent_and_never_overwrites_user_project(client):
    plan = build_plan()[0:1]
    user = client.post("/api/projects", json={"name": "用户项目", "params": {"site_area": 999}}).json()
    first = publish(ClientApi(client), plan)
    again = publish(ClientApi(client), plan)
    assert first == again
    assert len(client.get("/api/projects").json()) == 2
    assert client.get(f"/api/projects/{user['id']}").json() == user
    conflict = [{**plan[0], "params": {**plan[0]["params"], "site_area": 1}}]
    with pytest.raises(ValueError, match="拒绝覆盖"):
        publish(ClientApi(client), conflict)
    assert client.get(f"/api/projects/{first[0]['project_id']}").json()["params"]["site_area"] == 25577


def test_whatif_is_stored_but_not_added_to_default_dashboard(client):
    receipt = publish(ClientApi(client), build_plan()[3:4])[0]
    assert receipt["schemes"] == 7
    assert receipt["evaluated"] == 6
    project_id = receipt["project_id"]
    assert len(client.get(f"/api/projects/{project_id}/schemes").json()) == 6
    assert len(client.get(f"/api/projects/{project_id}/schemes?include_whatif=true").json()) == 7
    assert len(client.get(f"/api/projects/{project_id}/evaluate").json()["results"]) == 6
