"""T9 指南示例的回归测试。

保证三件事：
1. ``docs/rules-guide.md`` 里所有「正确示例」都能通过 ``check_rules``；
2. ``_bad/`` 下每个错误示例都触发对应错误码；
3. ``docs/fields.generated.md`` 与当前 JSON Schema 同步（防止文档漂移）。
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUIDE_FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "guide_examples"
GOOD_DIR = GUIDE_FIXTURES  # 顶层 6 个文件都是「正确示例」
BAD_DIR = GUIDE_FIXTURES / "_bad"
FIELDS_MD = ROOT / "docs" / "fields.generated.md"
CHECK_RULES = ROOT / "scripts" / "check_rules.py"
GEN_FIELD_TABLE = ROOT / "scripts" / "gen_field_table.py"


def _run_script(script: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    """跑 ``uv run --project backend python <script>`` 并捕获 stdout/stderr。"""
    cmd = [
        "uv",
        "run",
        "--project",
        "backend",
        "python",
        str(script.relative_to(ROOT)),
        *extra_args,
    ]
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# —— 1. 6 个正确示例必须全部通过 check_rules —— #


@pytest.mark.parametrize(
    "filename",
    [
        "hard_simple.yaml",
        "hard_derived.yaml",
        "hard_when.yaml",
        "metric_bigger_is_better.yaml",
        "metric_smaller_is_better.yaml",
        "metric_optimal_in_middle.yaml",
    ],
)
def test_valid_examples_pass_check_rules(filename: str) -> None:
    """``docs/rules-guide.md`` 引用的 6 个示例必须 exit code 0。"""
    result = _run_script(CHECK_RULES, str(GOOD_DIR / filename))
    assert result.returncode == 0, (
        f"{filename} 应当通过校验但报错了：\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# —— 2. 错误示例触发对应的 ERROR / WARNING —— #


# 每个错误示例 → 必须出现的错误码
BAD_CASES: list[tuple[str, list[str]]] = [
    (
        "hard_tab_indent.yaml",
        ["TAB_INDENT", "YAML_PARSE"],
    ),
    (
        "hard_chinese_colon.yaml",
        ["CHINESE_COLON"],
    ),
    (
        "hard_unaligned.yaml",
        ["UNALIGNED"],
    ),
    (
        "hard_missing_field.yaml",
        ["MISSING_FIELD"],
    ),
    (
        "metric_points_not_monotonic.yaml",
        ["METRIC_POINTS_NOT_MONOTONIC"],
    ),
    (
        "metric_missing_dimension.yaml",
        ["METRIC_BAD_DIMENSION"],
    ),
]


@pytest.mark.parametrize(
    "filename, expected_codes",
    BAD_CASES,
    ids=[c[0] for c in BAD_CASES],
)
def test_bad_examples_fail_with_expected_codes(
    filename: str, expected_codes: list[str]
) -> None:
    """每个错误示例至少触发一个期望的错误码，且 exit code = 1。"""
    result = _run_script(CHECK_RULES, str(BAD_DIR / filename))
    assert result.returncode == 1, (
        f"{filename} 应当报错但 exit 0：\nSTDOUT:\n{result.stdout}"
    )
    combined = result.stdout + result.stderr
    missing = [code for code in expected_codes if code not in combined]
    assert not missing, (
        f"{filename} 缺少期望错误码 {missing}；\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# —— 3. 字段对照表与当前 JSON Schema 同步 —— #


def test_field_table_exists_and_nonempty() -> None:
    """``docs/fields.generated.md`` 必须存在且含派生量段。"""
    assert FIELDS_MD.exists(), "字段对照表未生成，请跑 gen_field_table.py"
    content = FIELDS_MD.read_text(encoding="utf-8")
    assert "派生量" in content
    assert "shape_coefficient" in content
    assert "ProjectParams" in content
    assert "SchemeParams" in content


def test_gen_field_table_is_idempotent() -> None:
    """``gen_field_table.py --check`` 必须返回 0（脚本输出与磁盘一致）。"""
    result = _run_script(GEN_FIELD_TABLE, "--check")
    assert result.returncode == 0, (
        "字段对照表与 JSON Schema 漂移，请执行：\n"
        "  uv run --project backend python scripts/gen_field_table.py\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


# —— 4. 校验 ``check_rules`` 加载模块本身可用 —— #


def test_check_rules_module_importable() -> None:
    """``scripts/check_rules`` 应当作为模块可导入，方便其它脚本复用。"""
    sys.path.insert(0, str(ROOT))
    # 重置模块缓存，避免多次测试互相污染
    sys.modules.pop("scripts.check_rules", None)
    mod = importlib.import_module("scripts.check_rules")
    assert mod.main.__name__ == "main"
    assert mod.VALID_DIMENSIONS == ("quality", "structure", "construction", "green")


def test_check_rules_lists_all_yaml_files_in_dir() -> None:
    """``iter_rule_files`` 应枚举目录下所有 .yaml/.yml（除 weights.yaml）。"""
    sys.path.insert(0, str(ROOT))
    sys.modules.pop("scripts.check_rules", None)
    mod = importlib.import_module("scripts.check_rules")
    files = sorted(p.name for p in mod.iter_rule_files(GOOD_DIR))
    assert "weights.yaml" not in files  # 即便有也跳过
    assert "hard_simple.yaml" in files
    assert "metric_optimal_in_middle.yaml" in files
