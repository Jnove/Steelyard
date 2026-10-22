"""Function calling 工具；跨项目隔离、参数校验与确定性引擎调用。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.agents.readable import builtin_labels
from app.agents.storage import AgentResultRow
from app.api.evaluate import evaluate_project, get_last_evaluation
from app.api.rank import RankRequest, _resolve_weights, rank_project
from app.config import get_settings
from app.custom import fields as fields_service
from app.custom.signature import (
    SIGNATURE_KEY,
    project_rules_signature,
    project_ruleset,
    require_rules_signature,
)
from app.custom.templates import list_templates
from app.engine.weights import get_role_templates
from app.models import EvalResult, Project, ProjectParams, Scheme, SchemeParams


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ProjectArgs(StrictModel):
    project_id: int = Field(gt=0)


class EvaluateArgs(ProjectArgs):
    include_whatif: bool = False


class RankArgs(EvaluateArgs):
    role: str | None = None
    weights: list[float] | None = None


class UpdateArgs(StrictModel):
    scheme_id: int = Field(gt=0)
    field: str
    value: Any
    expected_fingerprint: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")


class ExplainArgs(StrictModel):
    rule_id: str


class SearchArgs(StrictModel):
    query: str = Field(max_length=2000)
    k: int = Field(5, ge=1, le=20)


ARGUMENTS: dict[str, type[BaseModel]] = {
    "get_result": ProjectArgs,
    "update_scheme_param": UpdateArgs,
    "evaluate": EvaluateArgs,
    "rank": RankArgs,
    "explain_metric": ExplainArgs,
    "search_clause": SearchArgs,
}
DESCRIPTIONS = {
    "get_result": "读取本项目最近一次评估与排名；输入变更后要求重新评估。",
    "update_scheme_param": "校验字段和值后创建 what-if 副本，绝不修改原方案。",
    "evaluate": "调用规则引擎评估项目方案。",
    "rank": "仅调用决策引擎按角色或明确权重排序。",
    "explain_metric": "返回真实规则定义、公式及 source。",
    "search_clause": "条文检索桩，当前返回空列表，等待 T10。",
}


def tool_schemas(names: list[str] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": DESCRIPTIONS[name],
                "parameters": ARGUMENTS[name].model_json_schema(),
            },
        }
        for name in (names if names is not None else list(ARGUMENTS))
    ]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("参数不允许 NaN 或无穷大")
    if isinstance(value, dict):
        for item in value.values():
            _reject_nonfinite(item)
    elif isinstance(value, list):
        for item in value:
            _reject_nonfinite(item)


class AgentTools:
    def __init__(self, engine: Engine, project_id: int) -> None:
        self.engine = engine
        self.project_id = project_id

    def field_labels(self) -> dict[str, str]:
        with Session(self.engine) as session:
            return {**builtin_labels(), **{row.key: row.label for row in fields_service.list_fields(session)}}

    def case_context(self, include_whatif: bool = False) -> dict[str, Any]:
        """读取案例出处与教学说明，供报告解释输入性质，不参与评分。"""
        with Session(self.engine) as session:
            project = self._require_project(session)
            query = select(Scheme).where(Scheme.project_id == self.project_id)
            if not include_whatif:
                query = query.where(Scheme.is_whatif == False)  # noqa: E712
            return {
                "project_notes": (project.params or {}).get("project_notes"),
                "scoring_exclusions": (project.params or {}).get("scoring_exclusions", []),
                "schemes": [{"scheme_id": str(row.id), "scheme_notes": (row.params or {}).get("scheme_notes")}
                            for row in session.exec(query.order_by(Scheme.id)).all()],
            }

    def _require_project(self, session: Session) -> Project:
        project = session.get(Project, self.project_id)
        if project is None:
            raise HTTPException(404, "项目不存在")
        return project

    def fingerprint(self, include_whatif: bool) -> str:
        with Session(self.engine) as session:
            return self._fingerprint(session, include_whatif, self.rule_definitions())

    def _fingerprint(self, session: Session, include_whatif: bool, rules: list[dict[str, Any]] | None = None) -> str:
        project = self._require_project(session)
        query = select(Scheme).where(Scheme.project_id == self.project_id)
        if not include_whatif:
            query = query.where(Scheme.is_whatif == False)  # noqa: E712
        schemes = session.exec(query.order_by(Scheme.id)).all()
        return digest(
            {
                "project": {"id": project.id, "name": project.name, "params": project.params},
                "schemes": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "params": s.params,
                        "is_whatif": s.is_whatif,
                        "parent_id": s.parent_id,
                    }
                    for s in schemes
                ],
                "rules": rules if rules is not None else [rule.model_dump(mode="json") for rule in project_ruleset(session, ProjectParams.model_validate(project.params or {})).rules],
                "custom_fields": [row.model_dump(mode="json") for row in fields_service.list_fields(session)],
                "rules_signature": project_rules_signature(session, ProjectParams.model_validate(project.params or {})),
            }
        )

    def require_fingerprint(self, expected: str | None) -> None:
        if expected is not None and expected != self.fingerprint(True):
            raise HTTPException(409, "方案或规则已变更，请重新预览并确认调整")

    def cache_key(self, request: RankRequest) -> str:
        # 读取权重定义与提示词；同组权重归一化后共享缓存。
        templates = {k: v.model_dump(mode="json") for k, v in get_role_templates().items()}
        prompts = {
            p.name: p.read_text(encoding="utf-8")
            for p in (Path(__file__).parent / "prompts").glob("*.md")
        }
        with Session(self.engine) as session:
            weights = _resolve_weights(request, session).model_dump(mode="json")
            # 运行期自定义的角色模板同样进缓存键：它一改，权重就变、结论也可能变；
            # 不带上它会出现"模板改了但报告还是旧结论"。
            custom_templates = [row.model_dump(mode="json") for row in list_templates(session)]
        return digest(
            {
                "version": "T8-v1",
                "data": self.fingerprint(request.include_whatif),
                "weights": weights,
                "custom_templates": custom_templates,
                "provider": get_settings().llm_provider,
                "model": get_settings().llm_model,
                "reasoning_effort": get_settings().llm_reasoning_effort,
                "templates": templates,
                "prompts": prompts,
                "include_whatif": request.include_whatif,
            }
        )

    def rule_definitions(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            params = ProjectParams.model_validate(self._require_project(session).params or {})
            return [rule.model_dump(mode="json") for rule in project_ruleset(session, params).rules]

    def scheme_count(self, include_whatif: bool) -> int:
        with Session(self.engine) as session:
            query = select(Scheme).where(Scheme.project_id == self.project_id)
            if not include_whatif:
                query = query.where(Scheme.is_whatif == False)  # noqa: E712
            return len(session.exec(query).all())

    def validate_inputs(self, include_whatif: bool) -> None:
        with Session(self.engine) as session:
            ProjectParams.model_validate(self._require_project(session).params)
            query = select(Scheme).where(Scheme.project_id == self.project_id)
            if not include_whatif:
                query = query.where(Scheme.is_whatif == False)  # noqa: E712
            for scheme in session.exec(query).all():
                params = SchemeParams.model_validate(scheme.params)
                fields_service.validate_values(session, params.custom, allow_inactive=True)

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in ARGUMENTS:
            raise ValueError("未知工具")
        args = ARGUMENTS[name].model_validate(arguments)
        _reject_nonfinite(arguments)
        if hasattr(args, "project_id") and args.project_id != self.project_id:
            raise ValueError("工具只允许访问当前项目")
        return getattr(self, name)(**args.model_dump())

    def get_result(self, project_id: int) -> dict[str, Any]:
        with Session(self.engine) as session:
            self._require_project(session)
            row = session.get(AgentResultRow, project_id)
            if row:
                params = ProjectParams.model_validate(self._require_project(session).params or {})
                require_rules_signature(row.evaluation, project_rules_signature(session, params))
                if row.fingerprint != self.fingerprint(row.include_whatif):
                    raise HTTPException(409, "项目数据或规则已变更，请先重新评估")
                public_evaluation = {key: value for key, value in row.evaluation.items() if key != SIGNATURE_KEY}
                return {"evaluation": public_evaluation, "ranking": row.ranking}
            # 支持引擎 REST 接口刚刚生成的结果；检查更新时间避免解释旧结果。
            evaluation = get_last_evaluation(project_id, session)
            if not evaluation.results:
                return {"evaluation": evaluation.model_dump(mode="json"), "ranking": {}}
            from app.models import EvalResultRow

            rows = session.exec(
                select(EvalResultRow).where(EvalResultRow.project_id == project_id)
            ).all()
            project = self._require_project(session)
            for row in rows:
                scheme = session.get(Scheme, row.scheme_id)
                if not scheme or max(
                    scheme.updated_at.replace(tzinfo=None), project.updated_at.replace(tzinfo=None)
                ) > row.created_at.replace(tzinfo=None):
                    raise HTTPException(409, "评估结果早于输入修改，请先重新评估")
            return {"evaluation": evaluation.model_dump(mode="json"), "ranking": {}}

    def planning_context(self, include_whatif: bool = False) -> dict[str, Any]:
        """Only identity and field metadata for intent resolution; no evaluation or writes."""
        with Session(self.engine) as session:
            self._require_project(session)
            query = select(Scheme).where(Scheme.project_id == self.project_id)
            if not include_whatif:
                query = query.where(Scheme.is_whatif == False)  # noqa: E712
            labels = self.field_labels()
            return {
                "schemes": [{"scheme_id": row.id, "name": row.name} for row in session.exec(query.order_by(Scheme.id)).all()],
                "fields": {key: {"label": labels.get(key, key), **value}
                           for key, value in SchemeParams.model_json_schema()["properties"].items()},
                "custom_fields": [{"key": row.key, "label": row.label, "kind": row.kind, "options": row.options}
                                  for row in fields_service.list_fields(session)],
            }

    def validate_preferences(self, role: str | None, weights: list[float] | None) -> list[float]:
        request = RankRequest(role=role, weights=weights if role is not None or weights is not None else [0.25] * 4)
        with Session(self.engine) as session:
            return _resolve_weights(request, session).weights

    def _prepare_scheme_change(
        self, session: Session, scheme_id: int, field: str, value: Any,
    ) -> tuple[Scheme, SchemeParams, Any]:
        """Shared read-only validation for preview and the eventual copy operation."""
        _reject_nonfinite(value)
        if field == "window_wall_ratio" and isinstance(value, dict):
            if any(
                isinstance(ratio, bool)
                or not isinstance(ratio, (int, float))
                or not 0 <= ratio <= 1
                for ratio in value.values()
            ):
                raise ValueError("各朝向窗墙比必须为 0–1 小数")
        if field == "unit_mix" and isinstance(value, dict):
            if any(
                isinstance(count, bool) or not isinstance(count, int) or count < 0
                for count in value.values()
            ):
                raise ValueError("各户型户数必须为非负整数")
        self._require_project(session)
        parent = session.get(Scheme, scheme_id)
        if parent is None or parent.project_id != self.project_id:
            raise ValueError("方案不属于当前项目")
        is_custom = field in fields_service.field_keys(session)
        if field not in SchemeParams.model_fields and not is_custom:
            raise ValueError("字段必须是内建设计参数或已注册的自定义字段")
        previous_custom = (parent.params or {}).get("custom", {})
        updated = {**parent.params, field: value}
        before = parent.params.get(field)
        if is_custom:
            updated = {**parent.params, "custom": {**previous_custom, field: value}}
            before = previous_custom.get(field)
        # 严格模式避免 bool 被当作数值；嵌套字段也经过完整模型校验。
        params = SchemeParams.model_validate(updated, strict=True)
        fields_service.validate_values(session, params.custom, previous=previous_custom)
        return parent, params, before

    def preview_scheme_change(self, scheme_id: int, field: str, value: Any) -> dict[str, Any]:
        with Session(self.engine) as session:
            parent, _, before = self._prepare_scheme_change(session, scheme_id, field, value)
            return {"scheme_name": parent.name, "field_label": self.field_labels().get(field, field),
                    "before": before, "after": value}

    def update_scheme_param(self, scheme_id: int, field: str, value: Any, expected_fingerprint: str | None = None) -> dict[str, Any]:
        with Session(self.engine) as session:
            if expected_fingerprint is not None:
                # SQLite serializes writers until commit, closing the check/copy race.
                # Use this same session for the fingerprint; nested sessions may roll back
                # the shared in-memory test connection or see a different snapshot.
                if self.engine.dialect.name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                if expected_fingerprint != self._fingerprint(session, True):
                    raise HTTPException(409, "方案或规则已变更，请重新预览并确认调整")
            parent, params, before = self._prepare_scheme_change(session, scheme_id, field, value)
            copy = Scheme(
                project_id=self.project_id,
                name=f"{parent.name}（假设推演）"[:200],
                params=params.model_dump(mode="json"),
                is_whatif=True,
                parent_id=parent.id,
            )
            session.add(copy)
            session.commit()
            session.refresh(copy)
            return {
                "scheme_id": copy.id,
                "parent_id": parent.id,
                "is_whatif": True,
                "field": field,
                "before": before,
                "after": value,
            }

    def evaluate(self, project_id: int, include_whatif: bool = False) -> dict[str, Any]:
        with Session(self.engine) as session:
            return evaluate_project(project_id, session, include_whatif).model_dump(mode="json")

    def rank(
        self,
        project_id: int,
        role: str | None = None,
        weights: list[float] | None = None,
        include_whatif: bool = False,
    ) -> dict[str, Any]:
        request = RankRequest(role=role, weights=weights, include_whatif=include_whatif)
        previous = self.get_result(project_id)
        with Session(self.engine) as session:
            query = select(Scheme).where(Scheme.project_id == project_id)
            if not include_whatif:
                query = query.where(Scheme.is_whatif == False)  # noqa: E712
            expected = {str(s.id) for s in session.exec(query).all()}
            evaluation = {
                **previous["evaluation"],
                "results": [
                    item
                    for item in previous["evaluation"]["results"]
                    if item["scheme_id"] in expected
                ],
            }
            if expected != {item["scheme_id"] for item in evaluation["results"]}:
                raise HTTPException(409, "本次候选集合的评估不完整，请先按 include_whatif 重新评估")
            result = rank_project(project_id, request, session).model_dump(mode="json")
            return result

    def explain_metric(self, rule_id: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            params = ProjectParams.model_validate(self._require_project(session).params or {})
            rules = project_ruleset(session, params).rules
        for rule in rules:
            if rule.id == rule_id:
                result = rule.model_dump(mode="json")
                result["formula"] = (
                    rule.check
                    if rule.type == "hard"
                    else {
                        "value": rule.value,
                        "scoring": rule.scoring.model_dump(mode="json") if rule.scoring else None,
                        "weight_in_dimension": rule.weight_in_dimension,
                    }
                )
                return result
        raise ValueError("规则 ID 不存在")

    def search_clause(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """TODO(专业组)：T10 接入有出处的真实条文，当前无检索结果。"""
        return []


def record_evaluation(
    session: Session, project_id: int, evaluation: dict[str, Any], include_whatif: bool,
    *, signature: str | None = None,
) -> None:
    """记录 REST 与智能体共同使用的最新评估。"""
    row = session.get(AgentResultRow, project_id) or AgentResultRow(
        project_id=project_id, fingerprint=""
    )
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail=f"项目 {project_id} 不存在")
    params = ProjectParams.model_validate(project.params or {})
    row.evaluation = {**evaluation, SIGNATURE_KEY: signature if signature is not None else project_rules_signature(session, params)}
    row.ranking = {}
    row.include_whatif = include_whatif
    row.fingerprint = AgentTools(session.get_bind(), project_id).fingerprint(include_whatif)
    session.add(row)
    session.commit()


def record_ranking(
    session: Session,
    project_id: int,
    ranking: dict[str, Any],
    include_whatif: bool,
    pairs: list[tuple[Scheme, EvalResult]],
) -> None:
    """记录 REST 权重滑杆或智能体产生的最新排名，保留同一候选集合的证据。"""
    row = session.get(AgentResultRow, project_id)
    tools = AgentTools(session.get_bind(), project_id)
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, detail=f"项目 {project_id} 不存在")
    params = ProjectParams.model_validate(project.params or {})
    signature = project_rules_signature(session, params)
    if row:
        require_rules_signature(row.evaluation, signature)
    if row and row.fingerprint != tools.fingerprint(row.include_whatif):
        raise HTTPException(409, "项目数据或规则已变更，请先重新评估")
    row = row or AgentResultRow(project_id=project_id, fingerprint="")
    row.evaluation = {
        "project_id": project_id,
        "rule_count": len(project_ruleset(session, params).rules),
        "results": [result.model_dump(mode="json") for _, result in pairs],
        SIGNATURE_KEY: signature,
    }
    row.ranking = ranking
    row.include_whatif = include_whatif
    row.fingerprint = AgentTools(session.get_bind(), project_id).fingerprint(include_whatif)
    session.add(row)
    session.commit()


def compare_whatif(
    baseline: dict[str, Any], current: dict[str, Any], change: dict[str, Any]
) -> dict[str, Any]:
    """仅比较并复制 T3/T4 值；不让模型计算差值或推测变化原因。"""
    results = {item["scheme_id"]: item for item in current["evaluation"]["results"]}
    parent = results[str(change["parent_id"])]
    copy = results[str(change["scheme_id"])]
    changed = []
    for rule, item in copy["metrics"].items():
        before = parent["metrics"].get(rule, {})
        if (before.get("value"), before.get("score")) != (item["value"], item["score"]):
            changed.append(
                {
                    "rule_id": rule,
                    "before_value": before.get("value"),
                    "after_value": item["value"],
                    "before_score": before.get("score"),
                    "after_score": item["score"],
                    "source": item["source"],
                }
            )

    def find_rank(evidence: dict[str, Any], scheme_id: str) -> int | None:
        return next(
            (
                item["rank"]
                for item in evidence["ranking"]["ranking"]
                if item["scheme_id"] == scheme_id
            ),
            None,
        )

    return {
        **change,
        "changed_metrics": changed,
        "parent_scores": parent["dimension_scores"],
        "copy_scores": copy["dimension_scores"],
        "baseline_rank": find_rank(baseline, str(change["parent_id"])),
        "parent_rank": find_rank(current, str(change["parent_id"])),
        "copy_rank": find_rank(current, str(change["scheme_id"])),
    }
