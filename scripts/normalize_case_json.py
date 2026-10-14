"""把演示案例的方案 JSON 以 UTF-8（无 BOM）、2 空格缩进重写一遍。

用途：修完数值后用统一格式落盘，避免 PowerShell ``ConvertTo-Json`` 造成的
4 空格缩进、``\\u003e`` 转义与 BOM 差异。

用法：
    python scripts/normalize_case_json.py data/schemes/qiantang-real
    python scripts/normalize_case_json.py data/schemes/qiantang-real --check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize(path: Path, check: bool) -> bool:
    """返回 True 表示文件已符合规范（或被改写）。"""
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    canonical = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if text == canonical:
        return True
    if check:
        print(f"需要规范化：{path}")
        return False
    path.write_text(canonical, encoding="utf-8")
    print(f"已规范化：{path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统一案例 JSON 的编码与缩进")
    parser.add_argument("case", type=Path, help="案例目录")
    parser.add_argument("--check", action="store_true", help="只检查不写回")
    args = parser.parse_args(argv)

    if not args.case.is_dir():
        raise SystemExit(f"ERROR · 目录不存在：{args.case}")

    ok = True
    for path in sorted(args.case.glob("*.json")):
        if path.name.startswith("_"):
            continue
        ok = normalize(path, args.check) and ok
    if not ok:
        raise SystemExit("ERROR · 有文件未规范化（去掉 --check 可自动改写）")
    print("OK · 全部文件格式一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
