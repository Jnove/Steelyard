"""只读项目摘要与简短建议问题，不执行评估或修改方案。"""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.agents.citation import check_citations
from app.agents.readable import builtin_labels, humanize, reader_evidence, reader_questions
from app.agents.tools import AgentTools, digest
from app.engine.regions import pack_label
from app.models import Project, Scheme


class QuestionSuggestions(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=3)
    source: Literal["model", "fake"]

    @field_validator("questions")
    @classmethod
    def short_unique_questions(cls, values: list[str]) -> list[str]:
        values = [value.strip() for value in values]
        if len(set(values)) != len(values) or any(
            not 6 <= len(value) <= 120 or "\n" in value or not value.endswith(("?", "？")) for value in values
        ):
            raise ValueError("建议应为不重复的简短问题")
        return values


def project_context(engine: Engine, project_id: int, scheme_id: int | None) -> dict[str, Any]:
    with Session(engine) as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(404, "项目不存在")
        schemes = session.exec(select(Scheme).where(
            Scheme.project_id == project_id, Scheme.is_whatif == False  # noqa: E712
        ).order_by(Scheme.id)).all()
        selected = next((row for row in schemes if row.id == scheme_id), None)
        if scheme_id is not None and selected is None:
            raise HTTPException(404, "方案不属于当前项目的常规候选")
        selected = selected or next(iter(schemes), None)
        context: dict[str, Any] = {
            "project": {"name": project.name, "params": {key: project.params.get(key) for key in (
                "site_area", "far_max", "density_max", "height_max", "climate_zone", "province", "seismic_intensity"
            )}},
            "standard_packs": [pack_label(code) for code in project.params.get("standard_packs") or ["GB"]],
            "schemes": [{"id": row.id, "name": row.name, "structure_type": row.params.get("structure_type")}
                        for row in schemes[:30]],
            "selected_scheme": {"id": selected.id, "name": selected.name, "params": {key: selected.params.get(key) for key in (
                "structure_type", "mic_system", "gfa", "floors", "building_count", "prefab_ratio_est", "std_floor_repeat", "risk_features"
            )}} if selected else None,
        }
    try:
        evidence = AgentTools(engine, project_id).get_result(project_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        context["evaluation_status"] = "stale"
        return context
    results = evidence.get("evaluation", {}).get("results", [])
    context["evaluation_status"] = "current" if results else "not_evaluated"
    context["ranking"] = [{key: row[key] for key in ("scheme_id", "scheme_name", "rank")}
                          for row in evidence.get("ranking", {}).get("ranking", [])[:3]]
    weights = evidence.get("ranking", {}).get("weights_used", {})
    context["ranking_signature"] = digest(evidence.get("ranking", {}))
    context["weights_used"] = {key: weights[key] for key in ("source", "role", "role_name") if key in weights}
    relevant = {item["scheme_id"] for item in context["ranking"][:2]}
    if selected:
        relevant.add(str(selected.id))
        context["tradeoffs"] = reader_evidence(evidence, selected.id, "", builtin_labels()).get("主要取舍", [])
    context["evaluations"] = [{
        "scheme_id": row["scheme_id"], "scheme_name": row["scheme_name"],
        "dimension_scores": row["dimension_scores"], "dimension_coverage": row["dimension_coverage"],
        # 建议问题只需知道哪项失败/缺资料，不重复长篇规范原文与数值阈值。
        "issues": [{key: item[key] for key in ("rule_id", "name", "status", "severity", "missing_fields") if key in item}
                   for item in row["compliance"] if item["status"] in ("failed", "insufficient_data")][:4]
                  if selected and row["scheme_id"] == str(selected.id) else [],
    } for row in results if row["scheme_id"] in relevant][:3]
    return context


def local_questions(context: dict[str, Any]) -> list[str]:
    """FakeLLM 的确定性演示也随项目与选中方案变化。"""
    if "项目" in context:
        name = context.get("当前方案", context["项目"])[:35]
        issues = context.get("待核实的检查", []) or context.get("未通过的事项", [])
        first = f"「{name}」还需补充哪些资料？" if issues else f"「{name}」应先核对哪些条件？"
        others = context.get("方案取舍", [])
        second = f"「{name}」与「{others[0]['相比方案'][:35]}」主要差在哪？" if others else f"「{name}」的判断还需核实哪些依据？"
        return [first, second]
    selected = context.get("selected_scheme")
    if not selected:
        return [f"「{context['project']['name'][:35]}」应先补充哪些地块信息？", "开始方案比选前，需要准备哪些候选方案资料？"]
    name = selected["name"][:45]
    if context.get("evaluation_status") != "current":
        return [f"「{name}」评估前应先核对哪些输入？", f"「{name}」适用哪些已选择的地区标准？"]
    current = next((row for row in context["evaluations"] if row["scheme_id"] == str(selected["id"])), {})
    questions = []
    if current.get("issues"):
        questions.append(f"「{name}」的{current['issues'][0]['rule_id']}有哪些待核实问题？")
    others = [row for row in context["ranking"] if row["scheme_id"] != str(selected["id"])]
    if others:
        questions.append(f"「{name}」与「{others[0]['scheme_name'][:35]}」的主要取舍是什么？")
    incomplete = any(value < 1 for value in current.get("dimension_coverage", {}).values())
    questions.append(f"「{name}」哪些维度的数据覆盖还不足？" if incomplete else f"「{name}」哪些评分依据最值得核实？")
    return questions[:3]


def question_view(context: dict[str, Any], labels: dict[str, str] | None = None) -> dict[str, Any]:
    return reader_questions(context, labels or builtin_labels())


def parse_questions(content: str, context: dict[str, Any], source: Literal["model", "fake"], labels: dict[str, str] | None = None) -> QuestionSuggestions:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", content, re.DOTALL)
    raw = json.loads(fenced[1] if fenced else content)
    names = {item["rule_id"]: item["name"] for row in context.get("evaluations", []) for item in row.get("issues", [])}
    protected_names = tuple(row["name"] for row in context.get("schemes", [])) + (context.get("project", {}).get("name", ""),)
    # 模型偶尔多写几个问题；保留合同允许的前三个，不为数量问题再请求模型。
    questions = [humanize(re.sub(r"\b(?:[A-Z]+-)+\d{2}\b", lambda match: names.get(match[0], match[0]), question), labels, protected_names)
                 if isinstance(question, str) else question for question in raw["questions"][:3]]
    response = QuestionSuggestions(questions=questions, source=source)
    if any(re.search(r"\b(?:[A-Z]+-)+\d{2}\b", question) for question in response.questions):
        raise ValueError("建议问题含有未提供的检查编号")
    citation_context = {key: value for key, value in context.items() if key != "ranking_signature"}
    if check_citations("\n".join(response.questions), citation_context, [], len(context["schemes"])):
        raise ValueError("建议问题含有未提供的数值")
    return response
