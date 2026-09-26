"""把 ``data/schemes/mock/`` 下的虚构项目与方案导入数据库。

用途：
- 引擎、前端与演示调试用的样例数据。
- 这些数据是虚构的，**绝不用于验证或答辩**。

用法：

    make seed                                       # 默认从仓库根目录读 data/schemes/mock/
    uv run python scripts/seed_mock.py              # 同上
    uv run python scripts/seed_mock.py --mock-dir <dir>

行为：
- 每次执行都是「清空 + 导入」：若数据库里已存在同名项目（``杭州钱塘 · 保障性租赁住房 · 虚构示例项目``），
  会先把它连带其下所有方案与评估结果删掉，再写入新数据。其它项目不会被影响。
- 写入完成后会打印项目 id 与每个方案的 id，便于在 ``/docs`` 里直接点开看。
- ``--dry-run`` 模式下只读 + 校验 JSON，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import get_engine, init_db  # noqa: E402
from app.models import EvalResultRow, Project, Scheme, SchemeParams  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

#: 项目层数据文件名（位于 mock 目录）。
PROJECT_FILE = "project.json"
#: 方案文件名（位于 mock 目录）。每个方案的 ``name`` 字段就是写入数据库后的方案名。
SCHEME_FILES: tuple[str, ...] = (
    "A_高品质.json",
    "B_不合规.json",
    "C_MiC高标准化.json",
    "D_均衡.json",
    "E_被支配.json",
)
#: what-if 副本文件名；写入时挂到对应原方案之下。
WHATIF_FILE = "C_现浇.json"
#: what-if 副本指向的原方案名（与 SCHEME_FILES 里某一项的 ``name`` 完全一致）。
WHATIF_PARENT_NAME = "C MiC 高标准化"
#: 默认清空目标项目名（项目 JSON 里的 ``name`` 字段）。
DEFAULT_PROJECT_NAME = "杭州钱塘 · 保障性租赁住房 · 虚构示例项目"
#: 顶层必填字段；缺失就报错并退出，避免静默导入残缺数据。
REQUIRED_TOP_KEYS = ("_note", "name", "params")
NOTE_PREFIX = "虚构数据"


def _mock_dir() -> Path:
    return ROOT / "data" / "schemes" / "mock"


def _load_json(path: Path) -> dict:
    """读取 JSON，文件名 / 编码错误给出可定位的报错。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR · 找不到文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR · {path} 不是合法 JSON：{exc}") from exc


def _check_note(payload: dict, path: Path) -> None:
    """检查每个 JSON 都带虚构声明。"""
    note = payload.get("_note")
    if not isinstance(note, str) or NOTE_PREFIX not in note:
        raise SystemExit(
            f"ERROR · {path.name} 缺少 _note 声明（必须以「{NOTE_PREFIX}」开头，"
            "防止误把虚构数据用于验证）"
        )


def _check_top_level(payload: dict, path: Path) -> None:
    for key in REQUIRED_TOP_KEYS:
        if key not in payload:
            raise SystemExit(f"ERROR · {path.name} 缺少顶层字段 {key!r}")
    if not isinstance(payload["params"], dict):
        raise SystemExit(f"ERROR · {path.name} 的 params 必须是对象")


def load_project_payload(mock_dir: Path) -> dict:
    """读取并校验项目 JSON。"""
    path = mock_dir / PROJECT_FILE
    payload = _load_json(path)
    _check_note(payload, path)
    _check_top_level(payload, path)
    return payload


def load_scheme_payloads(mock_dir: Path) -> tuple[list[tuple[dict, Path]], tuple[dict, Path] | None]:
    """读取并校验所有方案 JSON。what-if 单独返回，便于写入时挂上 parent_id。

    返回值：
    - ``schemes`` 是 ``(payload, 源文件路径)`` 的列表，按 SCHEME_FILES 顺序；
    - ``whatif`` 是 ``(payload, 源文件路径)`` 或 ``None``。
    """
    schemes: list[tuple[dict, Path]] = []
    for filename in SCHEME_FILES:
        path = mock_dir / filename
        payload = _load_json(path)
        _check_note(payload, path)
        _check_top_level(payload, path)
        schemes.append((payload, path))

    whatif: tuple[dict, Path] | None = None
    whatif_path = mock_dir / WHATIF_FILE
    if whatif_path.exists():
        payload = _load_json(whatif_path)
        _check_note(payload, whatif_path)
        _check_top_level(payload, whatif_path)
        whatif = (payload, whatif_path)
    return schemes, whatif


