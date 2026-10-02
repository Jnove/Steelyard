"""把 ProjectParams / SchemeParams / EvalResult 的字段 schema 写到 ``data/schema/``。

供前端 / Excel 模板生成器使用；与 ``GET /api/schema`` 返回内容一致。

运行：

    uv run python scripts/export_schema.py

输出：

    data/schema/project.schema.json
    data/schema/scheme.schema.json
    data/schema/eval.schema.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 把 backend/ 加入 import path，让 ``app.*`` 能被找到
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import EvalResult, ProjectParams, SchemeParams  # noqa: E402
from app.schemas.meta import enriched_schema  # noqa: E402

OUT_DIR = ROOT / "data" / "schema"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = {
        "project.schema.json": ProjectParams,
        "scheme.schema.json": SchemeParams,
        "eval.schema.json": EvalResult,
    }

    for filename, model in targets.items():
        path = OUT_DIR / filename
        path.write_text(
            json.dumps(enriched_schema(model), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  wrote {path}")

    print(f"OK · 3 files under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())