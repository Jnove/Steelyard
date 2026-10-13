"""回灌路径：把覆盖层导出成可落库的片段。

这是片 3 / 片 4 验收里的最后一项，也是目标里那条不变式——
"自定义内容可导回 YAML / 代码成为最终权威"。守住四条：

1. 四类内容都能导出成片段，且片段**语法可用**：YAML 过 ``yaml.safe_load``，
   Python 片段去掉注释行与类体缩进后过 ``ast.parse``；
2. 不能自动改对的地方必须**写明**，而不是悄悄替使用者决定：
   ``X-`` 编号要给建议编号、权重模板要提示改角色键并同步 ``ROLE_KEYS``、
   ``compliance`` 要声明是硬门槛参考值；
3. 导出**只读**：生产环境照常可用；
4. 回灌的强制点落在**文件校验**上：``rules/*.yaml`` 里出现保留前缀 ``X-`` 直接报错。
   共享校验器还要放行运行期的 ``X-`` 规则，所以这条只能在文件层校验。
"""

from __future__ import annotations

import ast
import importlib
import sys
import textwrap
from pathlib import Path

import pytest
import yaml
from app.config import get_settings
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
check_rules = importlib.import_module("scripts.check_rules")

EXPORT = "/api/custom/export"

METRIC_RULE = {
    "id": "X-02",
    "name": "标准层重复率（自定义）",
    "type": "metric",
    "dimension": "structure",
    "value": "std_floor_repeat",
    "scoring": {"kind": "piecewise", "points": [[0.3, 0], [0.6, 60], [0.8, 100]]},
    "weight_in_dimension": 1,
    "source": "经验规则（土木组）：标准层重复率越高，模板与构件周转越充分",
}
FIELD = {"key": "bearing_wall_ratio", "label": "承重墙占比", "kind": "ratio"}
OPTION = {"field": "risk_features", "value": "临近地铁振动"}
TEMPLATE = {
    "name": "代建单位（重工期）",
    "note": "代建单位更在意工期，因此把施工维度调高",
    "source": "经验规则（专业组）：代建合同通常带工期考核",
    "weights": [0.2, 0.2, 0.5, 0.1],
}


def _python_code(snippet: str) -> str:
    """取出片段里的代码部分：去掉列 0 的注释行，再去掉类体缩进。"""
    code = "\n".join(line for line in snippet.splitlines() if not line.lstrip().startswith("#"))
    return textwrap.dedent(code)


def _seed(client: TestClient) -> None:
    assert client.post("/api/custom/rules", json=METRIC_RULE).status_code == 201
    assert client.post("/api/custom/fields", json=FIELD).status_code == 201
    assert client.post("/api/custom/options", json=OPTION).status_code == 201
    assert client.post("/api/custom/weight-templates", json=TEMPLATE).status_code == 201


def test_empty_overlay_exports_placeholders(client: TestClient) -> None:
    body = client.get(EXPORT).json()
    assert body["counts"] == {"rules": 0, "fields": 0, "options": 0, "templates": 0}
    for section in ("rules_yaml", "fields_python", "options_python", "weights_yaml"):
        assert "没有" in body[section]
    # 清单与注意事项在任何情况下都要给出来——它们是"怎么落地"的唯一说明书
    assert len(body["checklist"]) >= 5
    assert any("X-" in note for note in body["notes"])
    assert "# 自定义内容导出" in body["markdown"]


def test_snippets_are_syntactically_usable(client: TestClient) -> None:
    _seed(client)
    body = client.get(EXPORT).json()
    assert body["counts"] == {"rules": 1, "fields": 1, "options": 1, "templates": 1}

    # ① 规则片段：注释 + YAML 列表；清单里带建议编号（S 系列现有到 S-14，故建议 S-15）
    rules = yaml.safe_load(body["rules_yaml"])
    assert isinstance(rules, list) and len(rules) == 1
    assert rules[0]["id"] == METRIC_RULE["id"]
    assert rules[0]["dimension"] == "structure"
    assert "入库前把 id" in body["rules_yaml"]
    assert "S-15" in body["rules_yaml"]

    # ② Python 片段：去掉注释与缩进后能过 ast.parse
    ast.parse(_python_code(body["fields_python"]))
    ast.parse(_python_code(body["options_python"]))
    assert "bearing_wall_ratio" in body["fields_python"]
    assert "RISK_FEATURE_OPTIONS" in body["options_python"]
    assert "临近地铁振动" in body["options_python"]

    # ③ 权重片段：YAML 可用，且补齐了 compliance（硬门槛，不计分）
    weights = yaml.safe_load(body["weights_yaml"])
    role = next(iter(weights.values()))
    assert role["label"] == TEMPLATE["name"]
    assert set(role["weights"]) == {"compliance", "quality", "structure", "construction", "green"}
    # 四个评分维度必须与模板一致（只补 compliance，不改使用者给的值）
    assert role["weights"]["construction"] == 0.5
    # 三件必须人工确认的事都写在片段里
    assert "ROLE_KEYS" in body["weights_yaml"]
    assert "compliance" in body["weights_yaml"]
    assert "rationale" in body["weights_yaml"]

    # ④ 汇总 markdown 把四段都带上
    for section in ("## 1. 规则", "## 2. 字段", "## 3. 枚举选项", "## 4. 角色权重模板"):
        assert section in body["markdown"]


def test_export_is_read_only_and_readable_in_prod(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    try:
        assert client.get(EXPORT).status_code == 200
        # 写接口仍然关着
        assert client.post("/api/custom/options", json=OPTION).status_code == 403
    finally:
        get_settings.cache_clear()


def test_runtime_prefix_is_rejected_in_files(tmp_path: Path) -> None:
    """文件里出现 X- 编号必须报错：它是运行期保留前缀，回灌时要换维度前缀。"""
    bad = tmp_path / "structure.yaml"
    bad.write_text(
        "- id: X-01\n"
        "  name: 楼板厚度复核\n"
        "  type: hard\n"
        "  when: slab_thickness >= 0\n"
        "  check: slab_thickness >= 100\n"
        "  message: 楼板厚度不足\n"
        "  source: 经验规则（土木组）：住宅现浇楼板按 100 mm 控制\n",
        encoding="utf-8",
    )
    codes = [issue.code for issue in check_rules.check_file(bad).issues]
    assert "RUNTIME_PREFIX_IN_FILE" in codes

    # 换成维度前缀后这条特定的报错就消失（其它报错与本条无关）
    good = tmp_path / "structure_ok.yaml"
    good.write_text(bad.read_text(encoding="utf-8").replace("X-01", "S-99"), encoding="utf-8")
    assert "RUNTIME_PREFIX_IN_FILE" not in [
        issue.code for issue in check_rules.check_file(good).issues
    ]


def test_repo_rules_never_use_the_runtime_prefix() -> None:
    """仓库里的规则文件一条都不该用 X-：这条不变式由 CI 的 check_rules 兜住。"""
    offenders: list[str] = []
    for path in sorted((ROOT / "rules").glob("*.yaml")):
        for issue in check_rules.check_file(path).issues:
            if issue.code == "RUNTIME_PREFIX_IN_FILE":
                offenders.append(f"{path.name}:{issue.line}")
    assert offenders == []
