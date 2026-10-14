"""校验并追加演示案例；默认只预览，绝不删除、覆盖已有项目或方案。"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.models import ProjectParams, SchemeParams  # noqa: E402
from seed_mock import discover_layout, resolve_whatif_parent  # noqa: E402

CASES = (
    ("xiasha-real", "下沙公租房一期 · 真实地块参考／教学推演（公开字段版）", True),
    ("linping-donghu-real", "东湖北路公租房 · 真实地块参考／教学推演（公开字段版）", True),
    ("qiantang-real", "前进公租房一期 · 真实地块参考／教学推演（公开字段版）", True),
    ("demo-boundaries-fictional", "虚构边界案例 · 超限排除与调整推演", False),
    ("demo-qiantang-fictional", "虚构钱塘案例 · 品质与工业化取舍", False),
)


def build_plan() -> list[dict[str, Any]]:
    plan = []
    for case_id, name, real in CASES:
        directory = ROOT / "data" / "schemes" / case_id
        project_file = directory / ("project_verified.json" if real else "project.json")
        payload = json.loads(project_file.read_text(encoding="utf-8"))
        notes = [
            "真实地块公开资料作背景，全部候选方案为教学自拟；当前规则下的推演不评价历史建成工程。"
            if real else "地块和方案均为虚构教学数据，仅用于流程与边界演示。",
            "未取得或未核定的规划上限、设防和局部构件条件保持缺失，数据不足不等于合规通过。",
        ]
        if case_id == "qiantang-real":
            notes.append("用地面积引自历史规划许可记录，本次许可页未能复核；批准面积比不能充作规划上限。")
            notes.append("历史来源：https://ghzy.hangzhou.gov.cn/art/2022/7/6/art_1228968732_78156.html（本次未能访问复核）")
        sources = payload.get("_sources", [])
        notes.extend(
            f"公开来源：{source.get('url', '')}（页码 {source.get('page', '见案例说明')}）"
            for source in sources if isinstance(source, dict) and source.get("url")
        )
        params = ProjectParams.model_validate({
            **payload["params"], "project_notes": "\n".join(notes),
        }).model_dump(mode="json")
        filenames, whatif_file = discover_layout(directory)
        schemes = []
        for filename in (*filenames, *((whatif_file,) if whatif_file else ())):
            item = json.loads((directory / filename).read_text(encoding="utf-8"))
            scheme_note = "教学自拟方案，非真实项目的批准或建成方案。" if real else "虚构方案，用于程序流程演示。"
            parent = resolve_whatif_parent(directory, item) if filename == whatif_file else None
            suffix = " · 教学推演" if real else ""
            schemes.append({
                "name": item["name"] + suffix,
                "params": SchemeParams.model_validate({
                    **item["params"], "scheme_notes": scheme_note,
                }).model_dump(mode="json"),
                "parent_name": parent + suffix if parent else None,
            })
        plan.append({"case_id": case_id, "name": name, "params": params, "schemes": schemes})
    return plan


class Api:
    def __init__(self, url: str):
        self.base = url.rstrip("/") + "/api"

    def call(self, path: str, method: str = "GET", body: Any = None) -> Any:
        data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"User-Agent": "Mozilla/5.0 Steelyard case integration", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        return json.loads(content) if content else None


def publish(api: Api, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = api.call("/projects")
    receipt = []
    for case in plan:
        matches = [row for row in existing if row["name"] == case["name"]]
        if len(matches) > 1:
            raise ValueError(f"同名项目不唯一，停止追加：{case['name']}")
        if matches:
            project = matches[0]
            if project["params"] != case["params"]:
                raise ValueError(f"已有项目参数不同，拒绝覆盖：{case['name']}")
        else:
            project = api.call("/projects", "POST", {"name": case["name"], "params": case["params"]})
            existing.append(project)
        project_id = project["id"]
        rows = api.call(f"/projects/{project_id}/schemes?include_whatif=true")
        by_name = {row["name"]: row for row in rows}
        if set(by_name) - {item["name"] for item in case["schemes"]}:
            raise ValueError(f"已有项目存在额外方案，拒绝对其追加或评估：{case['name']}")
        for scheme in case["schemes"]:
            parent = by_name.get(scheme["parent_name"]) if scheme["parent_name"] else None
            if scheme["parent_name"] and not parent:
                raise ValueError(f"What-if 父方案不存在：{scheme['parent_name']}")
            body = {"name": scheme["name"], "params": scheme["params"],
                    "is_whatif": parent is not None, "parent_id": parent["id"] if parent else None}
            if scheme["name"] in by_name:
                row = by_name[scheme["name"]]
                if any(row.get(key) != value for key, value in body.items()):
                    raise ValueError(f"已有方案不同，拒绝覆盖：{scheme['name']}")
            else:
                by_name[scheme["name"]] = api.call(f"/projects/{project_id}/schemes", "POST", body)
        # 副本保存在库中，默认看板只比较正式候选；What-if 由明确请求开启。
        evaluated = api.call(f"/projects/{project_id}/evaluate", "POST", {})
        ranking = api.call(f"/projects/{project_id}/rank", "POST", {"role": "government"})
        receipt.append({"case_id": case["case_id"], "project_id": project_id, "name": case["name"],
                        "schemes": len(by_name), "rule_count": evaluated["rule_count"],
                        "evaluated": len(evaluated["results"]), "ranked": len(ranking["ranking"])})
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://project.jnove.dpdns.org/steelyard")
    parser.add_argument("--apply", action="store_true", help="追加到指定站点；不删除或覆盖")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    plan = build_plan()
    result = publish(Api(args.url), plan) if args.apply else [
        {"case_id": item["case_id"], "name": item["name"], "schemes": len(item["schemes"])} for item in plan
    ]
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
