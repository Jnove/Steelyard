"""Stable rule evidence version, independent of checkout paths and SQLite ids."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.custom import fields
from app.custom.rules import ruleset_with_custom
from app.engine.metrics import DERIVED_QUANTITIES
from app.engine.rules import RuleSet
from app.models import ProjectParams, SchemeParams

SIGNATURE_KEY = "_rules_signature"


def rules_signature(session: Session | None, *, ruleset: RuleSet | None = None) -> str:
    """Hash definitions and field semantics; exclude origins, ids and authorship."""
    current = ruleset if ruleset is not None else ruleset_with_custom(session)
    custom_fields = [] if session is None else [
        {name: getattr(row, name) for name in ("key", "kind", "unit", "options", "label", "description", "group")}
        for row in fields.list_fields(session)
    ]
    evidence = {
        "version": "rules-evidence-v1",
        "rules": [rule.model_dump(mode="json") for rule in current.rules],
        "models": [ProjectParams.model_json_schema(), SchemeParams.model_json_schema()],
        "custom_fields": custom_fields,
        "derived": [
            {name: getattr(item, name) for name in ("name", "label", "unit", "formula", "deps", "note")}
            for item in DERIVED_QUANTITIES
        ],
    }
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require_rules_signature(payload: dict[str, Any], current: str) -> None:
    """Legacy and obsolete evidence must be explicitly recomputed, never relabeled."""
    if payload.get(SIGNATURE_KEY) != current:
        raise HTTPException(409, detail="评估使用的规则或字段版本已变更（或旧结果缺少版本记录），请先重新评估")
