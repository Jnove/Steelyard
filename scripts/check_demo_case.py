"""检查一个演示案例目录：参数校验 + 硬约束 + 四维得分 + 帕累托 + 角色排名。

用途：在把 ``data/schemes/<case>/`` 的虚构案例拿去录视频或写说明文档之前，
先把「这套数据在规则引擎里到底会得到什么结论」跑出来，避免录到一半才发现
某个方案越线、某个维度是 0 分、或者两个方案互相支配。

它是**只读**的：不写数据库、不调大模型、不改规则。要真正把案例导入 Demo 库，
用 ``scripts/seed_mock.py --mock-dir data/schemes/<case>``。

用法：

    uv run --project backend python scripts/check_demo_case.py
    uv run --project backend python scripts/check_demo_case.py --case data/schemes/demo
    uv run --project backend python scripts/check_demo_case.py --case data/schemes/demo --packs GB
    uv run --project backend python scripts/check_demo_case.py --case data/schemes/demo --json out.json

``--packs`` 用来对比「同一套方案，只按国标判 vs 加上地方册判」的结论差异；
不传时用项目 JSON 里的 ``standard_packs``。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402
from app.engine.mcdm import (  # noqa: E402
    CRITERION_ORDER,
    pareto_front,
    topsis,
)
from app.engine.rules import SchemeInput, evaluate, get_ruleset  # noqa: E402
from app.engine.weights import load_role_templates  # noqa: E402
from app.models.params import ProjectParams, SchemeParams  # noqa: E402

DEFAULT_CASE = ROOT / "data" / "schemes" / "qiantang-real"
PROJECT_FILE = "project.json"
WHATIF_FILE = "whatif.json"
REQUIRED_TOP_KEYS = ("_note", "name", "params")
#: 顶层 ``_note`` 必须命中其中一种：虚构案例声明，或「方案数值为演示自拟」声明。
#: 真实地块案例的项目层来自公开文件，不能强求它自称虚构；但方案层仍须声明是演示数据。
NOTE_MARKERS = ("虚构数据", "演示自拟")


class CaseError(SystemExit):
    """案例目录本身有问题（缺文件、JSON 坏、字段不合法）。"""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CaseError(f"ERROR · 找不到文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CaseError(f"ERROR · {path.name} 不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise CaseError(f"ERROR · {path.name} 顶层必须是对象")
    for key in REQUIRED_TOP_KEYS:
        if key not in payload:
            raise CaseError(f"ERROR · {path.name} 缺少顶层字段 {key!r}")
    note = str(payload.get("_note", ""))
    if not any(marker in note for marker in NOTE_MARKERS):
        raise CaseError(
            f"ERROR · {path.name} 的 _note 既没有「虚构数据」也没有「演示自拟」声明；"
            "案例数据必须显式标注来源性质，防止被当成工程结论"
        )
    return payload


def load_case(case_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """读案例目录：项目 JSON + 全部方案 JSON（``whatif.json`` 排最后）。"""
    if not case_dir.is_dir():
        raise CaseError(f"ERROR · 案例目录不存在：{case_dir}")

    project = _load_json(case_dir / PROJECT_FILE)

    rest = sorted(
        p
        for p in case_dir.glob("*.json")
        if p.name not in {PROJECT_FILE, WHATIF_FILE} and not p.name.startswith("_")
    )
    if not rest:
        raise CaseError(f"ERROR · {case_dir} 下没有方案 JSON")

    schemes = [_load_json(p) for p in rest]
    whatif_path = case_dir / WHATIF_FILE
    if whatif_path.is_file():
        whatif = _load_json(whatif_path)
        whatif["_whatif"] = True
        schemes.append(whatif)
    return project, schemes


def _failed(compliance: list[Any], severity: str = "error") -> list[Any]:
    return [c for c in compliance if c.status == "failed" and c.severity == severity]


def _insufficient(compliance: list[Any]) -> list[Any]:
    return [c for c in compliance if c.status == "insufficient_data"]


def _fmt_scores(scores: Any) -> str:
    return "  ".join(f"{name}={getattr(scores, name):6.2f}" for name in CRITERION_ORDER)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查一个演示案例在规则引擎里的结论")
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE, help="案例目录")
    parser.add_argument(
        "--packs",
        nargs="+",
        default=None,
        help='覆盖项目的 standard_packs，例如 --packs GB（只按国标判）',
    )
    parser.add_argument("--json", type=Path, default=None, help="把完整结果另存为 JSON")
    args = parser.parse_args(argv)

    project_payload, scheme_payloads = load_case(args.case)

    # —— 参数校验 —— #
    params_raw = dict(project_payload["params"])
    if args.packs is not None:
        params_raw["standard_packs"] = list(args.packs)
    try:
        project = ProjectParams.model_validate(params_raw)
    except Exception as exc:  # noqa: BLE001
        raise CaseError(f"ERROR · 项目参数未通过 ProjectParams 校验：\n{exc}") from exc

    schemes: list[SchemeInput] = []
    for payload in scheme_payloads:
        try:
            validated = SchemeParams.model_validate(payload["params"])
        except Exception as exc:  # noqa: BLE001
            raise CaseError(
                f"ERROR · {payload['name']} 未通过 SchemeParams 校验：\n{exc}"
            ) from exc
        schemes.append(
            SchemeInput(scheme_id=payload["name"], name=payload["name"], params=validated)
        )

    # —— 规则集 —— #
    base = get_ruleset()
    packs = tuple(project.standard_packs or ("GB",))
    rules = base.select_packs(packs)

    print(f"案例目录：{args.case}")
    print(f"项目：{project_payload['name']}")
    print(f"适用标准册：{'、'.join(packs)}（可用规则 {len(rules.rules)} 条）")
    print(f"方案数：{len(schemes)}（含 What-if 副本 {sum(1 for p in scheme_payloads if p.get('_whatif'))}）")
    print()

    results = evaluate(project, schemes, rules)

    # —— 逐方案：硬约束 —— #
    print("=" * 78)
    print("一、硬约束逐条结论")
    print("=" * 78)
    for result in results:
        errors = _failed(result.compliance, "error")
        warnings = _failed(result.compliance, "warning")
        insufficient = _insufficient(result.compliance)
        verdict = "✗ 被剔除排名" if errors else "✓ 通过"
        print(f"\n【{result.scheme_name}】{verdict}")
        print(
            f"  error 未通过 {len(errors)} 条、warning 未通过 {len(warnings)} 条、"
            f"数据不足 {len(insufficient)} 条"
        )
        for item in errors:
            print(f"    ✗ [{item.rule_id}] {item.message}")
        for item in warnings:
            print(f"    ! [{item.rule_id}] {item.message}")
        for item in insufficient:
            missing = "、".join(item.missing_fields) or "?"
            print(f"    ? [{item.rule_id}] 缺字段：{missing}")

    # —— 逐方案：四维得分 —— #
    print()
    print("=" * 78)
    print("二、四维得分与指标明细")
    print("=" * 78)
    for result in results:
        print(f"\n【{result.scheme_name}】")
        print(f"  {_fmt_scores(result.dimension_scores)}")
        cov = result.dimension_coverage
        weak = [n for n in CRITERION_ORDER if getattr(cov, n) < 1.0]
        if weak:
            print(
                "  数据覆盖率不足："
                + "、".join(f"{n}={getattr(cov, n):.2f}" for n in weak)
            )
        for rule_id, metric in sorted(result.metrics.items()):
            if metric.status != "scored":
                missing = "、".join(metric.missing_fields) or "?"
                print(f"    · [{rule_id}] {metric.name}：{metric.status}（缺 {missing}）")
            else:
                print(
                    f"    · [{rule_id}] {metric.name}：值 {metric.value} → {metric.score:.1f} 分"
                    f"（{metric.dimension}，权重 {metric.weight_in_dimension:g}）"
                )

    # —— 帕累托 —— #
    participants = [r for r in results if not _failed(r.compliance, "error")]
    excluded = [r for r in results if _failed(r.compliance, "error")]

    print()
    print("=" * 78)
    print("三、帕累托筛选（只比较通过硬约束的方案）")
    print("=" * 78)
    if excluded:
        print("已剔除：" + "、".join(r.scheme_name for r in excluded))
    if len(participants) < 2:
        print("可比较方案不足 2 个，跳过帕累托与排名。")
    else:
        rows = np.asarray(
            [
                [getattr(r.dimension_scores, k) for k in CRITERION_ORDER]
                for r in participants
            ],
            dtype=float,
        )
        pareto = pareto_front(rows)
        for idx, result in enumerate(participants):
            if idx in pareto.non_dominated:
                print(f"  · {result.scheme_name}：非劣方案")
            else:
                dominators = "、".join(
                    participants[d].scheme_name for d in pareto.dominated_by[idx]
                )
                print(f"  · {result.scheme_name}：被支配（{dominators}）")

        # —— 角色排名 —— #
        print()
        print("=" * 78)
        print("四、五个角色视角下的 TOPSIS 排名")
        print("=" * 78)
        templates = load_role_templates()
        for template in templates.values():
            ranking = topsis(rows, list(template.weights))
            order = sorted(range(len(participants)), key=lambda i: -ranking.closeness[i])
            cells = " > ".join(
                f"{participants[i].scheme_name.split(' ')[0]}"
                f"({ranking.closeness[i]:.3f})"
                for i in order
            )
            print(f"  {template.name:<8}{cells}")

    # —— 机读输出 —— #
    if args.json is not None:
        payload = {
            "case_dir": str(args.case),
            "project": project_payload["name"],
            "packs": list(packs),
            "schemes": [
                {
                    "name": r.scheme_name,
                    "dimension_scores": r.dimension_scores.model_dump(),
                    "blocking_rules": [c.rule_id for c in _failed(r.compliance, "error")],
                    "warning_rules": [c.rule_id for c in _failed(r.compliance, "warning")],
                    "insufficient_rules": [c.rule_id for c in _insufficient(r.compliance)],
                    "metrics": {
                        rid: {"value": m.value, "score": m.score, "status": m.status}
                        for rid, m in r.metrics.items()
                    },
                }
                for r in results
            ],
        }
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n完整结果已写入 {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
