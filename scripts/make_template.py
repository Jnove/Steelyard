"""生成方案录入 Excel 模板。

用法：

    uv run python scripts/make_template.py            # 写到默认路径 data/schemes/方案录入模板.xlsx
    uv run python scripts/make_template.py --out other.xlsx

模板字段从 ``app.models`` 的字段元信息自动生成，参数表改了之后重新运行此脚本即可。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.excel import write_template  # noqa: E402

# 默认输出 = 当前工作目录下的 data/schemes/，便于在不同环境（开发机 / CI）下都用本地路径
DEFAULT_OUT = Path("data") / "schemes" / "方案录入模板.xlsx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成方案录入 Excel 模板")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"输出路径（默认 {DEFAULT_OUT}，相对当前工作目录）",
    )
    args = parser.parse_args(argv)

    out_path = write_template(args.out)
    print(f"OK · wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())