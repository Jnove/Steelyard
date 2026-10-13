"""覆盖层的变更留痕与操作者标识（片 4：权限与审计）。

守住四条：

1. 四类内容（选项 / 模板 / 规则 / 字段）的**新增与删除**都要留痕——覆盖层不进 git、
   不经过 CI，留痕是唯一能追查"谁在什么时候加了什么"的依据；
2. 留痕**只追加**：没有修改与删除接口，且 `record` 只 flush 不 commit，
   与业务写操作同一个事务，所以"改成功但没留痕"不会发生；
3. 操作者标识做归一化：空值 → `anonymous`，控制字符清掉，超长截断
   ——它不是权限判据（头可以伪造），但必须始终可读、可比对；
4. 生产环境（`APP_ENV` 非 dev）写接口照旧 403，而**留痕读接口照常可用**。
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from app.config import get_settings
from app.custom.audit import (
    OPERATOR_ANONYMOUS,
    OPERATOR_MAX_LENGTH,
    normalize_operator,
    record,
)
from fastapi.testclient import TestClient

AUDIT = "/api/custom/audit"
#: HTTP 头只能是 ASCII，中文名要由客户端百分号编码后传（浏览器里就是 encodeURIComponent）。
OPERATOR = {"X-Operator": quote("张三")}

OPTION = {"field": "risk_features", "value": "临近地铁振动"}
TEMPLATE = {
    "name": "代建单位（重工期）",
    "note": "代建单位更在意工期，因此把施工维度调高",
    "source": "经验规则（专业组）：代建合同通常带工期考核",
    "weights": [0.2, 0.2, 0.5, 0.1],
}
RULE = {
    "id": "X-77",
    "name": "楼板厚度下限复核",
    "type": "hard",
    "when": "slab_thickness >= 0",
    "check": "slab_thickness >= 100",
    "message": "楼板厚度 {slab_thickness} mm 低于 100 mm",
    "source": "经验规则（土木组）：住宅现浇楼板按 100 mm 控制",
}
FIELD = {"key": "bearing_wall_ratio", "label": "承重墙占比", "kind": "ratio"}


def _entries(client: TestClient) -> list[dict]:
    response = client.get(AUDIT)
    assert response.status_code == 200, response.text
    return response.json()


def test_all_four_kinds_leave_a_trace_on_create_and_delete(client: TestClient) -> None:
    """四类内容各建一条、再各删一条 → 八条留痕，且新的在前。"""
    created: list[tuple[str, int]] = []
    option = client.post("/api/custom/options", json=OPTION, headers=OPERATOR)
    created.append(("options", option.json()["id"]))
    template = client.post("/api/custom/weight-templates", json=TEMPLATE, headers=OPERATOR)
    created.append(("weight-templates", template.json()["id"]))
    rule = client.post("/api/custom/rules", json=RULE, headers=OPERATOR)
    created.append(("rules", rule.json()["id"]))
    field = client.post("/api/custom/fields", json=FIELD, headers=OPERATOR)
    created.append(("fields", field.json()["id"]))
    for path, row_id in created:
        deleted = client.delete(f"/api/custom/{path}/{row_id}", headers=OPERATOR)
        assert deleted.status_code == 204, deleted.text

    entries = _entries(client)
    assert len(entries) == 8
    # 新的在前：最后一条删除排在最前
    assert entries[0]["action"] == "delete"
    assert {item["kind"] for item in entries} == {"option", "template", "rule", "field"}
    assert {item["action"] for item in entries} == {"create", "delete"}
    # 每个类别各有一次新增与一次删除
    for kind in ("option", "template", "rule", "field"):
        actions = sorted(item["action"] for item in entries if item["kind"] == kind)
        assert actions == ["create", "delete"], kind
    # 类别中文名直接给界面用
    assert all(item["kind_label"] for item in entries)
    # 操作者标识原样带上
    assert {item["operator"] for item in entries} == {"张三"}


def test_delete_trace_keeps_the_original_value(client: TestClient) -> None:
    """删除的留痕必须记住"删掉的是什么"——删完就说不清就失去了意义。"""
    created = client.post("/api/custom/options", json=OPTION, headers=OPERATOR).json()
    assert client.delete(f"/api/custom/options/{created['id']}", headers=OPERATOR).status_code == 204

    entries = _entries(client)
    deleted = next(item for item in entries if item["action"] == "delete")
    assert deleted["kind"] == "option"
    assert deleted["target"] == "risk_features=临近地铁振动"
    assert deleted["detail"]["value"] == "临近地铁振动"
    assert "临近地铁振动" in deleted["summary"]


def test_operator_is_normalized_and_defaults_to_anonymous(client: TestClient) -> None:
    messy = client.post(
        "/api/custom/options",
        json=OPTION,
        headers={"X-Operator": quote("  张三\n土木\t组  ")},
    )
    assert messy.status_code == 201, messy.text
    # 纯 ASCII 的工号不必编码，原样留存
    ascii_id = client.post(
        "/api/custom/options",
        json={"field": "risk_features", "value": "邻近铁路振动"},
        headers={"X-Operator": "A-1024"},
    )
    assert ascii_id.status_code == 201, ascii_id.text
    silent = client.post(
        "/api/custom/options",
        json={"field": "risk_features", "value": "狭窄施工场地"},
    )
    assert silent.status_code == 201, silent.text

    by_operator = {item["operator"] for item in _entries(client)}
    assert by_operator == {"张三 土木 组", "A-1024", OPERATOR_ANONYMOUS}


def test_writes_are_closed_in_prod_but_audit_stays_readable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = len(_entries(client))
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        blocked = client.post("/api/custom/options", json=OPTION, headers=OPERATOR)
        assert blocked.status_code == 403, blocked.text
        # 读接口要继续可用：前端要能展示"谁改过什么"
        after = _entries(client)
        assert len(after) == before
    finally:
        get_settings.cache_clear()


def test_audit_limit_is_bounded(client: TestClient) -> None:
    client.post("/api/custom/options", json=OPTION, headers=OPERATOR)
    assert client.get(f"{AUDIT}?limit=1").status_code == 200
    assert len(client.get(f"{AUDIT}?limit=1").json()) == 1
    # 上限 500：即使传一个很大的数也不会把整库拉出来
    assert client.get(f"{AUDIT}?limit=9999").status_code == 200


def test_normalize_operator_rules() -> None:
    assert normalize_operator(None) == OPERATOR_ANONYMOUS
    assert normalize_operator("   ") == OPERATOR_ANONYMOUS
    # 纯 ASCII 标识（工号）原样通过
    assert normalize_operator("A-1024") == "A-1024"
    # 百分号编码的中文名解回 UTF-8
    assert normalize_operator(quote("张三")) == "张三"
    assert normalize_operator("张三\n土木\t组") == "张三 土木 组"
    assert len(normalize_operator("x" * 500)) == OPERATOR_MAX_LENGTH


def test_record_refuses_unknown_action_or_kind() -> None:
    """宁可当场炸，也不要写进一条"看起来像留痕、其实没人认识"的记录。"""
    with pytest.raises(ValueError):
        record(None, operator="张三", action="update", kind="option", target="t")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        record(None, operator="张三", action="create", kind="project", target="t")  # type: ignore[arg-type]
