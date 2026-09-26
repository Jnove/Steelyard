"""把 xlsx 导入到数据库。

用法：

    uv run python scripts/import_schemes.py <project_id> <xlsx_path>
    uv run python scripts/import_schemes.py <project_id> <xlsx_path> --allow-partial

行为：
- 默认任何一个错误就拒绝整文件（退出码非 0）。
- ``--allow-partial`` 时把可成功创建的方案写入数据库，失败的方案跳过并打印错误清单。
- 若方案名已存在于项目内，自动重命名为 ``原名 (2)`` / ``原名 (3)`` ...
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlmodel import Session, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.excel import ParseError, parse_workbook  # noqa: E402
from app.models import Project, Scheme, SchemeParams  # noqa: E402


def _format_errors(errors: list[ParseError]) -> str:
    lines: list[str] = []
    for e in errors:
        prefix = e.scheme or "项目"
        lines.append(f"  - {prefix} · 【{e.label}】{e.message}")
    return "\n".join(lines)


def _unique_name(session: Session, project_id: int, base: str) -> str:
    """项目内唯一化方案名；已存在时加 ``(n)`` 后缀。"""
    existing = {
        s.name
        for s in session.exec(
            select(Scheme).where(Scheme.project_id == project_id)
        ).all()
    }
    if base not in existing:
        return base
    n = 2
    while f"{base} ({n})" in existing:
        n += 1
    return f"{base} ({n})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 xlsx 导入方案到指定项目")
    parser.add_argument("project_id", type=int, help="目标项目 id")
    parser.add_argument("xlsx", type=Path, help="xlsx 文件路径")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="允许部分成功：跳过失败的方案，把能导入的写入数据库",
    )
    args = parser.parse_args(argv)

    if not args.xlsx.exists():
        print(f"ERROR · 文件不存在：{args.xlsx}", file=sys.stderr)
        return 2

    # 数据库初始化：脚本运行时不依赖 FastAPI lifespan。
    init_db()

    result = parse_workbook(args.xlsx)

    # 即使无方案，也打印项目层错误便于排查
    if result.errors and not args.allow_partial:
        # 看是否能凑出至少一个无错误的方案
        errors_by_scheme: dict[str, list[ParseError]] = {}
        for e in result.errors:
            if e.scheme is None:
                continue
            errors_by_scheme.setdefault(e.scheme, []).append(e)
        ok_count = sum(
            1 for s in result.schemes if s["name"] not in errors_by_scheme
        )
        if ok_count == 0:
            print(
                "导入失败：xlsx 含错误，未写入任何方案。", file=sys.stderr
            )
            print(_format_errors(result.errors), file=sys.stderr)
            return 1

    if not result.schemes:
        print("ERROR · xlsx 里没有任何方案列（方案A-方案F 都为空）", file=sys.stderr)
        return 1

    engine = get_engine()
    with Session(engine) as session:
        project = session.get(Project, args.project_id)
        if project is None:
            print(f"ERROR · 项目 {args.project_id} 不存在", file=sys.stderr)
            return 2

        # 如果有项目参数且当前项目空，更新之（仅在用户没显式提供时应用）
        if result.project_params and not project.params:
            project.params = result.project_params
            project.updated_at = datetime.now(UTC)
            session.add(project)

        # 把错误按方案分组，便于 partial 模式跳过
        errors_by_scheme: dict[str, list[ParseError]] = {}
        for e in result.errors:
            if e.scheme is None:
                continue
            errors_by_scheme.setdefault(e.scheme, []).append(e)

        created = 0
        for scheme_data in result.schemes:
            name = scheme_data["name"]
            errs = errors_by_scheme.get(name, [])
            if errs and not args.allow_partial:
                continue  # 整文件已在上方 reject，这里仅作防御
            if errs:
                print(f"-- 跳过【{name}】:", file=sys.stderr)
                for e in errs:
                    print(f"     · 【{e.label}】{e.message}", file=sys.stderr)
                continue
            unique = _unique_name(session, args.project_id, name)
            try:
                params = SchemeParams.model_validate(scheme_data["params"])
            except Exception as exc:
                print(
                    f"ERROR · 方案【{name}】参数校验失败：{exc}",
                    file=sys.stderr,
                )
                continue
            scheme = Scheme(
                project_id=args.project_id,
                name=unique,
                params=params.model_dump(),
            )
            session.add(scheme)
            created += 1

        session.commit()

    print(f"OK · 创建 {created} 个方案")
    if result.errors and args.allow_partial:
        print("以下方案因错误被跳过：", file=sys.stderr)
        print(_format_errors(result.errors), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())