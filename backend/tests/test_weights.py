"""角色矩阵、直接权重与校验脚本的集成行为。"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest
import yaml
from app.engine.weights import (
    ROLE_KEYS,
    check_weights_file,
    default_weights_path,
    load_role_templates,
)


def _write_roles(path: Path, government: dict[str, object]) -> Path:
    roles = {key: {"name": "测试角色", "weights": [1, 1, 1, 1]} for key in ROLE_KEYS}
    roles["government"] = government
    path.write_text(yaml.safe_dump(roles, allow_unicode=True), encoding="utf-8")
    return path


def test_example_roles_are_consistent() -> None:
    """仓库里四个角色模板：角色齐全、权重归一；给了矩阵的还要正互反且 CR < 0.1。

    仓库模板既可能是 AHP 矩阵写法，也可能是 ``weights:`` 直接给权重
    （``rules-guide`` 认可的另一种写法，此时没有一致性比率可检验），两种都要能过。
    """
    roles = load_role_templates()
    assert list(roles) == [*ROLE_KEYS, "design"]
    for role in roles.values():
        assert sum(role.weights) == pytest.approx(1)
        if role.ahp is None:
            continue
        assert role.ahp.consistent
        assert role.ahp.cr < 0.1
        a = np.asarray(role.matrix)
        np.testing.assert_allclose(a, 1 / a.T, atol=1e-6, rtol=0)


def test_todo_source_is_marked_for_review(tmp_path: Path) -> None:
    """``source`` 里挂着 TODO 的角色模板必须被标记为待复核。

    2026-10 专业组核定后仓库里的模板已无 TODO，所以用合成文件覆盖这个机制，
    免得测试和种子模板的占位状态绑死。
    """
    path = _write_roles(
        tmp_path / "weights.yaml",
        {"name": "占位角色", "weights": [1, 1, 1, 1], "source": "【示例】TODO(专业组)"},
    )
    assert load_role_templates(path)["government"].needs_review


def test_direct_weights_and_fraction_matrix(tmp_path: Path) -> None:
    path = _write_roles(tmp_path / "weights.yaml", {"name": "测试角色", "weights": [4, 2, 3, 1]})
    template = load_role_templates(path)["government"]
    assert template.weights == pytest.approx([0.4, 0.2, 0.3, 0.1])
    assert template.ahp is None
    # 仓库模板当前用 weights 写法直接给权重（见 rules/weights.yaml 顶部的格式适配说明），
    # 因此没有矩阵；这里确认它能加载、角色齐全、权重归一。
    roles = load_role_templates(default_weights_path())
    assert list(roles) == [*ROLE_KEYS, "design"]
    assert sum(roles["resident"].weights) == pytest.approx(1)


@pytest.mark.parametrize(
    "config,code",
    [
        ({"name": "测试", "weights": [0, 0, 0, 0]}, "WEIGHTS_NOT_POSITIVE"),
        ({"name": "测试", "weights": [float("nan"), 1, 1, 1]}, "WEIGHTS_NOT_NUMBER"),
        ({"name": "测试", "weights": [float("inf"), 1, 1, 1]}, "WEIGHTS_NOT_NUMBER"),
        ({"name": "测试", "weights": [1, 2]}, "WEIGHTS_BAD_LENGTH"),
        ({"name": "测试", "matrix": [[1, 1], [1, 1]]}, "MATRIX_BAD_SHAPE"),
        ({"name": "测试", "weights": [1] * 4, "matrix": [[1] * 4] * 4}, "ROLE_BOTH_SOURCES"),
        ({"name": "测试"}, "ROLE_NO_SOURCE"),
        ({"weights": [1] * 4}, "ROLE_MISSING_NAME"),
        ({"name": "测试", "weigths": [1] * 4}, "ROLE_UNKNOWN_FIELD"),
    ],
)
def test_invalid_role_configuration(tmp_path: Path, config: dict[str, object], code: str) -> None:
    path = _write_roles(tmp_path / "weights.yaml", config)
    _, issues = check_weights_file(path)
    assert any(issue.code == code and issue.severity == "error" for issue in issues)


def test_check_rules_includes_weights_for_all_entry_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """默认、显式文件、显式目录、--rules-dir 都要包含同一套权重检查。"""
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2]))
    check = importlib.import_module("scripts.check_rules")
    # 正互反但不一致的循环判断：Q>S、S>K、K>Q 均为 9 倍。
    a = [[1, 9, "1/9", 1], ["1/9", 1, 9, 1], [9, "1/9", 1, 1], [1, 1, 1, 1]]
    path = _write_roles(tmp_path / "weights.yaml", {"name": "矛盾示例", "matrix": a})
    with pytest.warns(UserWarning, match="CR"):
        assert load_role_templates(path)["government"].ahp.cr >= 0.1  # type: ignore[union-attr]
    for args in ([str(path)], [str(tmp_path)], ["--rules-dir", str(tmp_path)]):
        assert check.main(args) == 0
        output = capsys.readouterr().out
        assert "警告" in output and "CR =" in output
        assert "government" in output
        assert "1 个文件，0 个错误，1 个警告" in output
        assert "顶层必须是一个规则列表" not in output
    assert check.main([]) == 0
    default_output = capsys.readouterr().out
    # 2026-10 专业组核定后，仓库的权重模板不再有占位警告；
    # 这里只要求默认路径确实把 weights.yaml 纳入校验并且通过。
    assert "weights.yaml" in default_output
    assert "0 个错误，0 个警告" in default_output
    # 不互反属于错误，必须退出 1；不能把 developer 误报成缺少角色。
    a[0][1] = 3
    _write_roles(path, {"name": "互反错误", "matrix": a})
    assert check.main([str(path)]) == 1
    assert "互反" in capsys.readouterr().out


def test_weights_yaml_errors_and_missing_roles(tmp_path: Path) -> None:
    path = tmp_path / "weights.yaml"
    path.write_text("government:\n\tname: 测试", encoding="utf-8")
    assert check_weights_file(path)[1][0].code == "WEIGHTS_YAML_PARSE"
    path.write_text("{}", encoding="utf-8")
    assert check_weights_file(path)[1][0].code == "WEIGHTS_MISSING_ROLE"
