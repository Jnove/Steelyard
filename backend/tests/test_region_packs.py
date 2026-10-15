"""地区规则册（pack）：注册表、编号、筛选与项目选择。

守住五条：

1. **31 个省级行政区**一个不少、代码唯一，且不含港澳台；
2. **册与编号必须自洽**：地方规则的 ID 形如 ``ZJ-S-01``，``pack`` 必须与之相符，
   册代码必须在注册表里——不一致时报告会把来源归错，所以加载就该失败；
3. **GB 永远生效**：项目可以加地方册，但**不能去掉 GB**；
4. **筛选不动原件**：``select_packs`` 返回新集合，全局缓存的那份永远含全部册
   （否则一个项目开了地方册会顺手影响另一个项目）；
5. **评估只跑选中的册**：默认（只有 GB）时浙江册的规则根本不出现；
   开了 ZJ 才参与——这正是"地方条例灵活选用"的含义。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from app.engine.regions import (
    GB_PACK,
    MAINLAND_PROVINCES,
    PROVINCE_CODES,
    pack_label,
)
from app.engine.rules import (
    RuleLoadError,
    SchemeInput,
    default_rules_dir,
    evaluate,
    load_rules_from_dir,
)
from app.excel import parse_workbook, write_export
from app.models import ProjectParams, SchemeParams
from fastapi.testclient import TestClient

REPO_RULES = default_rules_dir()


def _write_rules(path: Path, rules: list[dict]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "x.yaml").write_text(
        yaml.safe_dump(rules, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def test_registry_covers_mainland_provinces() -> None:
    assert len(MAINLAND_PROVINCES) == 31
    assert len(set(PROVINCE_CODES)) == 31
    # 内部缩写不是官方代码，但 GB/T 2260 的六位码要带上，便于与外部数据对齐
    assert all(p.gb_code.isdigit() and len(p.gb_code) == 6 for p in MAINLAND_PROVINCES)
    # 只收大陆：不含港澳台（71/81/82 开头）
    assert not {p.gb_code[:2] for p in MAINLAND_PROVINCES} & {"71", "81", "82"}
    # GB 是册代码但不是省份
    assert GB_PACK not in PROVINCE_CODES


def test_pack_labels() -> None:
    assert pack_label(GB_PACK) == "国家标准"
    assert pack_label("ZJ") == "浙江省地方标准"
    assert pack_label("ZZ") == "ZZ"  # 未知代码原样返回，不编造名字


def test_region_rule_id_and_pack_must_agree(tmp_path: Path) -> None:
    base = {
        "name": "示例",
        "type": "hard",
        "when": "slab_thickness >= 0",
        "check": "slab_thickness >= 100",
        "message": "楼板厚度不足",
        "source": "经验规则（土木组）：按 100 mm 控制",
    }
    # 正确：地区码与 pack 一致
    _write_rules(tmp_path / "ok", [{**base, "id": "ZJ-S-01", "pack": "ZJ"}])
    loaded = load_rules_from_dir(tmp_path / "ok")
    assert loaded.rules[0].pack == "ZJ"
    assert loaded.packs == ("ZJ",)

    # 地区码与 pack 不一致 → 拒绝加载
    _write_rules(tmp_path / "mismatch", [{**base, "id": "ZJ-S-01", "pack": "JS"}])
    with pytest.raises(RuleLoadError):
        load_rules_from_dir(tmp_path / "mismatch")

    # 册代码不在注册表里 → 拒绝（选不中的规则等于白写）
    _write_rules(tmp_path / "unknown", [{**base, "id": "ZZ-S-01", "pack": "ZZ"}])
    with pytest.raises(RuleLoadError):
        load_rules_from_dir(tmp_path / "unknown")

    # 没有地区码却声明了地方册 → 拒绝
    _write_rules(tmp_path / "noregion", [{**base, "id": "S-99", "pack": "ZJ"}])
    with pytest.raises(RuleLoadError):
        load_rules_from_dir(tmp_path / "noregion")

    # 国标规则（不写 pack）默认归 GB
    _write_rules(tmp_path / "gb", [{**base, "id": "S-99"}])
    assert load_rules_from_dir(tmp_path / "gb").rules[0].pack == GB_PACK


def test_select_packs_filters_without_mutating_the_original() -> None:
    full = load_rules_from_dir(REPO_RULES)
    assert "ZJ" in full.packs
    zj_ids = {r.id for r in full.rules if r.pack == "ZJ"}
    assert zj_ids  # 浙江册里有已核过原文的条文

    gb_only = full.select_packs(["GB"])
    assert gb_only.rules and not (zj_ids & {r.id for r in gb_only.rules})
    # 原件不受影响：全局缓存的那份永远含全部册
    assert zj_ids <= {r.id for r in full.rules}
    # 全选时原样返回同一个对象（不必要地复制会浪费）。
    # 这里用 full.packs 而不是写死的 ["GB", "ZJ"]——每收一个新省册，
    # 写死的列表就不再等于全集，测试会莫名其妙地变红。
    assert full.select_packs(full.packs) is full


def test_project_params_requires_gb_and_known_packs() -> None:
    # 留空＝只用国家标准。刻意不设成 ["GB"] 的默认值：前端按"字段是否全为空"
    # 判断新建项目，凭空多一个非空默认值会被当成"参数已经填过了"。
    assert ProjectParams().standard_packs is None
    assert ProjectParams(province="ZJ", standard_packs=["GB", "ZJ"]).standard_packs == ["GB", "ZJ"]
    # 去重且保持顺序
    assert ProjectParams(province="ZJ", standard_packs=["GB", "ZJ", "ZJ"]).standard_packs == ["GB", "ZJ"]
    # 不能关掉国标
    with pytest.raises(ValueError, match="国家标准是底线"):
        ProjectParams(standard_packs=["ZJ"])
    # 未知册
    with pytest.raises(ValueError, match="未知的标准册"):
        ProjectParams(standard_packs=["GB", "ZZ"])
    # 省份校验：合法写法会被规整成大写代码
    assert ProjectParams(province=" zj ").province == "ZJ"
    with pytest.raises(ValueError, match="未知的省份代码"):
        ProjectParams(province="浙江")


PROJECT = {
    "site_area": 18000,
    "far_max": 2.5,
    "density_max": 0.22,
    "height_max": 120,
    "climate_zone": "夏热冬冷",
    "seismic_intensity": "6度(0.05g)",
}
MIC_SCHEME = {
    "structure_type": "MiC",
    "mic_system": "模块化叠合剪力墙结构",
    "floors": 20,
    "floor_height": 3.0,
    "concrete_grade": 30,
    "units": 320,
}


def _evaluate_items(packs: list[str], **overrides: object) -> dict[str, str]:
    """跑一次评估，返回 ``规则 ID → 状态``（状态见 app/models/eval.py 的 ComplianceStatus）。"""
    ruleset = load_rules_from_dir(REPO_RULES).select_packs(packs)
    params = {**MIC_SCHEME, **overrides}
    local = [code for code in packs if code != "GB"]
    project = {**PROJECT, "standard_packs": packs, "province": local[0] if local else None}
    results = evaluate(
        ProjectParams.model_validate(project),
        [SchemeInput(scheme_id="1", name="MiC 示例", params=SchemeParams.model_validate(params))],
        ruleset,
    )
    return {item.rule_id: item.status for item in results[0].compliance}


def _evaluate_ids(packs: list[str]) -> set[str]:
    return set(_evaluate_items(packs))


def test_evaluation_only_runs_the_selected_packs() -> None:
    gb_only = _evaluate_ids(["GB"])
    with_zj = _evaluate_ids(["GB", "ZJ"])

    # 浙江册的规则在默认（只开 GB）时**根本不出现**——不是"不适用"，是没加载
    assert not {i for i in gb_only if i.startswith("ZJ-")}
    assert {i for i in with_zj if i.startswith("ZJ-")} == {
        "ZJ-S-01",
        "ZJ-S-02",
        "ZJ-S-03",
        "ZJ-S-04",
        "ZJ-S-05",
        "ZJ-S-06",
    }
    # 开了地方册只会**多**出规则，不会挤掉国标
    assert gb_only <= with_zj


def test_standard_packs_round_trips_through_excel(tmp_path: Path) -> None:
    """项目层的册选择必须能经 Excel 往返（导出写逗号分隔，解析要读回列表）。

    这是"新增字段类型要同时检查写入与读取两端"的又一次提醒：项目层解析器原先
    没有 ``array<...>`` 分支，加了列表字段之后"导出再解析"会直接报错
    （前端离线快照那条测试也会因此变红）。
    """
    project = {**PROJECT, "standard_packs": ["GB", "ZJ"], "province": "ZJ"}
    path = write_export(tmp_path / "packs.xlsx", project, [{"name": "示例", "params": MIC_SCHEME}])
    parsed = parse_workbook(path)
    assert not parsed.errors
    assert list(parsed.project_params["standard_packs"]) == ["GB", "ZJ"]
    assert parsed.project_params["province"] == "ZJ"


def test_every_province_pack_is_selectable() -> None:
    """31 个省册都要能被选中（哪怕还是空册）——注册表与引擎必须对得上。"""
    full = load_rules_from_dir(REPO_RULES)
    for code in PROVINCE_CODES:
        selected = full.select_packs(["GB", code])
        assert selected.rules, code
        # 选中后只剩 GB 与本省：别的省一条都不该混进来
        assert {r.pack for r in selected.rules} <= {"GB", code}


def test_new_local_fields_actually_drive_judgement() -> None:
    """新加的地方字段必须真的参与判定，否则加字段等于没加。

    山西 DBJ04/T 437-2022：5.2.11 层高一般 ≥3.0m、**设新风系统时 ≥3.2m**；
    4.2.2 日照按**冬至日累计 1h**。这三条正好覆盖"条件表达式、枚举标准日、新字段"。
    """
    # 3.1m + 有新风 → 不达标（要求 3.2m）；冬至日 0.5h → 不达标（要求 1h）
    bad = _evaluate_items(
        ["GB", "SX"],
        floor_height=3.1,
        has_fresh_air=True,
        daylight_standard_day="冬至日",
        sunlight_hours=0.5,
    )
    assert bad["SX-Q-01"] == "failed"
    assert bad["SX-Q-02"] == "failed"

    # 同样 3.1m，但没有新风 → 达标（要求 3.0m）；日照 1.2h → 达标
    good = _evaluate_items(
        ["GB", "SX"],
        floor_height=3.1,
        has_fresh_air=False,
        daylight_standard_day="冬至日",
        sunlight_hours=1.2,
    )
    assert good["SX-Q-01"] == "passed"
    assert good["SX-Q-02"] == "passed"

    # 标准日不对（按大寒日分析）→ 冬至日那条不适用，交给提示条 SX-Q-03
    mismatched = _evaluate_items(
        ["GB", "SX"],
        floor_height=3.1,
        has_fresh_air=False,
        daylight_standard_day="大寒日",
        sunlight_hours=3.0,
    )
    assert mismatched["SX-Q-02"] == "not_applicable"
    assert mismatched["SX-Q-03"] == "failed"  # check 恒为 False，warning 级

    # 字段没填 → 数据不足，不会误判为通过
    missing = _evaluate_items(["GB", "SX"], floor_height=3.1)
    assert missing["SX-Q-01"] == "insufficient_data"


def test_boolean_fields_round_trip_through_excel(tmp_path: Path) -> None:
    """布尔字段必须能经 Excel 往返。

    这是"新增字段类型要同时检查写入与读取两端"的第三条教训（前两条是项目层
    缺 ``array<...>`` 分支、整体缺 boolean 分支）：地方册的层高加严条款以
    "是否设新风系统"这类开关为条件，读不回来就等于规则永远判不了。
    """
    scheme = {**MIC_SCHEME, "has_fresh_air": True, "has_stretcher_elevator": False}
    path = write_export(tmp_path / "bools.xlsx", PROJECT, [{"name": "示例", "params": scheme}])
    parsed = parse_workbook(path)
    assert not parsed.errors
    saved = parsed.schemes[0]["params"]
    assert saved["has_fresh_air"] is True
    assert saved["has_stretcher_elevator"] is False


def test_packs_endpoint_lists_gb_and_every_province(client: TestClient) -> None:
    body = client.get("/api/standards/packs").json()
    assert len(body) == 32  # GB + 31 个省级行政区
    by_code = {item["code"]: item for item in body}

    assert by_code["GB"]["always_on"] is True
    assert by_code["GB"]["scope"] == "全国"
    assert by_code["GB"]["rule_count"] > 0
    assert by_code["ZJ"]["label"] == "浙江省地方标准"
    assert by_code["ZJ"]["gb_code"] == "330000"
    assert by_code["ZJ"]["rule_count"] == 6
    assert by_code["ZJ"]["hard_count"] == 6
    assert by_code["NX"]["always_on"] is False
    # 已收条文的省册清单：收新省时要一起更新——它同时是"哪些省已有规则"的清单。
    # GB 不写死（国标规则会随核定轮次增减），只要求它有内容。
    local_counts = {
        code: item["rule_count"] for code, item in by_code.items() if code != "GB"
    }
    assert {c: n for c, n in local_counts.items() if n} == {
        "BJ": 4,
        "TJ": 3,
        "HE": 3,
        "SX": 4,
        "LN": 6,
        "JL": 5,
        "SH": 3,
        "JS": 3,
        "ZJ": 6,
        "SD": 2,
        "HB": 4,
        "HN": 3,
        "GS": 3,
        "CQ": 3,
        "SC": 2,
        "NX": 3,
        "XJ": 1,
    }
    assert by_code["GB"]["rule_count"] > 0
    # 尚未取得现行、可逐条核验正文的省册仍为空，并写明原因。
    assert by_code["AH"]["rule_count"] == 0
    assert by_code["AH"]["note"]
    assert sum(1 for item in body if item["always_on"]) == 1
