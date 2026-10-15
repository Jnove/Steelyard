"""模型只读取报告摘要；原始计算证据仍完整用于溯源和返回。"""
from __future__ import annotations

from typing import Any


def compact_evidence(evidence: dict[str, Any], rule_id: str | None = None) -> dict[str, Any]:
    summary = {key: value for key, value in evidence.items() if key not in ("evaluation", "ranking", "tool_queries")}
    if "evaluation" in evidence:
        evaluation = evidence["evaluation"]
        rows = []
        for result in evaluation.get("results", [])[:8]:
            metrics = result.get("metrics", {})
            selected = ([rule_id] if rule_id in metrics else []) + [key for key in metrics if key != rule_id][:3]
            issues = [item for item in result.get("compliance", []) if item["status"] in ("failed", "insufficient_data")]
            issues.sort(key=lambda item: (item["status"] != "failed", item.get("severity") != "error"))
            rows.append({
                **{key: result[key] for key in ("scheme_id", "scheme_name", "dimension_scores", "dimension_coverage") if key in result},
                "compliance": issues[:3], "metrics": {key: metrics[key] for key in selected},
            })
        summary["evaluation"] = {"results": rows, "detail_note": "仅关键问题与指标摘要，未列出的条目不代表通过；完整证据保留在工具结果中"}
    if "ranking" in evidence:
        ranking = evidence["ranking"]
        summary["ranking"] = {key: ranking[key] for key in ("criteria", "weights_used", "ranking", "excluded") if key in ranking}
    return summary
