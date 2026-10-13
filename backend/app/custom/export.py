"""把运行期的自定义内容导出成**可以落进仓库**的片段（回灌路径）。

覆盖层是**草稿台**：使用者在这里试出来的字段、规则、选项与权重，最终要变成
``rules/*.yaml`` 与 ``params.py`` 里的正式内容，经 CI 校验后才是权威
（见 ``docs/design-custom-add.md`` 第一节第二条决策）。

这个模块生成那些片段，并把"落地步骤"一并写清楚。每条片段都尽量做到**粘进去就能用**：

- Python 片段**去掉注释行、去掉类体缩进**后能通过 ``ast.parse``；
- YAML 片段能通过 ``yaml.safe_load``；
- 凡是**不能自动改对**的地方（保留前缀 ``X-`` 必须换维度前缀、角色键要改成英文标识、
  ``compliance`` 是硬门槛要专业组确认），都在片段里写明，而不是悄悄替使用者决定。

⚠️ 最容易被忽略的一条：**规则 ID 的保留前缀 ``X-``**。它在运行期专属；
文件里出现 ``X-`` 会让"进了 git 的"和"界面加的"再也分不开，
所以 ``scripts/check_rules.py`` 对文件里的 ``X-`` 直接报错——导出片段会给出建议编号。
"""

from __future__ import annotations

from typing import Any

import yaml
from sqlmodel import Session

from app.custom import fields as fields_service
from app.custom import options as options_service
from app.custom import rules as rules_service
from app.custom import templates as templates_service
from app.engine.mcdm import CRITERION_ORDER
from app.engine.rules import get_ruleset
from app.models.params import IRREGULARITY_OPTIONS, RISK_FEATURE_OPTIONS

__all__ = ["COMPLIANCE_REFERENCE", "FIELD_PYTYPES", "export_overlay"]

#: 评分指标按 dimension 决定落进哪个文件，也就决定了前缀。
PREFIX_BY_DIMENSION: dict[str, str] = {
    "quality": "Q",
    "structure": "S",
    "construction": "K",
    "green": "G",
}

#: 硬约束按**主题**选文件（合规 C / 结构 S / 施工 K），无法自动判断，列出候选。
HARD_PREFIXES: tuple[str, ...] = ("C", "S", "K")

#: 自定义字段的类型 → Python 注解。
FIELD_PYTYPES: dict[str, str] = {
    "number": "float",
    "integer": "int",
    "ratio": "float",
    "text": "str",
    "list": "list[str]",
}

#: ``rules/weights.yaml`` 里 compliance 是**独立硬门槛、不计入评分**；
#: 自定义模板只存四个评分维度，所以导出时补一个参考值，并在片段里注明要专业组确认。
COMPLIANCE_REFERENCE = 0.20

_OPTION_LISTS: dict[str, list[str]] = {
    "risk_features": RISK_FEATURE_OPTIONS,
    "irregularity_items": IRREGULARITY_OPTIONS,
}

#: 字段名 → params.py 里候选列表的**真实常量名**。
#: 不能靠 `field.upper() + "_OPTIONS"` 拼：`risk_features` 拼出来是
#: `RISK_FEATURES_OPTIONS`，而真实常量叫 `RISK_FEATURE_OPTIONS`（单数）。
_OPTION_LIST_NAMES: dict[str, str] = {
    "risk_features": "RISK_FEATURE_OPTIONS",
    "irregularity_items": "IRREGULARITY_OPTIONS",
}


