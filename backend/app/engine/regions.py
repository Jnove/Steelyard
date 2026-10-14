"""地区（省级行政区）注册表：规则"册"（pack）的名字与编号来源。

**为什么需要它**：国家层面标准之外，各省还有地方标准与地方导则（DB33 等）。
它们在实战里可以灵活选用，但**不能混进国标**——所以规则按"册"归属：

- ``GB``：国家标准册（GB / GB-T、JGJ 等行业标准、住建部部委文件），**永远生效**，
  是所有项目的底线；
- 其余每册对应一个省级行政区，**默认关闭**，由项目显式选择（见 ``ProjectParams.standard_packs``）。

**编号约定**：地方规则的 ID 形如 ``ZJ-S-01``——两字母地区码 + 维度字母 + 两位数字。
它同时用于三处：规则 ID、``pack`` 字段、册清单接口，三处必须一致（校验器会查）。

**地区码的取法**：两字母**缩写是内部约定**（便于编号与阅读），不是官方代码；
官方代码是 GB/T 2260 的六位行政区划码，一并记录在 :attr:`Province.gb_code` 里，
用于和外部数据（统计、地图）对齐。**只收大陆 31 个省级行政区**，
不含港澳台（编号 71/81/82 开头的三个）。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "GB_PACK",
    "MAINLAND_PROVINCES",
    "PROVINCE_BY_CODE",
    "PROVINCE_CODES",
    "Province",
    "is_region_code",
    "pack_label",
    "pack_options",
]


@dataclass(frozen=True)
class Province:
    """一个省级行政区。"""

    #: 两字母地区码，用于规则 ID 与 pack（如 ``ZJ``）
    code: str
    #: 全称（如 ``浙江省``）
    name: str
    #: GB/T 2260 六位行政区划码（如 ``330000``）
    gb_code: str


#: 国家标准册的代码。它**永远生效**，不允许在项目里关掉。
GB_PACK = "GB"

#: 大陆 31 个省级行政区。顺序按 GB/T 2260 的行政区划码，便于与外部数据对照。
MAINLAND_PROVINCES: tuple[Province, ...] = (
    Province("BJ", "北京市", "110000"),
    Province("TJ", "天津市", "120000"),
    Province("HE", "河北省", "130000"),
    Province("SX", "山西省", "140000"),
    Province("NM", "内蒙古自治区", "150000"),
    Province("LN", "辽宁省", "210000"),
    Province("JL", "吉林省", "220000"),
    Province("HL", "黑龙江省", "230000"),
    Province("SH", "上海市", "310000"),
    Province("JS", "江苏省", "320000"),
    Province("ZJ", "浙江省", "330000"),
    Province("AH", "安徽省", "340000"),
    Province("FJ", "福建省", "350000"),
    Province("JX", "江西省", "360000"),
    Province("SD", "山东省", "370000"),
    Province("HA", "河南省", "410000"),
    Province("HB", "湖北省", "420000"),
    Province("HN", "湖南省", "430000"),
    Province("GD", "广东省", "440000"),
    Province("GX", "广西壮族自治区", "450000"),
    Province("HI", "海南省", "460000"),
    Province("CQ", "重庆市", "500000"),
    Province("SC", "四川省", "510000"),
    Province("GZ", "贵州省", "520000"),
    Province("YN", "云南省", "530000"),
    Province("XZ", "西藏自治区", "540000"),
    Province("SN", "陕西省", "610000"),
    Province("GS", "甘肃省", "620000"),
    Province("QH", "青海省", "630000"),
    Province("NX", "宁夏回族自治区", "640000"),
    Province("XJ", "新疆维吾尔自治区", "650000"),
)

PROVINCE_BY_CODE: dict[str, Province] = {p.code: p for p in MAINLAND_PROVINCES}

PROVINCE_CODES: tuple[str, ...] = tuple(p.code for p in MAINLAND_PROVINCES)


def is_region_code(code: str) -> bool:
    """是不是一个合法的册代码（``GB`` 或某个省级行政区）。"""
    return code == GB_PACK or code in PROVINCE_BY_CODE


def pack_label(code: str) -> str:
    """册的中文名，给界面与报告直接用。"""
    if code == GB_PACK:
        return "国家标准"
    province = PROVINCE_BY_CODE.get(code)
    return f"{province.name}地方标准" if province else code


def pack_options(codes: tuple[str, ...] | None = None) -> list[str]:
    """给前端表单用的候选册清单（默认：``GB`` + 全部省级行政区）。"""
    return [GB_PACK, *(codes if codes is not None else PROVINCE_CODES)]
