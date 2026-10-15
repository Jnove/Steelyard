from __future__ import annotations

import json

import pytest
from app.agents.graph import AgentGraph
from app.agents.llm import FakeLLM, LLMResponse
from app.agents.readable import builtin_labels, humanize, reader_evidence, reader_questions
from app.agents.state import AgentRequest, GraphState
from app.agents.tools import AgentTools


def test_identifier_translation_keeps_names_numbers_and_boundaries():
    text = humanize("缺 excavation_depth、local_probe，insufficient_data；GB 55003—2021，0.82；excavation_depth_extra",
                    {"local_probe": "现场勘测资料"})
    assert "基坑开挖深度" in text and "现场勘测资料" in text and "资料不足" in text
    assert "GB 55003—2021，0.82" in text and "excavation_depth_extra" in text
    assert humanize("https://source.test/quality 和 green", protected_names=("green",)) == "https://source.test/quality 和 green"


def test_missing_data_stays_attached_to_its_own_check():
    view = reader_questions({"project": {"name": "虚构示例"}, "standard_packs": ["国家标准"], "evaluation_status": "current",
        "selected_scheme": {"id": 1, "name": "B 模块化候选", "params": {"structure_type": "MiC"}}, "evaluations": [
        {"scheme_id": "1", "scheme_name": "B 模块化候选", "dimension_scores": {}, "dimension_coverage": {}, "issues": [
            {"rule_id": "K-03", "name": "深基坑属超过一定规模的危大工程（须专家论证）", "status": "insufficient_data", "missing_fields": ["excavation_depth"]}]}]}, builtin_labels())
    assert view["待核实的检查"] == [{"核实事项": "深基坑", "待补资料": ["基坑开挖深度"], "目前结论": "资料不足"}]


def test_reader_summary_preserves_risk_and_comparisons_without_dumping_numbers():
    def row(identifier, name, quality, construction):
        return {"scheme_id": identifier, "scheme_name": name, "dimension_scores": {"quality": quality, "construction": construction},
                "dimension_coverage": {"quality": 1, "construction": 1}, "compliance": []}
    current = row("1", "B 工业化", 60, 90)
    current["metrics"] = {"Q-01": {"rule_id": "Q-01", "name": "得房率", "value": 0.76, "score": 60, "status": "scored", "dimension": "quality", "source": "测试依据"}}
    current["compliance"] = [
        {"rule_id": "K-06", "name": "支护类型", "status": "insufficient_data", "missing_fields": ["retaining_type"]},
        {"rule_id": "K-03", "name": "深基坑危大工程", "status": "insufficient_data", "missing_fields": ["excavation_depth"]},
    ]
    other = row("2", "D 常规", 80, 70)
    blocked = row("3", "E 超限", 50, 60)
    blocked["compliance"] = [{"rule_id": "C-01", "name": "建筑高度超限", "status": "failed"}]
    evidence = {"evaluation": {"results": [current, other, blocked]}, "ranking": {"ranking": [
        {"scheme_id": "1", "scheme_name": "B 工业化"}, {"scheme_id": "2", "scheme_name": "D 常规"}],
        "excluded": [{"scheme_id": "3", "scheme_name": "E 超限"}]}}
    view = reader_evidence(evidence, 1, "基坑开挖深度还缺什么？", builtin_labels())
    raw = json.dumps(view, ensure_ascii=False)
    assert all(term not in raw for term in ("scheme_id", "excavation_depth", "K-03", "60", "90"))
    assert view["当前最相关的待核实事项"][0]["需要补充"] == ["基坑开挖深度"]
    assert view["主要取舍"][0]["当前方案较高的方面"] == ["施工友好"]
    assert view["主要取舍"][0]["当前方案较低的方面"] == ["居住品质"]
    assert view["未参与当前排序的方案"] == ["E 超限"] and view["需先处理的问题"]
    details = reader_evidence(evidence, 1, "具体分数是多少？", builtin_labels(), details=True)
    assert details["按需查看的评分"][0]["维度得分"]["居住品质"] == 60
    assert details["当前方案的相关指标详情"][0]["当前值"] == 0.76


@pytest.mark.asyncio
async def test_final_field_translation_precedes_citation_offsets(engine, mock_project):
    project, _ = mock_project
    tools = AgentTools(engine, project)
    tools.evaluate(project)
    llm = FakeLLM({"reporter": [LLMResponse(content="😀 excavation_depth 的得分为 998.23")]*3})
    async def emit(name, data):
        pass
    output = await AgentGraph(tools, llm, emit).run(GraphState(project_id=project, request=AgentRequest(intent="explain", message="还缺什么资料？")))
    assert "excavation_depth" not in output.report and "基坑开挖深度" in output.report
    assert output.unverified_numbers
    issue = output.unverified_numbers[0]
    assert output.report[issue.start:issue.end] == "998.23"
