"""从 ``data/schema/*.schema.json`` 自动生成字段对照表。

输出位置：``docs/fields.generated.md``，给 ``docs/rules-guide.md`` 用。

为什么需要这个脚本
------------------
字段对照表若由人手维护，会随着模型迭代迅速漂移；本脚本每次都从 JSON Schema 重新渲染，
并提供 ``--check`` 选项供 CI 校验：磁盘上的生成产物与重新生成的内容必须一致，
否则退出码 1，提示维护者重新跑一次。

用法::

    uv run --project backend python scripts/gen_field_table.py            # 写到 docs/fields.generated.md
    uv run --project backend python scripts/gen_field_table.py --check    # CI 用：与磁盘内容一致才返回 0
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "data" / "schema"
OUT_PATH = ROOT / "docs" / "fields.generated.md"


@dataclass(frozen=True)
class DerivedQuantity:
    """引擎在评估时算出来的派生量，不在 Pydantic 模型里但规则可能引用。"""

    name: str
    label: str
    unit: str
    formula: str
    note: str = ""


#: 评估阶段会计算的派生量清单。改这里的同时建议在 ``docs/rules-guide.md`` 第 3 节里同步描述。
DERIVED_QUANTITIES: tuple[DerivedQuantity, ...] = (
    DerivedQuantity(
        name="shape_coefficient",
        label="体形系数",
        unit="—",
        formula="envelope_area / volume",
        note="外表面积与体积之比，越小越利于节能；规则 K-X 经常引用。",
    ),
    DerivedQuantity(
        name="units_per_building",
        label="单栋户数",
        unit="户/栋",
        formula="units / buildings",
        note="疏散与电梯服务的关键指标。",
    ),
    DerivedQuantity(
        name="units_per_floor",
        label="每层户数",
        unit="户/层",
        formula="units / (floors * buildings)",
        note="决定标准层交通核大小。",
    ),
    DerivedQuantity(
        name="total_height",
        label="建筑总高",
        unit="m",
        formula="floor_height * floors",
        note="用于与项目层 height_max 比较。",
    ),
    DerivedQuantity(
        name="floor_efficiency",
        label="楼层效率",
        unit="—",
        formula="footprint * floors / gfa",
        note="基底与层数对总建筑面积的利用率，越接近 1 越理想。",
    ),
)


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_constraints(constraints: dict[str, Any]) -> str:
    """把约束字典渲染成人类可读的中文短语。"""
    if not constraints:
        return "—"
    parts: list[str] = []
    if "minimum" in constraints:
        parts.append(f"≥ {constraints['minimum']}")
    if "maximum" in constraints:
        parts.append(f"≤ {constraints['maximum']}")
    if "exclusiveMinimum" in constraints:
        parts.append(f"> {constraints['exclusiveMinimum']}")
    if "exclusiveMaximum" in constraints:
        parts.append(f"< {constraints['exclusiveMaximum']}")
    if "minLength" in constraints:
        parts.append(f"长度 ≥ {constraints['minLength']}")
    if "maxLength" in constraints:
        parts.append(f"长度 ≤ {constraints['maxLength']}")
    return "，".join(parts) if parts else "—"


def _format_field(field: dict[str, Any]) -> str:
    """把单条字段渲染成 Markdown 表格行。"""
    name = field.get("name", "")
    label = field.get("label") or name
    unit = field.get("unit") or ""
    type_ = field.get("type", "—")
    required = "是" if field.get("required") else "否"
    if field.get("essential"):
        required = f"{required} · 必录"

    note_parts: list[str] = []
    if "enum" in field:
        note_parts.append(f"取值：{' / '.join(field['enum'])}")
    if "options" in field:
        note_parts.append(f"预设：{' / '.join(field['options'])}")
    note_parts.append(_format_constraints(field.get("constraints", {})))
    note = "；".join(note_parts)

    return f"| `{name}` | {label} | {unit} | {type_} | {required} | {note} |"


def render_project_section(schema: dict[str, Any]) -> str:
    """渲染项目参数一节。"""
    lines = [
        f"### {schema.get('title', '项目参数')}",
        "",
        schema.get("description", ""),
        "",
        "| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for field in schema.get("fields", []):
        lines.append(_format_field(field))
    return "\n".join(lines) + "\n"


def render_scheme_section(schema: dict[str, Any]) -> str:
    """渲染方案参数一节，并按 ``group_order`` 顺序给每个分组加小标题。"""
    title = schema.get("title", "方案参数")
    description = schema.get("description", "")
    group_order: list[str] = schema.get("group_order", [])  # type: ignore[arg-type]

    fields = list(schema.get("fields", []))
    by_group: dict[str, list[dict[str, Any]]] = {}
    for f in fields:
        by_group.setdefault(f.get("group") or "其他", []).append(f)

    out: list[str] = [f"### {title}", "", description, ""]

    # 先按 group_order 输出已存在的分组，剩下的（如果有）追加在末尾
    rendered_groups: set[str] = set()
    for group in group_order:
        if group not in by_group:
            continue
        out.append(f"#### {group}")
        out.append("")
        out.append("| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for f in by_group[group]:
            out.append(_format_field(f))
        out.append("")
        rendered_groups.add(group)

    leftover = set(by_group) - rendered_groups
    for group in sorted(leftover):
        out.append(f"#### {group}")
        out.append("")
        out.append("| 字段名 | 中文名 | 单位 | 类型 | 必填 | 说明 |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for f in by_group[group]:
            out.append(_format_field(f))
        out.append("")

    return "\n".join(out)


def render_eval_section(schema: dict[str, Any]) -> str:
    """渲染评估结果一节（顶层几个字段）。"""
    lines = [
        f"### {schema.get('title', '评估结果')}",
        "",
        schema.get("description", ""),
        "",
        "| 字段名 | 中文名 | 类型 | 必填 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field in schema.get("fields", []):
        name = field.get("name", "")
        label = field.get("label") or name
        type_ = field.get("type", "—")
        required = "是" if field.get("required") else "否"
        lines.append(f"| `{name}` | {label} | {type_} | {required} | — |")
    return "\n".join(lines) + "\n"


def render_derived_section() -> str:
    """渲染派生量说明段，规则里能引用的字段名在这里集中列出。"""
    lines = [
        "### 派生量（引擎在评估时计算，不在 Pydantic 模型里）",
        "",
        "规则和指标里可以直接用 ``value`` 引用下面的字段名，效果等同于评估时算出的数。",
        "",
        "| 字段名 | 中文名 | 单位 | 公式 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for q in DERIVED_QUANTITIES:
        lines.append(f"| `{q.name}` | {q.label} | {q.unit} | `{q.formula}` | {q.note} |")
    return "\n".join(lines) + "\n"


def render() -> str:
    """生成完整 Markdown 文档。"""
    project = _load_schema(SCHEMA_DIR / "project.schema.json")
    scheme = _load_schema(SCHEMA_DIR / "scheme.schema.json")
    eval_ = _load_schema(SCHEMA_DIR / "eval.schema.json")

    header = (
        "# 字段对照表（自动生成）\n"
        "\n"
        "> 本文件由 `scripts/gen_field_table.py` 从 `data/schema/*.schema.json` 渲染，"
        "**不要手改**。模型或字段元信息变更后，请重新运行脚本：\n"
        "> \n"
        "> ```bash\n"
        "> uv run --project backend python scripts/gen_field_table.py\n"
        "> ```\n"
        "\n"
        "CI 会跑 `gen_field_table.py --check`，结果与磁盘不一致即失败，"
        "防止文档与代码漂移。\n"
    )

    parts = [
        header,
        "",
        "## 一、项目参数（ProjectParams）",
        "",
        render_project_section(project),
        "## 二、方案参数（SchemeParams）",
        "",
        render_scheme_section(scheme),
        "## 三、评估结果（EvalResult）",
        "",
        render_eval_section(eval_),
        "## 四、派生量",
        "",
        render_derived_section(),
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 JSON Schema 渲染字段对照表")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_PATH,
        help=f"输出文件（默认 {OUT_PATH.relative_to(ROOT)}）",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查磁盘文件是否与重新生成结果一致；不一致退出码 1",
    )
    args = parser.parse_args(argv)

    # Windows 控制台 GBK 兜底：让中文 / 框线字符正确打印。
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

    content = render()

    if args.check:
        existing = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if existing != content:
            sys.stderr.write(
                f"ERROR · {args.out} 与重新生成结果不一致，请执行：\n"
                f"  uv run --project backend python scripts/gen_field_table.py\n"
            )
            # 写一份临时预览到 stderr 末尾，方便定位差异
            sys.stderr.write("\n--- 期望内容（首 20 行） ---\n")
            sys.stderr.write("\n".join(content.splitlines()[:20]))
            sys.stderr.write("\n")
            return 1
        print(f"OK · {args.out} 与 JSON Schema 同步")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    print(f"OK · wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
