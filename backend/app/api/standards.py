"""规则册（标准册）清单路由。

前端用它渲染"适用标准"的勾选框：每册叫什么、管哪里、当前收了多少条规则。
**只读**：册的**选择**是项目层字段（``ProjectParams.standard_packs``），
写入走项目更新接口；这里只回答"有哪些册可选、各册现在什么状态"。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.engine.regions import GB_PACK, MAINLAND_PROVINCES, pack_label
from app.engine.rules import RuleDef, get_ruleset

router = APIRouter(prefix="/standards", tags=["standards"])


class PackRead(BaseModel):
    """一个规则册的对外描述。"""

    model_config = ConfigDict(json_schema_extra={"title": "规则册"})

    code: str = Field(description="册代码：GB 或省级地区码（如 ZJ）")
    label: str = Field(description="中文名，如「浙江省地方标准」")
    scope: str = Field(description="适用范围，如「全国」「浙江省」")
    gb_code: str | None = Field(None, description="省级册的 GB/T 2260 行政区划码")
    rule_count: int = Field(description="该册当前收录的规则条数；0 表示尚无已核定条文")
    hard_count: int = Field(description="硬约束条数")
    metric_count: int = Field(description="评分指标条数")
    always_on: bool = Field(description="是否永远生效（只有 GB 为 true，不可关闭）")
    coverage: Literal["partial", "not_collected"] = Field(description="partial 为部分规则，not_collected 为尚未收录；均不代表完整覆盖")
    note: str = Field("", description="给专业组的说明")


def _pack_read(code: str, scope: str, gb_code: str | None, rules: list[RuleDef]) -> PackRead:
    note = "仅覆盖已收录条目，不代表完整规范审查；适用对象、版本和项目条件需专业组核定"
    if code != GB_PACK and not rules:
        note = "尚未收录地方条文，选中后仍仅执行国家册；不能宣称已覆盖该地区规范"
    return PackRead(
        code=code,
        label=pack_label(code),
        scope=scope,
        gb_code=gb_code,
        rule_count=len(rules),
        hard_count=sum(1 for rule in rules if rule.type == "hard"),
        metric_count=sum(1 for rule in rules if rule.type == "metric"),
        always_on=code == GB_PACK,
        coverage="partial" if rules else "not_collected",
        note=note,
    )


@router.get(
    "/packs",
    response_model=list[PackRead],
    summary="规则册清单（国家标准 + 大陆 31 个省级行政区）",
)
def list_packs() -> list[PackRead]:
    """列出所有可选的标准册，供前端渲染"适用标准"勾选框。

    - **GB 永远生效**，不允许在项目里关掉；
    - 省级册**默认关闭**，由项目在 ``standard_packs`` 里显式开启——地方条例的适用范围
      就是那一省，别的项目未必适用；
    - ``rule_count`` 为 0 的省册表示**政策上可收、但还没有逐条核对过原文的条文**：
      我们不凭记忆或二手转录往册里塞规则（收录纪律见 docs/design-regional-packs.md）。

    返回的是"有哪些册"，**不代表项目已经启用**——项目启用了哪些看它自己的
    ``standard_packs`` 字段。
    """
    by_pack: dict[str, list[RuleDef]] = {}
    for rule in get_ruleset().rules:
        by_pack.setdefault(rule.pack, []).append(rule)

    packs = [_pack_read(GB_PACK, "全国", None, by_pack.get(GB_PACK, []))]
    packs.extend(
        _pack_read(province.code, province.name, province.gb_code, by_pack.get(province.code, []))
        for province in MAINLAND_PROVINCES
    )
    return packs
