"""从根目录导出与从 backend 目录检查时，来源指纹必须一致。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_source_fingerprint_is_independent_of_script_entry_path() -> None:
    script = ROOT / "scripts/export_frontend_fixtures.py"
    spec = importlib.util.spec_from_file_location("fixture_export_under_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = module.source_hashes(ROOT)

    # Linux Python 保留这种绝对路径中的 ../；对应 CI 的实际调用方式。
    module.__file__ = str(ROOT / "backend/../scripts/export_frontend_fixtures.py")
    checked = module.source_hashes(ROOT)
    assert checked == generated
    assert "scripts/export_frontend_fixtures.py" in checked
    assert all(".." not in Path(key).parts for key in checked)