def _validate_scheme_payload(payload: dict, path: Path) -> SchemeParams:
    """用 Pydantic 重新校验一次，发现问题就退出（带定位信息）。"""
    try:
        return SchemeParams.model_validate(payload["params"])
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"ERROR · {path.name}（{payload.get('name', '?')}）"
            f"参数未通过 SchemeParams 校验：\n{exc}"
        ) from exc


def _wipe_existing_project(session: Session, project_name: str) -> int | None:
    """若数据库里已有同名项目，先把它连同方案 / 评估结果一起删掉。返回被删项目的旧 id。"""
    existing = session.exec(select(Project).where(Project.name == project_name)).first()
    if existing is None:
        return None
    old_id = existing.id
    for scheme in session.exec(
        select(Scheme).where(Scheme.project_id == old_id)
    ).all():
        for ev in session.exec(
            select(EvalResultRow).where(EvalResultRow.scheme_id == scheme.id)
        ).all():
            session.delete(ev)
        session.delete(scheme)
    session.delete(existing)
    return old_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把虚构项目与方案导入数据库")
    parser.add_argument(
        "--mock-dir",
        type=Path,
        default=_mock_dir(),
        help="mock 数据目录（默认 data/schemes/mock/）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只读取并校验 JSON，不写数据库",
    )
    args = parser.parse_args(argv)

    mock_dir: Path = args.mock_dir
    if not mock_dir.is_dir():
        raise SystemExit(f"ERROR · mock 目录不存在：{mock_dir}")

    project_payload = load_project_payload(mock_dir)
    scheme_pairs, whatif_pair = load_scheme_payloads(mock_dir)

    # 全部用 Pydantic 再校验一次，提前报告问题。
    for payload, path in scheme_pairs:
        _validate_scheme_payload(payload, path)
    if whatif_pair is not None:
        whatif_payload, whatif_path = whatif_pair
        _validate_scheme_payload(whatif_payload, whatif_path)

    print(f"已读取 {len(scheme_pairs)} 套方案 + {1 if whatif_pair else 0} 个 what-if")

    if args.dry_run:
        print("DRY-RUN · 未写入数据库")
        return 0

    init_db()
    engine = get_engine()

    with Session(engine) as session:
        old_id = _wipe_existing_project(session, project_payload["name"])
        if old_id is not None:
            print(f"已清空旧项目 id={old_id}（含其下所有方案 / 评估结果）")

        project = Project(
            name=project_payload["name"],
            params=project_payload["params"],
            updated_at=datetime.now(UTC),
        )
        session.add(project)
        session.flush()  # 拿到 id

        scheme_by_name: dict[str, Scheme] = {}
        for payload, _path in scheme_pairs:
            scheme = Scheme(
                project_id=project.id,  # type: ignore[arg-type]
                name=payload["name"],
                params=payload["params"],
            )
            session.add(scheme)
            session.flush()
            scheme_by_name[payload["name"]] = scheme

        whatif_id: int | None = None
        if whatif_pair is not None:
            whatif_payload, _path = whatif_pair
            parent = scheme_by_name.get(WHATIF_PARENT_NAME)
            if parent is None:
                raise SystemExit(
                    f"ERROR · 找不到 what-if 父方案「{WHATIF_PARENT_NAME}」，"
                    f"请确认它出现在 SCHEME_FILES 中且 name 完全一致"
                )
            whatif_scheme = Scheme(
                project_id=project.id,  # type: ignore[arg-type]
                name=whatif_payload["name"],
                params=whatif_payload["params"],
                is_whatif=True,
                parent_id=parent.id,
            )
            session.add(whatif_scheme)
            session.flush()
            whatif_id = whatif_scheme.id

        session.commit()

        print(f"OK · 写入项目 id={project.id}「{project.name}」")
        for name, scheme in scheme_by_name.items():
            print(f"     · 方案 id={scheme.id}「{name}」")
        if whatif_id is not None and whatif_pair is not None:
            whatif_payload, _path = whatif_pair
            parent = scheme_by_name[WHATIF_PARENT_NAME]
            print(
                f"     · what-if id={whatif_id}「{whatif_payload['name']}」"
                f"（父方案 id={parent.id}「{parent.name}」）"
            )

    print()
    print("下一步：")
    print("  · 打开 http://127.0.0.1:8000/docs 看接口")
    print(f"  · GET  /api/projects/{'<id>'}/schemes 查 5 套方案（默认不含 what-if）")
    print(f"  · GET  /api/projects/{'<id>'}/schemes?include_whatif=true  查全部 6 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())