def _quote(text: str) -> str:
    """把文本塞进 YAML 双引号标量里。"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _next_free_ids() -> dict[str, str]:
    """每个前缀的下一个可用编号（按现有规则号顺延）。

    编号不必连续（``docs/rules-guide.md`` 说明过），所以取"最大号 + 1"，
    而不是"第一个空位"——这样不会把新规则塞进历史编号的缝里。
    """
    used: dict[str, list[int]] = {}
    for rule in get_ruleset().rules:
        prefix, _, number = rule.id.partition("-")
        if number.isdigit():
            used.setdefault(prefix, []).append(int(number))
    return {p: f"{p}-{max(ns) + 1:02d}" for p, ns in used.items() if ns}


def _rules_yaml(rows: list[Any], next_free: dict[str, str]) -> str:
    """自定义规则 → ``rules/*.yaml`` 的片段。"""
    if not rows:
        return "# （没有自定义规则）\n"
    blocks: list[str] = []
    for row in rows:
        payload = dict(row.payload)
        rule_id = row.rule_id
        dimension = payload.get("dimension")
        prefix = PREFIX_BY_DIMENSION.get(str(dimension)) if dimension else None
        if prefix:
            suggested = next_free.get(prefix, f"{prefix}-??")
            hint = (
                f"# ⚠️ 入库前把 id 从 {rule_id} 改成 {suggested}"
                f"（dimension={dimension} → {prefix} 系列）；"
                f"X- 是运行期自定义的保留前缀，文件里不允许出现。\n"
            )
        else:
            candidates = " / ".join(
                f"{p} 用 {next_free.get(p, p + '-??')}" for p in HARD_PREFIXES
            )
            hint = (
                f"# ⚠️ 入库前把 id 从 {rule_id} 换成维度前缀并顺延编号"
                f"（硬约束按主题选文件：合规 C / 结构 S / 施工 K，当前可用编号 {candidates}）；"
                f"X- 是运行期自定义的保留前缀，文件里不允许出现。\n"
            )
        body = yaml.safe_dump(
            [payload], allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000
        )
        blocks.append(hint + body.rstrip("\n"))
    return "\n\n".join(blocks) + "\n"


def _conditions(kind: str) -> str:
    """保留注册表约束；通用数值并未规定必须为正。"""
    if kind == "ratio":
        return "        ge=0,\n        le=1,\n"
    return ""


def _fields_python(rows: list[Any]) -> str:
    """自定义字段 → ``params.py`` 的类体片段。"""
    if not rows:
        return "# （没有自定义字段）\n"
    blocks: list[str] = []
    for row in rows:
        pytype = FIELD_PYTYPES.get(row.kind, "str")
        meta = f"{row.unit!r}, {row.group!r}, {row.label!r}"
        if row.options:
            options = ", ".join(repr(item) for item in row.options)
            meta += f", options=[{options}]"
        description = row.description or row.label
        blocks.append(
            f"# 落到 app/models/params.py 的 SchemeParams（分组：{row.group}）；"
            f"入库后必须重跑生成链（export_schema → gen_field_table → make_template → "
            f"gen:types → sync:mock → export_frontend_fixtures）\n"
            f"    {row.key}: {pytype} | None = Field(\n"
            f"        None,\n"
            f"        description={description!r},\n"
            f"{_conditions(row.kind)}"
            f"        json_schema_extra=_meta({meta}),\n"
            f"    )"
        )
    return "\n\n".join(blocks) + "\n"


def _options_python(rows: list[Any], custom_field_keys: set[str]) -> str:
    """自定义枚举选项 → ``params.py`` 里候选元组的追加行。"""
    if not rows:
        return "# （没有自定义枚举选项）\n"
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row.field, []).append(row.value)

    blocks: list[str] = []
    for field, values in grouped.items():
        target = _OPTION_LISTS.get(field)
        if target is not None:
            header = (
                f"# 追加到 app/models/params.py 的 {_OPTION_LIST_NAMES[field]}"
                f"（放在内建候选值之后）："
            )
        elif field in custom_field_keys:
            header = (
                f"# 「{field}」是自定义字段：先把它按上面的字段片段落进 params.py，"
                f"再把候选值追加到它的 options 里："
            )
        else:
            header = f"# 字段「{field}」未识别，请人工确认落点："
        lines = "\n".join(f"    {value!r}," for value in values)
        blocks.append(f"{header}\n{lines}")
    return "\n\n".join(blocks) + "\n"


def _weights_yaml(rows: list[Any]) -> str:
    """自定义角色权重模板 → ``rules/weights.yaml`` 的 ``roles:`` 片段。"""
    if not rows:
        return "# （没有自定义角色权重模板）\n"
    blocks: list[str] = []
    for row in rows:
        numbers = list(row.weights or [])
        if len(numbers) != len(CRITERION_ORDER):
            blocks.append(f"# 模板「{row.name}」的权重数量异常，请人工核对：{numbers}\n")
            continue
        weights = {"compliance": COMPLIANCE_REFERENCE}
        weights.update(dict(zip(CRITERION_ORDER, (round(float(v), 4) for v in numbers), strict=True)))
        body = yaml.safe_dump(
            {f"custom_role_{row.id}": {
                "label": row.name,
                "weights": weights,
                "rationale": row.note or row.name,
            }},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1000,
        )
        blocks.append(
            f"# ⚠️ 落到 rules/weights.yaml 的 roles: 之下。三件必须人工确认的事：\n"
            f"#   1) 角色键 custom_role_{row.id} 建议改成英文标识（如 agent_construction），"
            f"并同步 app/engine/weights.py 的 ROLE_KEYS；\n"
            f"#   2) compliance 是独立硬门槛、不计入评分，片段里给的是内建常见值 "
            f"{COMPLIANCE_REFERENCE}，请专业组确认；\n"
            f"#   3) rationale 需补成能说服人的一句话；来源见下面的 source。\n"
            f"#   来源：{' '.join((row.source or '（未填）').splitlines())}\n"
            + body.rstrip("\n")
        )
    return "\n\n".join(blocks) + "\n"


def export_overlay(session: Session) -> dict[str, Any]:
    """把当前覆盖层导出成片段 + 落地清单。

    Returns:
        ``rules_yaml`` / ``fields_python`` / ``options_python`` / ``weights_yaml`` 四段片段，
        ``checklist`` 落地步骤，``counts`` 各类条数，``notes`` 全局注意事项，
        ``markdown`` 一份可直接贴给人看的汇总。
    """
    rule_rows = rules_service.list_rules(session)
    field_rows = fields_service.list_fields(session)
    option_rows = options_service.list_options(session)
    template_rows = templates_service.list_templates(session)
    next_free = _next_free_ids()

    sections = {
        "rules_yaml": _rules_yaml(rule_rows, next_free),
        "fields_python": _fields_python(field_rows),
        "options_python": _options_python(option_rows, {row.key for row in field_rows}),
        "weights_yaml": _weights_yaml(template_rows),
    }
    counts = {
        "rules": len(rule_rows),
        "fields": len(field_rows),
        "options": len(option_rows),
        "templates": len(template_rows),
    }
    notes = [
        "覆盖层是草稿台：导出片段粘进仓库、跑通 CI 之后，才算成为权威内容。",
        "规则 ID 的保留前缀 X- 只能存在于运行期；文件里出现 X- 会被 check_rules 直接报错。",
        "自定义字段入库后必须重跑生成链，否则 schema / Excel / 前端类型不会带上它。",
        "权重模板入库时角色键要改成英文标识，并同步 app/engine/weights.py 的 ROLE_KEYS。",
        "内建规则不能引用自定义字段：若自定义规则要引用自定义字段，两者必须一起入库。",
        "字段片段是模型骨架：list 的 options 只提供展示元数据，不能代替封闭选项校验；回灌时须人工保留对应校验器，以及运行期数值的严格类型与有限值要求。",
    ]
    checklist = [
        "把 rules_yaml 里的规则按维度拆进 rules/*.yaml，并按要求把 X- 编号换成建议编号。",
        "把 fields_python 的字段块粘进 app/models/params.py 的 SchemeParams（注意分组）。",
        "逐字段补齐与运行期一致的校验器，尤其是列表候选值、严格数值类型及有限值；通用 number/integer 不能擅自增加正数限制。",
        "把 options_python 的候选值追加到对应字段的候选列表里。",
        "把 weights_yaml 的角色块粘进 rules/weights.yaml 的 roles: 之下（键改成英文并同步 ROLE_KEYS）。",
        "重跑生成链：export_schema → gen_field_table → make_template → gen:types → sync:mock → "
        "export_frontend_fixtures --grid-step 10。",
        "跑 scripts/check_rules.py、后端 pytest 与前端测试，全绿后提交并等 CI。",
        "CI 通过并合并后，回到界面把已入库的自定义内容删掉——否则它会以覆盖层的形式重复出现。",
    ]
    markdown = _markdown(sections, counts, notes, checklist)
    return {**sections, "counts": counts, "notes": notes, "checklist": checklist, "markdown": markdown}


def _markdown(
    sections: dict[str, str], counts: dict[str, int], notes: list[str], checklist: list[str]
) -> str:
    """把四段片段与清单拼成一份可直接贴给人看的汇总。"""
    lines = [
        "# 自定义内容导出（回灌到仓库）",
        "",
        f"待入库：规则 {counts['rules']} 条、字段 {counts['fields']} 个、"
        f"枚举选项 {counts['options']} 条、权重模板 {counts['templates']} 个。",
        "",
        "## 落地步骤",
        "",
        *[f"{index}. {step}" for index, step in enumerate(checklist, start=1)],
        "",
        "## 注意事项",
        "",
        *[f"- {note}" for note in notes],
        "",
        "## 1. 规则 → rules/*.yaml",
        "",
        "```yaml",
        sections["rules_yaml"].rstrip(),
        "```",
        "",
        "## 2. 字段 → params.py",
        "",
        "```python",
        sections["fields_python"].rstrip(),
        "```",
        "",
        "## 3. 枚举选项 → params.py 的候选列表",
        "",
        "```python",
        sections["options_python"].rstrip(),
        "```",
        "",
        "## 4. 角色权重模板 → rules/weights.yaml",
        "",
        "```yaml",
        sections["weights_yaml"].rstrip(),
        "```",
        "",
    ]
    return "\n".join(lines)
