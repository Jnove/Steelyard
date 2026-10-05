"""``scripts/check_rules.py`` 的测试。

这个脚本是给非程序员用的，所以测试重点不只是"报没报错"，还包括：
- 报错格式是不是 ``文件名:行号 规则ID — 中文说明 — 怎么改``；
- 行号是不是**真实行号**（而不是"第几条规则"）；
- 有错误退出码 1、只有警告退出码 0。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BAD_RULES = ROOT / "backend" / "tests" / "fixtures" / "rules_bad"
GOOD_RULES = ROOT / "backend" / "tests" / "fixtures" / "rules_good"
REPO_RULES = ROOT / "rules"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
check_rules = importlib.import_module("scripts.check_rules")


def _codes(path: Path) -> list[str]:
    """跑一遍校验，返回内部错误码列表（顺序即出现顺序）。"""
    return [issue.code for issue in check_rules.check_file(path).issues]


def _issues(path: Path, code: str) -> list[object]:
    return [i for i in check_rules.check_file(path).issues if i.code == code]


# —— 正常路径 —— #


def test_good_fixture_has_no_issues() -> None:
    report = check_rules.check_file(GOOD_RULES / "engine.yaml")
    assert report.issues == [], report.render()
    assert not report.has_errors


def test_repo_seed_rules_have_no_errors() -> None:
    """仓库里 rules/ 下的种子规则不许有 ERROR（TODO 警告是允许的）。"""
    for path in check_rules.iter_rule_files(REPO_RULES):
        report = check_rules.check_file(path)
        assert not report.has_errors, report.render()


def test_seed_rules_exit_code_is_zero_with_only_warnings() -> None:
    """只有警告时退出码必须是 0——否则 CI 会因为 TODO 出处而一直红。"""
    assert check_rules.main([str(REPO_RULES)]) == 0


def test_errors_exit_code_is_one() -> None:
    assert check_rules.main([str(BAD_RULES / "points_not_monotonic.yaml")]) == 1


def test_skips_underscore_and_weights_files(tmp_path: Path) -> None:
    (tmp_path / "_template.yaml").write_text("草稿", encoding="utf-8")
    (tmp_path / "weights.yaml").write_text("权重模板", encoding="utf-8")
    (tmp_path / "quality.yaml").write_text("# 空", encoding="utf-8")
    names = [p.name for p in check_rules.iter_rule_files(tmp_path)]
    assert names == ["quality.yaml"]


def test_explicit_single_file_is_not_filtered() -> None:
    """显式指定文件时不做下划线过滤，方便校验模板本身。"""
    template = REPO_RULES / "_template.yaml"
    assert list(check_rules.iter_rule_files(template)) == [template]


# —— 每类错误都要被抓到 —— #


@pytest.mark.parametrize(
    "filename, expected_code",
    [
        ("tab_indent.yaml", "TAB_INDENT"),
        ("chinese_colon.yaml", "CHINESE_COLON"),
        ("missing_required.yaml", "MISSING_FIELD"),
        ("bad_rule_id.yaml", "BAD_RULE_ID"),
        ("unknown_field.yaml", "UNKNOWN_FIELD"),
        ("points_not_monotonic.yaml", "POINTS_NOT_MONOTONIC"),
        ("points_score_out_of_range.yaml", "POINT_SCORE_OUT_OF_RANGE"),
        ("expression_syntax.yaml", "BAD_EXPRESSION"),
        ("unknown_field_in_expression.yaml", "BAD_EXPRESSION"),
        ("bad_dimension.yaml", "BAD_ENUM_DIMENSION"),
        ("type_field_mismatch.yaml", "TYPE_FIELD_MISMATCH"),
        ("disallowed_function.yaml", "BAD_EXPRESSION"),
        ("top_not_list.yaml", "TOP_NOT_LIST"),
    ],
)
def test_bad_fixture_reports_expected_code(filename: str, expected_code: str) -> None:
    codes = _codes(BAD_RULES / filename)
    assert expected_code in codes, f"{filename} 实际报出 {codes}"


def test_duplicate_id_reported_with_both_locations() -> None:
    """重复 ID 要同时说出"另一处在哪"，否则作者得自己全仓库搜。"""
    report = check_rules.check_file(BAD_RULES / "duplicate_id.yaml")
    dupes = check_rules.check_duplicate_ids([(BAD_RULES / "duplicate_id.yaml", _compose(BAD_RULES / "duplicate_id.yaml"))])
    assert dupes, "应当报出重复 ID"
    _, issue = dupes[0]
    assert issue.rule_id == "C-01"
    assert "duplicate_id.yaml:2" in issue.message, issue.message
    assert issue.line == 8, "第二处 ID 在第 8 行"
    assert not report.has_errors, "单文件结构校验本身不查重复 ID，那是跨文件的一步"


def _compose(path: Path) -> object:
    import yaml

    return yaml.compose(path.read_text(encoding="utf-8"))


# —— 行号必须是真实行号 —— #


def test_tab_indent_points_at_real_lines() -> None:
    """``tab_indent.yaml`` 的 Tab 在第 4、5、6 行。"""
    lines = sorted(i.line for i in _issues(BAD_RULES / "tab_indent.yaml", "TAB_INDENT"))
    assert lines == [4, 5, 6]


def test_points_error_points_at_points_block() -> None:
    """``points`` 不递增时，行号应当落在 points 那几行，而不是规则第 1 行。

    这是 T3 相对 T9 的关键改进：以前打印的是"第几条规则"，
    在一个文件放多条规则时几乎没法定位。
    """
    issue = _issues(BAD_RULES / "points_not_monotonic.yaml", "POINTS_NOT_MONOTONIC")[0]
    assert issue.line is not None and issue.line >= 9, f"实际行号 {issue.line}"


def test_score_out_of_range_points_at_offending_point() -> None:
    """分数越界要指到出问题的那个控制点（第 11 行的 ``- [0.95, 120]``）。"""
    issue = _issues(BAD_RULES / "points_score_out_of_range.yaml", "POINT_SCORE_OUT_OF_RANGE")[0]
    assert issue.line == 11, f"实际行号 {issue.line}"


def test_unknown_field_points_at_that_field() -> None:
    """未知字段的行号要指到那一行（``serverity: warning`` 在第 6 行）。"""
    issue = _issues(BAD_RULES / "unknown_field.yaml", "UNKNOWN_FIELD")[0]
    assert issue.line == 6, f"实际行号 {issue.line}"


def test_expression_error_points_at_check_line() -> None:
    issue = _issues(BAD_RULES / "unknown_field_in_expression.yaml", "BAD_EXPRESSION")[0]
    assert issue.line == 5, f"实际行号 {issue.line}"


def test_multi_rule_file_reports_second_rule_line() -> None:
    """一个文件里多条规则时，第二条的报错不能指到第一条的行号。"""
    codes = check_rules.check_file(BAD_RULES / "duplicate_id.yaml")
    assert not codes.has_errors  # 这个 fixture 单文件层面是合法的
    # 换一个：两条规则，第二条 points 写错。
    import tempfile

    body = (
        '- id: K-01\n  name: 好的\n  type: metric\n  dimension: construction\n'
        '  value: "std_floor_repeat"\n  scoring:\n    kind: piecewise\n    points:\n'
        "      - [0.5, 0]\n      - [0.95, 100]\n  source: \"测试\"\n"
        '\n- id: K-02\n  name: 坏的\n  type: metric\n  dimension: construction\n'
        '  value: "component_types"\n  scoring:\n    kind: piecewise\n    points:\n'
        "      - [40, 0]\n      - [8, 100]\n  source: \"测试\"\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "construction.yaml"
        path.write_text(body, encoding="utf-8")
        issue = [i for i in check_rules.check_file(path).issues if i.code == "POINTS_NOT_MONOTONIC"][0]
        assert issue.rule_id == "K-02"
        assert issue.line is not None and issue.line >= 20, f"实际行号 {issue.line}"


# —— 报错格式 —— #


def test_render_format_matches_spec() -> None:
    """报错渲染格式：``严重程度  文件名:行号  规则ID — 中文说明 — 怎么改``。"""
    path = BAD_RULES / "points_not_monotonic.yaml"
    issue = _issues(path, "POINTS_NOT_MONOTONIC")[0]
    rendered = issue.render(path)
    assert rendered.startswith("错误  ")
    assert "rules_bad/points_not_monotonic.yaml:" in rendered
    assert " K-01 — " in rendered
    assert " — 怎么改：" in rendered


def test_warning_rendered_as_warning() -> None:
    path = REPO_RULES / "compliance.yaml"
    todo = [i for i in check_rules.check_file(path).issues if i.code == "SOURCE_TODO"][0]
    assert todo.render(path).startswith("警告  ")


def test_every_issue_has_message_and_fix() -> None:
    """每条问题都必须同时给出"错在哪"和"怎么改"——这是给非程序员的硬要求。"""
    for path in sorted(BAD_RULES.glob("*.yaml")):
        for issue in check_rules.check_file(path).issues:
            assert issue.message.strip(), f"{path.name} 有问题缺中文说明"
            assert issue.fix.strip(), f"{path.name} 的「{issue.code}」缺「怎么改」"


def test_messages_are_chinese() -> None:
    """报错正文必须是中文（含 CJK 字符），不能直接抛英文堆栈给规则作者。"""
    for path in sorted(BAD_RULES.glob("*.yaml")):
        for issue in check_rules.check_file(path).issues:
            assert any("一" <= ch <= "鿿" for ch in issue.message), (
                f"{path.name} 的「{issue.code}」报错不是中文：{issue.message}"
            )


# —— 拼写建议 —— #


def test_unknown_field_suggests_correct_spelling() -> None:
    issue = _issues(BAD_RULES / "unknown_field.yaml", "UNKNOWN_FIELD")[0]
    assert "severity" in issue.fix


def test_expression_typo_suggests_correct_field() -> None:
    issue = _issues(BAD_RULES / "unknown_field_in_expression.yaml", "BAD_EXPRESSION")[0]
    assert "floor_height" in issue.fix


def test_bad_dimension_suggests_valid_value() -> None:
    issue = _issues(BAD_RULES / "bad_dimension.yaml", "BAD_ENUM_DIMENSION")[0]
    assert any(d in issue.fix for d in check_rules.VALID_DIMENSIONS)


# —— 重复字段 —— #


def test_duplicate_key_in_one_rule_is_error(tmp_path: Path) -> None:
    """同一条规则里写了两个 ``check``：YAML 只认最后一个，必须报错。"""
    path = tmp_path / "compliance.yaml"
    path.write_text(
        '- id: C-01\n  name: 重复字段\n  type: hard\n'
        '  check: "floor_height >= 3.0"\n  check: "floor_height >= 2.8"\n  source: "测试"\n',
        encoding="utf-8",
    )
    codes = [i.code for i in check_rules.check_file(path).issues]
    assert "DUPLICATE_KEY" in codes


def test_same_key_across_rules_is_not_flagged(tmp_path: Path) -> None:
    """多条规则各写一个 ``id`` 不是重复字段——这是 T9 启发式的误报点。"""
    path = tmp_path / "compliance.yaml"
    body = '- id: C-01\n  name: A\n  type: hard\n  check: "floor_height >= 3.0"\n  source: "测试"\n'
    path.write_text(body + '\n- id: C-02\n  name: B\n  type: hard\n  check: "floors >= 1"\n  source: "测试"\n', encoding="utf-8")
    report = check_rules.check_file(path)
    assert "DUPLICATE_KEY" not in [i.code for i in report.issues], report.render()
    assert not report.has_errors, report.render()


# —— 模块可复用性 —— #


def test_module_exposes_stable_names() -> None:
    assert check_rules.VALID_DIMENSIONS == ("quality", "structure", "construction", "green")
    assert check_rules.main.__name__ == "main"
    assert callable(check_rules.check_file)
