"""从现有字段元信息和引擎证据生成面向读者的摘要，不改计算结果。"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from app.engine.metrics import DERIVED_QUANTITIES
from app.models import ProjectParams, SchemeParams
from app.models.eval import DimensionScores

DIMENSIONS = {key: field.description or key for key, field in DimensionScores.model_fields.items()}
STATUS_LABELS = {"insufficient_data": "资料不足", "not_applicable": "不适用", "passed": "通过",
                 "failed": "未通过", "scored": "已评分", "source": "依据", "scheme_id": "方案", "TODO": "需专业组核实"}
DETAIL_REQUEST = re.compile(r"详细|逐条|完整清单|多少|几分|分值|数值|阈值|限值|公式|规则编号|字段名|来源原文|具体[的]*(?:得分|分数|数据)")
TOPICS = {"quality": ("居住", "品质", "体验", "得房", "采光", "舒适"),
          "structure": ("结构", "安全", "抗震"), "construction": ("施工", "建造", "装配", "标准层"),
          "green": ("绿色", "低碳", "节能", "环保")}


@lru_cache(maxsize=1)
def builtin_labels() -> dict[str, str]:
    labels = {key: (field.json_schema_extra or {}).get("label", key)
              for model in (ProjectParams, SchemeParams) for key, field in model.model_fields.items()}
    return {**labels, **{item.name: item.label for item in DERIVED_QUANTITIES}, **DIMENSIONS, **STATUS_LABELS}


def humanize(text: str, labels: dict[str, str] | None = None, protected_names: tuple[str, ...] = ()) -> str:
    """只替换已登记的完整标识符，保留用户名称、数值及证据含义。"""
    names = {**builtin_labels(), **(labels or {})}
    protected = set(filter(None, protected_names))
    pattern = r"https?://[^\s<>）)]+|" + ("|".join(re.escape(name) for name in sorted(protected, key=len, reverse=True)) + "|" if protected else "") + r"[A-Za-z][A-Za-z0-9_]*"
    return re.sub(pattern, lambda match: match[0] if match[0] in protected or match[0].startswith(("http://", "https://")) else names.get(match[0], match[0]), text)


def detailed_request(message: str) -> bool:
    return bool(DETAIL_REQUEST.search(message))


def issue_view(item: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    missing = [labels.get(key, "待补充的设计参数") for key in item.get("missing_fields", [])]
    name = item.get("name", "相关检查")
    if item.get("status") == "insufficient_data":
        name = re.split(r"[（(]|属", name, maxsplit=1)[0]
    return {"检查事项": humanize(name, labels),
            "判断": "触发提示" if item.get("status") == "failed" and item.get("severity") == "warning"
                    else STATUS_LABELS.get(item.get("status", ""), "待核实"),
            **({"需要补充": missing} if missing else {})}


def issue_relevance(item: dict[str, Any], question: str, labels: dict[str, str]) -> int:
    text = item.get("name", "") + "".join(labels.get(key, key) for key in item.get("missing_fields", []))
    words = {question[index:index+2] for index in range(len(question)-1)
             if re.fullmatch(r"[\u4e00-\u9fff]{2}", question[index:index+2])}
    return (100 if item.get("rule_id") and item["rule_id"] in question else 0) + sum(word in text for word in words)


def reader_evidence(evidence: dict[str, Any], scheme_id: int | None, question: str,
                    labels: dict[str, str], *, details: bool = False) -> dict[str, Any]:
    rows = evidence.get("evaluation", {}).get("results", [])
    ranking = evidence.get("ranking", {}).get("ranking", [])
    selected = next((row for row in rows if row["scheme_id"] == str(scheme_id)), None)
    selected = selected or next((row for row in rows if ranking and row["scheme_id"] == ranking[0]["scheme_id"]), None)
    selected = selected or next(iter(rows), None)
    view: dict[str, Any] = {
        "说明": "按当前录入参数、规则和决策视角，解释已有评分与方案差异。评分表达规则下的相对评价。",
        "回答重点": "先回答用户本次问题，解释有证据的优势、代价与可比较的结果。下列案例边界保留供判断，普通短答只说明影响本问的限制，不逐项复述；已有比较不因无关检查待补资料而失效。",
    }
    notes = evidence.get("data_notes", {})
    if notes.get("project_notes"):
        view["案例来源与边界"] = notes["project_notes"]
    if notes.get("scoring_exclusions"):
        view["暂不计分指标"] = notes["scoring_exclusions"]
    if selected:
        scheme_note = next((row.get("scheme_notes") for row in notes.get("schemes", [])
                            if row["scheme_id"] == selected["scheme_id"]), None)
        if scheme_note:
            view["方案数据说明"] = scheme_note
        view["暂不计分事项"] = [item["name"] for item in selected.get("metrics", {}).values()
                             if item.get("status") == "not_applicable"]
    if any(item["status"] == "insufficient_data" for row in rows for item in row.get("compliance", [])):
        view["资料提醒"] = "仍有检查数据不足；排名仅展示已知条件下的评分与取舍，不能认定全部合规或确定最优方案。"
    if ranking:
        view["当前排序"] = [row["scheme_name"] for row in ranking[:5]]
        weights = evidence.get("ranking", {}).get("weights_used", {})
        view["决策视角"] = weights.get("role_name") or "当前权重"
        if details and weights.get("weights"):
            view["具体权重"] = {DIMENSIONS.get(key, key): value for key, value in zip(weights.get("criteria", []), weights["weights"], strict=False)}
    failed = [{"方案": row["scheme_name"], "未通过事项": [issue_view(item, labels) for item in row.get("compliance", [])
               if item["status"] == "failed" and item.get("severity", "error") == "error"][:2]}
              for row in rows if any(item["status"] == "failed" and item.get("severity", "error") == "error"
                                     for item in row.get("compliance", []))]
    if failed:
        view["需先处理的问题"] = failed
    warnings = [{"方案": row["scheme_name"], "提示事项": [issue_view(item, labels) for item in row.get("compliance", [])
                 if item["status"] == "failed" and item.get("severity") == "warning"][:2]}
                for row in rows if any(item["status"] == "failed" and item.get("severity") == "warning"
                                       for item in row.get("compliance", []))]
    if warnings:
        view["专项与施工提示"] = warnings
    excluded = evidence.get("ranking", {}).get("excluded", [])
    if excluded:
        view["未参与当前排序的方案"] = [item.get("scheme_name", "未命名方案") for item in excluded]
    if selected:
        view["当前方案"] = selected["scheme_name"]
        issues = [item for item in selected.get("compliance", []) if item["status"] in ("failed", "insufficient_data")]
        focus = {key for key, words in TOPICS.items() if any(word in question for word in words)}
        if not details and not re.search(r"缺|补充|资料|核实|风险|安全|超限|合规|可靠|真实|教学|假设|边界|论证|报告", question):
            issues = [item for item in issues if item["status"] == "failed" and item.get("severity", "error") == "error"
                      or issue_relevance(item, question, labels) > 0]
        issues.sort(key=lambda item: (-issue_relevance(item, question, labels), item["status"] != "failed"))
        view["当前最相关的待核实事项"] = [issue_view(item, labels) for item in issues[:3]]
        view["评分资料不足的方面"] = [DIMENSIONS[key] for key, coverage in selected.get("dimension_coverage", {}).items() if coverage < 1]
        others = [row for row in rows if row is not selected]
        # 先比较问题点名的方案，其次采用当前排序中的相邻候选。
        def priority(row: dict[str, Any]) -> tuple[bool, int]:
            name = row["scheme_name"]
            letter = re.match(r"[A-Z](?![A-Za-z])", name)
            mentioned = name in question or bool(letter and re.search(r"(?<![A-Za-z])" + letter[0] + r"(?![A-Za-z])", question))
            rank = next((index for index, item in enumerate(ranking) if item["scheme_id"] == row["scheme_id"]), 1000)
            return not mentioned, rank
        others.sort(key=priority)
        view["主要取舍"] = []
        for other in others[:2]:
            available = [key for key in DIMENSIONS if selected.get("dimension_coverage", {}).get(key, 0) > 0
                         and other.get("dimension_coverage", {}).get(key, 0) > 0 and (not focus or key in focus)]
            clues = []
            for dimension in DIMENSIONS:
                if focus and dimension not in focus:
                    continue
                for key, metric in selected.get("metrics", {}).items():
                    peer = other.get("metrics", {}).get(key, {})
                    if (metric.get("dimension") == dimension and metric.get("status") == peer.get("status") == "scored"
                        and metric.get("score") is not None and peer.get("score") is not None and metric["score"] != peer["score"]):
                        clues.append({"指标": metric["name"], "当前规则评价": "较高" if metric["score"] > peer["score"] else "较低",
                                      **({"依据状态": "需专业组核实"} if "TODO" in metric.get("source", "") else {})})
                        break
            view["主要取舍"].append({"相比方案": other["scheme_name"],
                "当前方案较高的方面": [DIMENSIONS[key] for key in available if selected["dimension_scores"][key] > other["dimension_scores"][key]],
                "当前方案较低的方面": [DIMENSIONS[key] for key in available if selected["dimension_scores"][key] < other["dimension_scores"][key]],
                "已有的具体指标线索": clues})
    if details:
        view["按需查看的评分"] = [{"方案": row["scheme_name"], "维度得分": {DIMENSIONS[key]: value for key, value in row.get("dimension_scores", {}).items()}} for row in rows[:5]]
        if selected:
            metrics = list(selected.get("metrics", {}).values())
            metrics.sort(key=lambda item: -issue_relevance(item, question, labels))
            view["当前方案的相关指标详情"] = [{"指标": item["name"], "当前值": item.get("value"), "当前得分": item.get("score"),
                "依据": item.get("source"), "判断": STATUS_LABELS.get(item.get("status", ""), "待核实")}
                for item in metrics[:4]]
    if "clauses" in evidence:
        view["条文依据"] = evidence["clauses"] or "未取得检索原文；现有规则与计算依据仍可用于解释评分，正式条文结论需对应原文。"
    if evidence.get("explanation"):
        item = evidence["explanation"]
        view["指定检查"] = {"事项": item.get("name"), "依据": item.get("source"),
                          **({"规则编号": item.get("id"), "公式": humanize(str(item.get("formula", "")), labels)} if details else {})}
    # 先呈现本问的计算结论，资料来源和边界仍完整保留在后面供核对。
    primary = ("当前方案", "决策视角", "当前排序", "主要取舍", "需先处理的问题", "未参与当前排序的方案")
    return {**{key: view[key] for key in primary if key in view},
            **{key: value for key, value in view.items() if key not in primary}}


def reader_questions(context: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    selected = context.get("selected_scheme")
    view: dict[str, Any] = {"本轮任务": "为下面的项目和所选方案生成三个建议追问；已有评估时优先围绕方案优势与取舍。",
                           "输出要求": '只输出 JSON 对象，格式为 {"questions":["问题一？","问题二？","问题三？"]}；每项只有一个十八至二十八字的简短问句。前两问解释已有指标对应的优势或代价，最多一问核实资料。只问已有线索，不扩展空间构造、审批便利或未提供的因果。不总结资料、不回答、不输出其他文字。',
                           "项目": context["project"]["name"], "适用地区标准": context["standard_packs"],
                           "资料状态": {"current": "已有评估", "stale": "评估已过期", "not_evaluated": "尚未评估"}[context["evaluation_status"]]}
    if not selected:
        return view
    view["当前方案"] = selected["name"]
    view["建造方式"] = selected["params"].get("mic_system") or selected["params"].get("structure_type")
    current = next((row for row in context.get("evaluations", []) if row["scheme_id"] == str(selected["id"])), {})
    issues = current.get("issues", [])[:3]
    view["待核实的检查"] = [{"核实事项": re.split(r"[（(]|属", item.get("name", "相关检查"), maxsplit=1)[0],
                             "待补资料": [labels.get(key, "待补充的设计参数") for key in item.get("missing_fields", [])],
                             "目前结论": "触发提示" if item.get("status") == "failed" and item.get("severity") == "warning"
                                         else STATUS_LABELS.get(item.get("status", ""), "待核实")}
                            for item in issues]
    if any(item["status"] == "failed" and item.get("severity", "error") == "error" for item in issues):
        view["未通过的事项"] = [item["name"] for item in issues if item["status"] == "failed" and item.get("severity", "error") == "error"]
    # 复用同一套基于已计算维度分数的比较，只向建议模型传入定性关系。
    evidence = {"evaluation": {"results": context.get("evaluations", [])}, "ranking": {"ranking": context.get("ranking", [])}}
    tradeoffs = context.get("tradeoffs") or reader_evidence(evidence, selected["id"], "", labels).get("主要取舍", [])
    # 建议只围绕具体指标提问，避免将维度评分高低解读成实际安全/体验结论。
    view["方案取舍"] = [{"相比方案": item["相比方案"], "已有的具体指标线索": item.get("已有的具体指标线索", [])}
                       for item in tradeoffs[:1]]
    view["判断边界"] = "当前方案只是正在查看的候选，尚未确定采用。缺项资料只用于对应检查，不能归因到其他指标。规则评价差异不代表实际抗震风险、工期变化或居住损害；资料不足不能认定已触发专项要求。标为触发提示的事项则已知需履行相应程序，不是缺资料、未闭合或论证未通过。"
    return view


def render_reader_demo(context: dict[str, Any]) -> str:
    """离线桩也用自然中文，明确标出演示性质。"""
    view = context["reader_view"]
    name = view.get("当前方案", "当前方案")
    lines = ["FakeLLM 演示；以下仅摘录当前工具结果。", f"{name}可先结合现有排序比较取舍。"]
    if view.get("资料提醒"):
        lines.append(view["资料提醒"])
    if view.get("案例来源与边界") or view.get("方案数据说明"):
        lines.append("方案的资料版本与教学假设见案例说明，不能作为真实工程成效。")
    if view.get("暂不计分事项"):
        lines.append("、".join(view["暂不计分事项"]) + "暂不计分，不能作为性能优势。")
    if view.get("未参与当前排序的方案"):
        lines.append("、".join(view["未参与当前排序的方案"]) + "未参与当前排序，需先核实排除原因。")
    for problem in view.get("需先处理的问题", [])[:2]:
        lines.append(problem["方案"] + "有未通过的检查：" + "、".join(item["检查事项"] for item in problem["未通过事项"]) + "。")
    for warning in view.get("专项与施工提示", [])[:1]:
        lines.append(warning["方案"] + "触发施工提示：" + "、".join(item["检查事项"] for item in warning["提示事项"]) + "。")
    for issue in view.get("当前最相关的待核实事项", [])[:2]:
        fields = "、".join(issue.get("需要补充", []))
        lines.append(f"{issue['检查事项']}：{('还需补充' + fields) if fields else issue['判断']}。")
    if context.get("comparison_view"):
        lines.append("原方案与副本对比：" + context["comparison_view"])
    if view.get("指定检查"):
        lines.append(f"{view['指定检查']['事项']}：需结合该项计算与依据核实。")
    lines.append("先补齐相关资料，再确认判断；完整依据可在规则详情中查看。")
    if context.get("response_mode") == "brief_report":
        return "## 结论\n\n" + "\n\n".join(lines[:2]) + "\n\n## 关键问题\n\n" + "\n\n".join(lines[2:-1]) + "\n\n## 下一步\n\n" + lines[-1]
    return "\n\n".join(lines)
