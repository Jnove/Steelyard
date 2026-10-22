"""模型只读取报告摘要；原始计算证据仍完整用于溯源和返回。"""
from __future__ import annotations

from typing import Any


def compact_evidence(evidence: Any, rule_id: str | None = None) -> Any:
    # search_clause 的结果是列表（当前检索桩返回 []），不是评估/排名字典。
    # 非报告结构原样保留，避免工具成功后在整理模型上下文时崩溃。
    if not isinstance(evidence, dict):
        return evidence
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
                "insufficient_compliance_count": sum(item["status"] == "insufficient_data" for item in result.get("compliance", [])),
                "unscored_metrics": [key for key, item in metrics.items() if item.get("status") != "scored"],
                "compliance": issues[:3], "metrics": {key: metrics[key] for key in selected},
            })
        summary["evaluation"] = {"results": rows, "detail_note": "仅关键问题与指标摘要，未列出的条目不代表通过；存在数据不足时，排名仅是已知条件下的评分与取舍，不能宣称全部合规或确定最优；不适用指标不构成性能优势。完整证据保留在工具结果中"}
    if "ranking" in evidence:
        ranking = evidence["ranking"]
        summary["ranking"] = {key: ranking[key] for key in ("criteria", "weights_used", "ranking", "excluded") if key in ranking}
    return summary
