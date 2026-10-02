"""把数据库里的项目 + 方案导出为 xlsx，方便专业同学修改后再导入。

用法：

    uv run python scripts/export_schemes.py <project_id>
    uv run python scripts/export_schemes.py <project_id> --out my.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlmodel import Session, select  # noqa: E402

from app.db import get_engine, init_db  # noqa: E402
from app.excel import write_export  # noqa: E402
from app.models import Project, Scheme  # noqa: E402

# 默认输出 = 当前工作目录下的 data/schemes/，便于在不同环境（开发机 / CI）下都用本地路径
DEFAULT_OUT = Path("data") / "schemes" / "export_{project_id}.xlsx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从数据库导出方案为 xlsx")
    parser.add_argument("project_id", type=int, help="目标项目 id")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"输出路径（默认 {DEFAULT_OUT.name}）",
    )
    args = parser.parse_args(argv)

    init_db()
    engine = get_engine()
    with Session(engine) as session:
        project = session.get(Project, args.project_id)
        if project is None:
            print(f"ERROR · 项目 {args.project_id} 不存在", file=sys.stderr)
            return 2
        schemes_rows = session.exec(
            select(Scheme).where(Scheme.project_id == args.project_id)
        ).all()
        schemes_payload = [
            {"name": s.name, "params": s.params or {}} for s in schemes_rows
        ]

    out_path = args.out or DEFAULT_OUT.with_name(
        DEFAULT_OUT.name.format(project_id=args.project_id)
    )
    write_export(out_path, project.params or {}, schemes_payload)
    print(f"OK · wrote {out_path}")
    print(f"     · 项目 {project.id}「{project.name}」")
    print(f"     · 方案数 {len(schemes_payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())