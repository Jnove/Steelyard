"""导出字段元信息与用于 TypeScript 生成的标准 JSON Schema。

根目录的增强 schema 与 ``GET /api/schema`` 返回内容一致，供表单 / Excel
模板生成器使用；``jsonschema/`` 保留嵌套类型和约束，供 TypeScript 生成使用。

运行：

    uv run --project backend python scripts/export_schema.py

输出：

    data/schema/project.schema.json
    data/schema/scheme.schema.json
    data/schema/eval.schema.json
    data/schema/jsonschema/<ClassName>.schema.json
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

from app.agents.state import AgentOutput, AgentRequest  # noqa: E402
from app.api.evaluate import EvaluateResponse  # noqa: E402
from app.api.projects import ProjectCreate, ProjectRead  # noqa: E402
from app.api.rank import RankRequest, RankResponse  # noqa: E402
from app.api.rules import RulesResponse  # noqa: E402
from app.api.schemes import ImportResponse, SchemeCreate, SchemeRead  # noqa: E402
from app.models import EvalResult, ProjectParams, SchemeParams  # noqa: E402
from app.schemas.meta import enriched_schema  # noqa: E402

OUT_DIR = ROOT / "data" / "schema"
JSON_SCHEMA_MODELS = (
    ProjectParams,
    SchemeParams,
    EvalResult,
    ProjectRead,
    ProjectCreate,
    SchemeRead,
    SchemeCreate,
    EvaluateResponse,
    RulesResponse,
    ImportResponse,
    RankRequest,
    RankResponse,
    AgentRequest,
    AgentOutput,
)


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

    jsonschema_dir = OUT_DIR / "jsonschema"
    jsonschema_dir.mkdir(parents=True, exist_ok=True)
    for model in JSON_SCHEMA_MODELS:
        schema = model.model_json_schema()
        # 使用稳定的英文类名生成 TS 类型；保留中文 description 和字段元信息。
        schema["title"] = model.__name__
        for name, definition in schema.get("$defs", {}).items():
            definition["title"] = name
        if model in (RankResponse, AgentOutput):
            # model_dump 的响应包含默认字段；避免 TS 把 always-present 的数组当成可缺项。
            for definition in (schema, *schema.get("$defs", {}).values()):
                if "properties" in definition:
                    definition["required"] = list(definition["properties"])
        path = jsonschema_dir / f"{model.__name__}.schema.json"
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  wrote {path}")

    print(f"OK · {len(targets) + len(JSON_SCHEMA_MODELS)} files under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
