"""Stable rule evidence version, independent of checkout paths and SQLite ids."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.custom import fields
from app.custom.rules import ruleset_with_custom
from app.engine.metrics import DERIVED_QUANTITIES
from app.engine.rules import RuleSet
from app.models import ProjectParams, SchemeParams

SIGNATURE_KEY = "_rules_signature"


@lru_cache(maxsize=1)
def _static_semantics() -> dict[str, Any]:
    """模型与派生量定义在进程内固定；运行期字段和规则仍逐次读取。"""
    return {
        "models": [ProjectParams.model_json_schema(), SchemeParams.model_json_schema()],
        "derived": [
            {name: getattr(item, name) for name in ("name", "label", "unit", "formula", "deps", "note")}
            for item in DERIVED_QUANTITIES
        ],
    }


def project_ruleset(session: Session | None, params: ProjectParams) -> RuleSet:
    """本项目实际使用的规则；国家册和运行期 X- 规则始终保留。"""
    return ruleset_with_custom(session).select_packs(params.standard_packs or ["GB"])


def project_rules_signature(session: Session | None, params: ProjectParams) -> str:
    """有效规则定义与册选择共同决定证据版本，切换地区不能复用旧结果。"""
    selected = sorted(set(params.standard_packs or ["GB"]))
    evidence = {
        "version": "project-rules-evidence-v1",
        "packs": selected,
        "province": params.province,
        "definitions": rules_signature(session, ruleset=project_ruleset(session, params)),
    }
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        "custom_fields": custom_fields,
        **_static_semantics(),
    }
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require_rules_signature(payload: dict[str, Any], current: str) -> None:
    """Legacy and obsolete evidence must be explicitly recomputed, never relabeled."""
    if payload.get(SIGNATURE_KEY) != current:
        raise HTTPException(409, detail="评估使用的规则或字段版本已变更（或旧结果缺少版本记录），请先重新评估")
