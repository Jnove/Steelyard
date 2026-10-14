"""把 ``data/schemes/mock/`` 下的虚构项目与方案导入数据库。

用途：
- 引擎、前端与演示调试用的样例数据。
- 这些数据是虚构的，**绝不用于验证或答辩**。

用法：

    make seed                                       # 默认从仓库根目录读 data/schemes/mock/
    uv run --project backend python scripts/seed_mock.py  # 同上（Makefile 展开形式）
    uv run --project backend python scripts/seed_mock.py --mock-dir <dir>
    uv run --project backend python scripts/seed_mock.py --dry-run

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

#: 项目层数据文件名（位于案例目录）。
PROJECT_FILE = "project.json"
#: 默认方案文件名（仅用于 ``data/schemes/mock/`` 这套老样例）。
#: 其它案例目录改为**按目录内容自动发现**：除 ``project.json`` 外全部 ``*.json``
#: 按文件名排序即写入顺序，文件名含 ``whatif`` 的当作 what-if 副本。
SCHEME_FILES: tuple[str, ...] = (
    "A_高品质.json",
    "B_不合规.json",
    "C_MiC高标准化.json",
    "D_均衡.json",
    "E_被支配.json",
)
#: 默认 what-if 副本文件名；写入时挂到对应原方案之下。
WHATIF_FILE = "C_现浇.json"
#: 默认 what-if 副本指向的原方案名（仅老样例用；新样例在 what-if JSON 里写
#: 顶层字段 ``_whatif_parent`` 指定父方案名）。
WHATIF_PARENT_NAME = "C MiC 高标准化"
#: 默认清空目标项目名（项目 JSON 里的 ``name`` 字段）。仅老样例用；
#: 其它目录一律以本项目 JSON 的 ``name`` 作为清空目标，不再需要额外配置。
DEFAULT_PROJECT_NAME = "杭州钱塘 · 保障性租赁住房 · 虚构示例项目"
#: 顶层必填字段；缺失就报错并退出，避免静默导入残缺数据。
REQUIRED_TOP_KEYS = ("_note", "name", "params")
#: 顶层 ``_note`` 必须命中其中一种来源声明：虚构数据，或「方案数值为演示自拟」。
NOTE_MARKERS = ("虚构数据", "演示自拟")


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
    """检查每个 JSON 都带来源声明（虚构数据，或方案数值为演示自拟）。"""
    note = payload.get("_note")
    if not isinstance(note, str) or not any(m in note for m in NOTE_MARKERS):
        raise SystemExit(
            f"ERROR · {path.name} 的 _note 既没有「虚构数据」也没有「演示自拟」声明；"
            "案例数据必须显式标注来源性质，防止被当成工程结论"
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


def _is_default_mock_dir(mock_dir: Path) -> bool:
    """是不是 ``data/schemes/mock/`` 这套老样例（用写死的文件名清单）。"""
    try:
        return mock_dir.resolve() == _mock_dir().resolve()
    except OSError:  # pragma: no cover - 路径无法解析时按新目录处理
        return False


def discover_layout(mock_dir: Path) -> tuple[tuple[str, ...], str | None]:
    """给一个案例目录，返回 ``(方案文件名元组, what-if 文件名或 None)``。

    优先用目录里实际存在的文件，而不是写死的清单——新增案例
    （如 ``data/schemes/qiantang-real/``）不需要改任何脚本常量：

    - 除 ``project.json`` 外，所有 ``*.json`` 都是方案，按文件名排序即写入顺序；
    - 文件名里含 ``whatif`` 的当作 what-if 副本，其余为正式方案；
    - 以 ``_`` 开头的文件忽略（``_check.json`` 之类是产物，不是数据）；
    - 以 ``project`` 开头的文件都当项目层配置（``project.json`` 及其参数变体
      ``project_verified.json`` 等），不作为方案导入。

    名称为 ``whatif.json``（老样例的 ``C_现浇.json`` 除外）时也能识别。
    """
    names = sorted(
        p.name
        for p in mock_dir.glob("*.json")
        if not p.name.startswith(("_", "project"))
    )
    if not names:
        raise SystemExit(f"ERROR · {mock_dir} 下没有方案 JSON")

    legacy = _is_default_mock_dir(mock_dir)
    whatif_names = [
        n
        for n in names
        if ("whatif" in n.lower()) or (legacy and n == WHATIF_FILE)
    ]
    if len(whatif_names) > 1:
        raise SystemExit(
            f"ERROR · {mock_dir} 下有多个 what-if 文件：{whatif_names}；只允许一个"
        )
    scheme_names = tuple(n for n in names if n not in whatif_names)
    if not scheme_names:
        raise SystemExit(f"ERROR · {mock_dir} 下只有 what-if，没有正式方案")
    return scheme_names, (whatif_names[0] if whatif_names else None)


def resolve_whatif_parent(mock_dir: Path, whatif_payload: dict) -> str:
    """决定 what-if 副本挂到哪个方案下。

    规则（按优先级）：
    1. what-if JSON 里的顶层字段 ``_whatif_parent``（推荐，新案例都该写）；
    2. 老样例的常量 ``WHATIF_PARENT_NAME``。
    """
    declared = whatif_payload.get("_whatif_parent")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    if _is_default_mock_dir(mock_dir):
        return WHATIF_PARENT_NAME
    raise SystemExit(
        "ERROR · 非默认案例目录的 what-if 文件必须在顶层写 "
        '"_whatif_parent": "父方案名"（与某个方案 JSON 的 name 完全一致）'
    )


def load_scheme_payloads(
    mock_dir: Path, scheme_files: tuple[str, ...] | None = None
) -> tuple[list[tuple[dict, Path]], tuple[dict, Path] | None]:
    """读取并校验所有方案 JSON。what-if 单独返回，便于写入时挂上 parent_id。

    ``scheme_files`` 传 ``None`` 时按目录内容自动发现（见 :func:`discover_layout`）；
    老样例的测试会显式传 ``SCHEME_FILES``。

    返回值：
    - ``schemes`` 是 ``(payload, 源文件路径)`` 的列表，按写入顺序；
    - ``whatif`` 是 ``(payload, 源文件路径)`` 或 ``None``。
    """
    discovered, whatif_name = discover_layout(mock_dir)
    names = tuple(scheme_files) if scheme_files is not None else discovered

    schemes: list[tuple[dict, Path]] = []
    for filename in names:
        path = mock_dir / filename
        payload = _load_json(path)
        _check_note(payload, path)
        _check_top_level(payload, path)
        schemes.append((payload, path))

    whatif: tuple[dict, Path] | None = None
    if whatif_name is not None:
        whatif_path = mock_dir / whatif_name
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
        whatif_parent_name: str | None = None
        if whatif_pair is not None:
            whatif_payload, _path = whatif_pair
            whatif_parent_name = resolve_whatif_parent(mock_dir, whatif_payload)
            parent = scheme_by_name.get(whatif_parent_name)
            if parent is None:
                raise SystemExit(
                    f"ERROR · 找不到 what-if 父方案「{whatif_parent_name}」，"
                    f"请确认它是本目录某个方案 JSON 的 name 字段（完全一致）"
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
            parent = scheme_by_name[whatif_parent_name]  # type: ignore[index]
            print(
                f"     · what-if id={whatif_id}「{whatif_payload['name']}」"
                f"（父方案 id={parent.id}「{parent.name}」）"
            )

    print()
    print("下一步：")
    print("  · 打开 http://127.0.0.1:8000/docs 看接口")
    print(f"  · GET  /api/projects/{'<id>'}/schemes 查全部正式方案（默认不含 what-if）")
    print(f"  · GET  /api/projects/{'<id>'}/schemes?include_whatif=true  含 what-if 副本")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())