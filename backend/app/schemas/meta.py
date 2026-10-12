"""生成带中文元信息的 JSON Schema。

Pydantic v2 的 ``model_json_schema()`` 会把字段级 ``json_schema_extra``
平铺到属性对象的顶层（而不是塞进 ``json_schema_extra`` 子键），所以这里直接从
属性对象读取 ``unit`` / ``group`` / ``label``。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_META_KEYS = ("unit", "group", "label", "enum", "options", "essential", "extensible")


def enriched_schema(model: type[BaseModel]) -> dict[str, Any]:
    """构造带有 ``fields`` 列表的增强 schema。

    返回结构示例::

        {
          "title": "...",
          "description": "...",
          "group_order": ["基本信息", ...],
          "fields": [
            {"name": "site_area", "type": "number", "required": False,
             "label": "用地面积", "unit": "m²", "group": "基本信息", "constraints": {...}},
            ...
          ]
        }
    """
    base = model.model_json_schema()
    # Pydantic 把类级 extra 也放在 schema 顶层，提取出来
    title = base.pop("title", model.__name__)
    description = base.pop("description", "")
    group_order: list[str] = base.pop("group_order", [])  # type: ignore[arg-type]

    properties: dict[str, Any] = base.get("properties", {})
    required: set[str] = set(base.get("required", []))

    fields: list[dict[str, Any]] = []
    for name, prop in properties.items():
        field_info: dict[str, Any] = {
            "name": name,
            "label": prop.get("label", name),
            "description": prop.get("description", ""),
            "unit": prop.get("unit", ""),
            "group": prop.get("group", ""),
            "type": _simplify_type(prop),
            "required": name in required,
            "constraints": _constraints(prop),
        }
        if "enum" in prop:
            field_info["enum"] = prop["enum"]
        if "options" in prop:
            field_info["options"] = prop["options"]
        if prop.get("essential"):
            field_info["essential"] = True
        if prop.get("extensible"):
            # 开放枚举：允许使用者在界面上追加候选值（见 app/custom/options.py）。
            # 只有显式声明 extensible 的字段才放行——像 structure_type 这样的封闭枚举
            # 一旦多出规则不认识的取值，依赖它的规则会静默失效。
            field_info["extensible"] = True
        fields.append(field_info)

    return {
        "title": title,
        "description": description,
        "group_order": group_order,
        "fields": fields,
    }


def _simplify_type(prop: dict[str, Any]) -> str:
    """把 Pydantic 的类型描述简化为前端好处理的字符串。"""
    if prop.get("type") == "array":
        item_type = prop.get("items", {}).get("type", "string")
        return f"array<{item_type}>"
    if prop.get("type") == "object":
        additional = prop.get("additionalProperties", {})
        value_type = additional.get("type", "string")
        return f"object<{value_type}>"
    if "anyOf" in prop:
        non_null = [x for x in prop["anyOf"] if x.get("type") != "null"]
        if non_null:
            sub = non_null[0]
            if sub.get("type") == "object":
                value_type = sub.get("additionalProperties", {}).get("type", "string")
                return f"object<{value_type}>"
            return sub.get("type", "string")
    return prop.get("type", "string")


def _constraints(prop: dict[str, Any]) -> dict[str, Any]:
    """抽取数值范围 / 长度约束等。"""
    out: dict[str, Any] = {}
    for k in (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
    ):
        if k in prop:
            out[k] = prop[k]
    return out
