"""Excel 模板生成、导出与解析的共享模块。

依赖 openpyxl（纯 Python，对 WPS / Excel / LibreOffice 均兼容）。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.workbook import Workbook as WB
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from app.models import ProjectParams, SchemeParams
from app.schemas.meta import enriched_schema

# —— 模板常量 —— #

#: 模板支持的同时比选方案数；超出时 ``write_export`` 会拆到多张表。
MAX_SCHEMES = 6

#: 三个工作表的标题。
SHEET_PROJECT = "项目信息"
SHEET_SCHEMES = "方案参数"
SHEET_INSTRUCTIONS = "填写说明"

#: 关键样式。
HEADER_FILL = PatternFill("solid", fgColor="D9E9F6")  # 表头浅蓝
SECTION_FILL = PatternFill("solid", fgColor="F2F2F2")  # 分组标题灰
ESSENTIAL_FILL = PatternFill("solid", fgColor="FFF8DC")  # 必填浅黄 (Cornsilk)
HEADER_FONT = Font(bold=True)
SECTION_FONT = Font(bold=True, color="333333")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)

#: 列表 / 字典类字段在单元格里的分隔符（中文逗号优先，英文逗号兜底）。
LIST_SEPARATORS = ("，", ",")
DICT_PAIR_SEPARATORS = ("：", ":")
DICT_KV_SEPARATORS = (",", "，", ";", "；")


# —— 结果与错误 —— #


@dataclass
class ParseError:
    """单条解析错误。

    ``field`` 用英文字段名（与 schema 对应）便于程序定位；``label`` 是中文名，
    ``message`` 已经是面向用户的中文句子，三者组合显示给填写人。
    """

    scheme: str | None  #: 所属方案；项目层错误为 None
    field: str | None  #: 英文字段名；模板本身错误时为 None
    label: str  #: 中文 label（用于显示）
    message: str  #: 人类可读的错误信息


@dataclass
class ParseResult:
    """整个 xlsx 的解析结果。"""

    project_params: dict[str, Any] = field(default_factory=dict)
    schemes: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """无错误且至少解析出一个方案。"""
        return not self.errors and bool(self.schemes)


# —— 模板写入 —— #


def _build_enriched() -> tuple[dict[str, Any], dict[str, Any]]:
    """读取 ProjectParams / SchemeParams 的字段元信息。"""
    return enriched_schema(ProjectParams), enriched_schema(SchemeParams)


def _fields_by_group(enriched: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """按 ``group_order`` 把字段分组，便于渲染分组标题。"""
    out: list[tuple[str, list[dict[str, Any]]]] = []
    for group in enriched["group_order"]:
        rows = [f for f in enriched["fields"] if f.get("group") == group]
        if rows:
            out.append((group, rows))
    return out


def _ratio_field(kind: str) -> bool:
    """判断字段是否是 0-1 比例字段。"""
    if kind != "number":
        return False
    return True  # 我们靠约束 0≤x≤1 来识别，由调用方传入 constraints


def _write_header_row(ws: Worksheet, row: int, values: list[str]) -> None:
    """写表头行并加粗 + 浅蓝底。"""
    for col_idx, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col_idx, value=value)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER


def _auto_width(ws: Worksheet, widths: list[int]) -> None:
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _add_section_row(ws: Worksheet, row: int, text: str, span: int) -> None:
    """写一个跨多列的分组标题行。"""
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = SECTION_FONT
    cell.fill = SECTION_FILL
    cell.alignment = CENTER
    if span > 1:
        ws.merge_cells(
            start_row=row, start_column=1,
            end_row=row, end_column=span,
        )


def _apply_essential_fill(ws: Worksheet, row: int, col: int) -> None:
    cell = ws.cell(row=row, column=col)
    cell.fill = ESSENTIAL_FILL


def _make_numeric_validation(field: dict[str, Any]) -> DataValidation | None:
    """根据字段元信息构造数值 / 整数 / 小数范围验证。"""
    if field["type"] in ("number", "integer"):
        kind = "decimal" if field["type"] == "number" else "whole"
        dv = DataValidation(type=kind, operator="between", formula1=0, formula2=1e308)
        dv.error = f"【{field['label']}】必须是数字"
        dv.errorTitle = "类型错误"
        return dv
    return None


def _make_enum_validation(field: dict[str, Any]) -> DataValidation | None:
    """枚举字段的下拉验证。"""
    if "enum" not in field:
        return None
    quoted = ",".join(f'"{v}"' for v in field["enum"])
    dv = DataValidation(type="list", formula1=quoted, allow_blank=True)
    dv.error = f"【{field['label']}】必须是下列之一：{', '.join(field['enum'])}"
    dv.errorTitle = "取值不合法"
    return dv


def _write_project_sheet(wb: WB, project_meta: dict[str, Any]) -> None:
    """写"项目信息"工作表。"""
    ws = wb.create_sheet(SHEET_PROJECT)
    _auto_width(ws, [22, 24, 10, 50, 0])  # 最后一列 0 表示隐藏
    ws.column_dimensions["E"].hidden = True

    _write_header_row(ws, 1, ["字段中文名", "值", "单位", "说明"])
    # 隐藏列的标题用 ``__name__``，方便解析时识别列位置
    name_cell = ws.cell(row=1, column=5, value="__name__")
    name_cell.font = Font(color="999999")

    row = 2
    for group, fields in _fields_by_group(project_meta):
        _add_section_row(ws, row, f"【{group}】", span=4)
        row += 1
        for field_info in fields:
            ws.cell(row=row, column=1, value=field_info["label"]).alignment = LEFT_WRAP
            ws.cell(row=row, column=2, value=None)  # 用户填值
            ws.cell(row=row, column=3, value=field_info.get("unit", "—")).alignment = CENTER
            ws.cell(row=row, column=4, value=field_info.get("description", "")).alignment = LEFT_WRAP
            ws.cell(row=row, column=5, value=field_info["name"]).font = Font(color="999999")
            # 必填浅黄
            if field_info.get("essential"):
                _apply_essential_fill(ws, row, 2)
            # 数据验证
            dv = _make_enum_validation(field_info) or _make_numeric_validation(field_info)
            if dv is not None:
                dv.add(f"B{row}")
                ws.add_data_validation(dv)
            row += 1


def _write_scheme_sheet(wb: WB, scheme_meta: dict[str, Any]) -> None:
    """写"方案参数"工作表。"""
    ws = wb.create_sheet(SHEET_SCHEMES)
    scheme_names = [f"方案{chr(ord('A') + i)}" for i in range(MAX_SCHEMES)]
    _auto_width(
        ws,
        [22, 8] + [18] * MAX_SCHEMES + [0],
    )  # 最后一列隐藏
    name_col_idx = 3 + MAX_SCHEMES
    ws.column_dimensions[get_column_letter(name_col_idx)].hidden = True

    headers = ["字段中文名", "单位"] + scheme_names
    _write_header_row(ws, 1, headers)
    # 隐藏列的标题用 ``__name__``
    name_cell = ws.cell(row=1, column=name_col_idx, value="__name__")
    name_cell.font = Font(color="999999")

    row = 2
    visible_span = 2 + MAX_SCHEMES  # 标签 + 单位 + 6 个方案
    for group, fields in _fields_by_group(scheme_meta):
        _add_section_row(ws, row, f"【{group}】", span=visible_span)
        row += 1
        for field_info in fields:
            ws.cell(row=row, column=1, value=field_info["label"]).alignment = LEFT_WRAP
            ws.cell(row=row, column=2, value=field_info.get("unit", "—")).alignment = CENTER
            # 6 个方案的填写格
            for i in range(MAX_SCHEMES):
                ws.cell(row=row, column=3 + i, value=None)
            ws.cell(row=row, column=name_col_idx, value=field_info["name"]).font = Font(
                color="999999"
            )
            # 必填浅黄
            if field_info.get("essential"):
                for col in range(2, 3 + MAX_SCHEMES):
                    _apply_essential_fill(ws, row, col)
            # 数据验证：枚举 / 数值
            dv_enum = _make_enum_validation(field_info)
            if dv_enum is not None:
                dv_enum.add(f"C{row}:{get_column_letter(2 + MAX_SCHEMES)}{row}")
                ws.add_data_validation(dv_enum)
            dv_num = _make_numeric_validation(field_info)
            if dv_num is not None:
                dv_num.add(f"C{row}:{get_column_letter(2 + MAX_SCHEMES)}{row}")
                ws.add_data_validation(dv_num)
            row += 1


_INSTRUCTIONS_TEXT = """\
填写说明

比例字段（得房率、南向比例、窗地比、标准层重复率、预估装配率、建筑密度上限）请填 0-1 的小数，例如 0.82 表示 82%。
数值字段（面积、层高、层数、户数等）请填数字，不要写汉字或单位，如"三米"会被报错。
空格表示该项暂无数据，不视为错误。
风险特征一栏请用中文逗号分隔，例如"大悬挑，深基坑，高支模"。
结构体系只能选下拉框中的取值（剪力墙 / 框架-剪力墙 / 框架 / 钢结构 / MiC）。
可以整体调整行的顺序；列名"方案A / 方案B / ..."可以改成实际方案名（如"高层A / 小高层B"）。
户型配比 / 窗墙比 写为"键: 值"的形式，键值之间用中文冒号或英文冒号，多组之间用逗号分隔。
例如户型配比："两室: 60，三室: 60"；窗墙比："南: 0.40，北: 0.25"。
行末的隐藏英文列保存字段名，请勿改动；改动后导入会找不到对应字段。
"""


def _write_instructions_sheet(wb: WB) -> None:
    ws = wb.create_sheet(SHEET_INSTRUCTIONS)
    _auto_width(ws, [100])
    ws.cell(row=1, column=1, value=_INSTRUCTIONS_TEXT).alignment = LEFT_WRAP
    ws.row_dimensions[1].height = 360


def write_template(path: str | Path) -> Path:
    """生成空白录入模板。"""
    project_meta, scheme_meta = _build_enriched()

    wb = Workbook()
    # 默认第一张空白表删掉，换成"项目信息"
    default = wb.active
    wb.remove(default)

    _write_project_sheet(wb, project_meta)
    _write_scheme_sheet(wb, scheme_meta)
    _write_instructions_sheet(wb)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


# —— 导出（数据库 → xlsx）—— #


def _value_to_cell(value: Any) -> Any:
    """把 Python 值转成 xlsx 单元格字符串。

    dict / list 等结构化字段在 Excel 里存为可解析的中文表示，导入端按对应规则回解。
    """

    def _fmt_scalar(v: Any) -> str:
        if isinstance(v, float):
            # 避免 0.4 被写成 0.4000000000001
            return f"{v:.10g}"
        return str(v)

    if isinstance(value, dict):
        return ",".join(f"{k}: {_fmt_scalar(v)}" for k, v in value.items())
    if isinstance(value, list):
        if not value:
            return "[]"  # 与空单元格（未填写）区分，支持声明已核对无不规则项。
        return ",".join(_fmt_scalar(v) for v in value)
    return value


def _project_rows(meta: dict[str, Any], params: dict[str, Any]) -> list[list[Any]]:
    """把 ProjectParams 字典渲染成"项目信息"表的行内容（不含表头与分组标题）。"""
    rows: list[list[Any]] = []
    for _group, fields in _fields_by_group(meta):
        rows.append([f"【{_group}】", None, None, None, None])  # 分组标题占位
        for field_info in fields:
            value = params.get(field_info["name"])
            rows.append(
                [
                    field_info["label"],
                    _value_to_cell(value),
                    field_info.get("unit", "—"),
                    field_info.get("description", ""),
                    field_info["name"],
                ]
            )
    return rows


def _scheme_rows(
    meta: dict[str, Any], schemes: list[dict[str, Any]]
) -> tuple[list[list[Any]], list[str]]:
    """把多个方案的参数渲染成"方案参数"表的行内容。

    返回 ``(rows, scheme_names)``；``scheme_names`` 来自第一个方案分片。
    """
    names = [s["name"] for s in schemes]
    if len(names) > MAX_SCHEMES:
        # 多余的方案放在"方案参数_2"等附加表，本函数只生成第一张。
        names = names[:MAX_SCHEMES]
        schemes = schemes[:MAX_SCHEMES]

    # 行长度 = label + unit + MAX_SCHEMES 个方案 + hidden name = 1 + 1 + 6 + 1 = 9
    n_scheme_cols = len(schemes)

    rows: list[list[Any]] = []
    for _group, fields in _fields_by_group(meta):
        # 分组标题行：1 个 label + 1 + MAX_SCHEMES 个空 + 1 个 hidden = 9
        rows.append([f"【{_group}】"] + [None] * (1 + MAX_SCHEMES + 1))
        for field_info in fields:
            row = [field_info["label"], field_info.get("unit", "—")]
            for scheme in schemes:
                row.append(_value_to_cell(scheme["params"].get(field_info["name"])))
            # 填充未使用的方案列（保持行长度一致，便于正确写入列号）
            for _ in range(n_scheme_cols, MAX_SCHEMES):
                row.append(None)
            row.append(field_info["name"])
            rows.append(row)
    return rows, names


def write_export(
    path: str | Path,
    project_params: dict[str, Any],
    schemes: list[dict[str, Any]],
) -> Path:
    """把数据库里的项目 + 方案导出为 xlsx。

    ``schemes`` 每项形如 ``{"name": "高层A", "params": {...}}``。方案数大于
    :data:`MAX_SCHEMES` 时，溢出的方案写到"方案参数_2"补充表，并在文件里多保留一份模板。
    """
    project_meta, scheme_meta = _build_enriched()

    wb = Workbook()
    default = wb.active
    wb.remove(default)

    # 复用 _write_*_sheet 会覆盖空表，这里直接重写一份。
    _write_project_sheet(wb, project_meta)
    _write_scheme_sheet(wb, scheme_meta)
    _write_instructions_sheet(wb)

    # 覆写项目层数据
    proj_ws = wb[SHEET_PROJECT]
    for r_idx, row in enumerate(_project_rows(project_meta, project_params), start=2):
        for c_idx, value in enumerate(row, start=1):
            if value is not None:
                proj_ws.cell(row=r_idx, column=c_idx, value=value)

    # 覆写方案表数据
    scheme_ws = wb[SHEET_SCHEMES]
    scheme_rows, scheme_names = _scheme_rows(scheme_meta, schemes)
    for c_idx, name in enumerate(scheme_names, start=3):
        scheme_ws.cell(row=1, column=c_idx, value=name)
    for r_idx, row in enumerate(scheme_rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            if value is not None:
                scheme_ws.cell(row=r_idx, column=c_idx, value=value)

    # 额外方案溢出
    if len(schemes) > MAX_SCHEMES:
        extras = schemes[MAX_SCHEMES:]
        # 把多出来的方案均分到补充表，每张最多 MAX_SCHEMES 个。
        for sheet_idx, start in enumerate(range(0, len(extras), MAX_SCHEMES), start=2):
            chunk = extras[start : start + MAX_SCHEMES]
            ws_extra = wb.create_sheet(f"{SHEET_SCHEMES}_{sheet_idx}")
            _auto_width(ws_extra, [22, 8] + [18] * MAX_SCHEMES + [0])
            name_col_idx = 3 + MAX_SCHEMES
            ws_extra.column_dimensions[get_column_letter(name_col_idx)].hidden = True
            chunk_names = [f"方案{chr(ord('A') + i)}" for i in range(len(chunk))]
            headers = ["字段中文名", "单位"] + chunk_names + ["name"]
            _write_header_row(ws_extra, 1, headers)
            extra_rows, extra_names = _scheme_rows(scheme_meta, chunk)
            for c_idx, name in enumerate(extra_names, start=3):
                ws_extra.cell(row=1, column=c_idx, value=name)
            for r_idx, row in enumerate(extra_rows, start=2):
                for c_idx, value in enumerate(row, start=1):
                    if value is not None:
                        ws_extra.cell(row=r_idx, column=c_idx, value=value)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


# —— 解析 —— #


_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+(\.\d+)?$")


def _parse_number(value: Any, label: str) -> float:
    """把单元格值解析为 float。"""
    if isinstance(value, bool):
        raise ValueError(f"【{label}】应为数字，实际填了布尔值")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"【{label}】应为数字，实际为空")
        if _FLOAT.match(text):
            return float(text)
        if _INT.match(text):
            return float(text)
        raise ValueError(f"【{label}】应为数字，实际填了「{text}」")
    raise ValueError(f"【{label}】应为数字，实际类型为 {type(value).__name__}")


def _parse_integer(value: Any, label: str) -> int:
    f = _parse_number(value, label)
    if f != int(f):
        raise ValueError(f"【{label}】应为整数，实际填了 {f}")
    return int(f)


def _parse_ratio(value: Any, label: str) -> float:
    """0-1 比例字段。Excel 里 0-100 的整数会被解释为日期，需要先按字符串解析。"""
    if isinstance(value, bool):
        raise ValueError(f"【{label}】应为 0-1 的小数（如 0.82 表示 82%），实际填了布尔值")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"【{label}】应为 0-1 的小数，实际为空")
        # 防止 Excel 把 "82" 自动识别为日期（极少见但出现过）
        if _FLOAT.match(text):
            v = float(text)
        elif _INT.match(text):
            v = float(text)
        else:
            raise ValueError(
                f"【{label}】应为 0-1 的小数（如 0.82 表示 82%），实际填了「{text}」"
            )
    elif isinstance(value, (int, float)):
        v = float(value)
    else:
        raise ValueError(f"【{label}】类型不支持：{type(value).__name__}")
    if not 0 <= v <= 1:
        raise ValueError(
            f"【{label}】应在 0-1 之间（0.82 表示 82%），实际填了 {v}"
        )
    return v


def _parse_enum(value: Any, label: str, choices: Iterable[str]) -> str:
    choices_list = list(choices)
    if isinstance(value, str):
        text = value.strip()
        if text in choices_list:
            return text
        raise ValueError(
            f"【{label}】不是合法选项（可选：{', '.join(choices_list)}），实际填了「{text}」"
        )
    raise ValueError(f"【{label}】应为字符串，实际为 {type(value).__name__}")


def _parse_string(value: Any, label: str) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        # 数字 / 整数允许直接转字符串（防止"3"被记成 int）
        return str(value)
    raise ValueError(f"【{label}】应为文本，实际类型为 {type(value).__name__}")


def _parse_dict(value: Any, label: str, value_parser) -> dict[str, Any]:
    """解析 ``{label1: v1, label2: v2}`` 形式的单元格。

    ``value_parser`` 接受 ``(raw_str, key)`` 返回单个值。
    """
    if isinstance(value, dict):
        # openpyxl 不会自动把字符串解析为 dict；这条分支兜底。
        items = value.items()
        return {str(k): value_parser(v, str(k)) for k, v in items}
    if not isinstance(value, str):
        raise ValueError(f"【{label}】应为「键: 值」形式，实际为 {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"【{label}】应为「键: 值」形式，实际为空")
    out: dict[str, Any] = {}
    # 用最宽松的分隔符切
    chunks = re.split(r"[，,；;]", text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        # 找到第一个分隔符（中文 / 英文冒号）
        match = re.search(r"[：:]", chunk)
        if not match:
            raise ValueError(
                f"【{label}】中「{chunk}」缺少冒号，请写成「键: 值」"
            )
        key = chunk[: match.start()].strip()
        val_raw = chunk[match.end() :].strip()
        if not key:
            raise ValueError(f"【{label}】中「{chunk}」的键为空")
        out[key] = value_parser(val_raw, key)
    if not out:
        raise ValueError(f"【{label}】没有解析出任何键值对")
    return out


def _parse_list(value: Any, label: str) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if not isinstance(value, str):
        raise ValueError(f"【{label}】应为逗号分隔的列表，实际为 {type(value).__name__}")
    text = value.strip()
    if text == "[]":
        return []
    if not text:
        return []
    parts = re.split(r"[，,；;]", text)
    return [p.strip() for p in parts if p.strip()]


def _cell_value(cell: Cell) -> Any:
    """取单元格值，去掉多余空白但保留类型。"""
    v = cell.value
    if isinstance(v, str):
        return v.strip()
    return v


def _project_field_parser(
    project_meta: dict[str, Any], field_name: str, raw: Any
) -> Any:
    """按字段类型解析项目层单元格值。"""
    field_info = next(f for f in project_meta["fields"] if f["name"] == field_name)
    label = field_info["label"]
    typ = field_info["type"]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if typ == "number":
        if field_info.get("constraints", {}).get("maximum") == 1 and field_info.get(
            "constraints", {}
        ).get("minimum") == 0:
            return _parse_ratio(raw, label)
        return _parse_number(raw, label)
    if typ == "integer":
        return _parse_integer(raw, label)
    if typ == "string":
        if "enum" in field_info:
            return _parse_enum(raw, label, field_info["enum"])
        return _parse_string(raw, label)
    if typ.startswith("object<"):
        value_type = typ[len("object<") : -1]
        if value_type == "integer":
            return _parse_dict(raw, label, lambda v, _k: _parse_integer(v, label))
        if value_type == "number":
            return _parse_dict(raw, label, lambda v, _k: _parse_ratio(v, label))
        return _parse_dict(raw, label, lambda v, _k: _parse_string(v, label))
    raise ValueError(f"【{label}】字段类型 {typ} 暂未支持")


def _scheme_field_parser(
    scheme_meta: dict[str, Any], field_name: str, raw: Any
) -> Any:
    """按字段类型解析方案层单元格值。"""
    field_info = next(f for f in scheme_meta["fields"] if f["name"] == field_name)
    label = field_info["label"]
    typ = field_info["type"]
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if typ == "number":
        # 项目层的比例（density_max）有 constraints；方案层比例字段靠名字识别
        is_ratio = field_name in (
            "inner_area_ratio",
            "south_room_ratio",
            "window_floor_ratio",
            "std_floor_repeat",
            "prefab_ratio_est",
        )
        if is_ratio:
            return _parse_ratio(raw, label)
        return _parse_number(raw, label)
    if typ == "integer":
        return _parse_integer(raw, label)
    if typ == "string":
        if "enum" in field_info:
            return _parse_enum(raw, label, field_info["enum"])
        return _parse_string(raw, label)
    if typ.startswith("object<"):
        value_type = typ[len("object<") : -1]
        if value_type == "integer":
            return _parse_dict(raw, label, lambda v, _k: _parse_integer(v, label))
        if value_type == "number":
            return _parse_dict(raw, label, lambda v, _k: _parse_ratio(v, label))
        return _parse_dict(raw, label, lambda v, _k: _parse_string(v, label))
    if typ.startswith("array<"):
        return _parse_list(raw, label)
    raise ValueError(f"【{label}】字段类型 {typ} 暂未支持")


def _parse_project_sheet(
    ws: Worksheet, project_meta: dict[str, Any]
) -> tuple[dict[str, Any], list[ParseError]]:
    """解析"项目信息"工作表。"""
    errors: list[ParseError] = []
    params: dict[str, Any] = {}
    # 找隐藏列索引：扫描第 1 行的 name 列
    name_col = None
    for cell in ws[1]:
        if cell.value == "__name__":
            name_col = cell.column
            break
    if name_col is None:
        errors.append(
            ParseError(None, None, "项目信息", "找不到隐藏字段名（__name__），模板可能损坏")
        )
        return params, errors
    value_col = 2  # B 列
    for row in ws.iter_rows(min_row=2, values_only=False):
        name_cell = row[name_col - 1]
        name = name_cell.value
        if not name or not isinstance(name, str) or name == "__name__":
            # 分组标题行：第 1 列是【xxx】，hidden 列为空
            continue
        value_cell = row[value_col - 1]
        raw = _cell_value(value_cell)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        try:
            value = _project_field_parser(project_meta, name, raw)
        except ValueError as exc:
            label = next(
                (f["label"] for f in project_meta["fields"] if f["name"] == name),
                name,
            )
            errors.append(ParseError(None, name, label, str(exc)))
            continue
        if value is not None:
            params[name] = value
    return params, errors


def _parse_scheme_sheet(
    ws: Worksheet, scheme_meta: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[ParseError]]:
    """解析单个"方案参数"工作表（含 _2 后缀的溢出表）。"""
    errors: list[ParseError] = []
    schemes: list[dict[str, Any]] = []

    # 找隐藏列索引
    name_col = None
    for cell in ws[1]:
        if cell.value == "__name__":
            name_col = cell.column
            break
    if name_col is None:
        errors.append(
            ParseError(None, None, "方案参数", "找不到隐藏字段名（__name__），模板可能损坏")
        )
        return schemes, errors

    # 表头：第 3 列起为方案名
    n_scheme_cols = name_col - 3  # name_col 之前 = 单位 + 方案
    header_names: list[str] = []
    for c in range(3, 3 + n_scheme_cols):
        cell = ws.cell(row=1, column=c)
        v = cell.value
        if isinstance(v, str) and v.strip():
            header_names.append(v.strip())
        else:
            header_names.append(f"方案{chr(ord('A') + c - 3)}")

    # 先建空方案
    for name in header_names:
        schemes.append({"name": name, "params": {}})

    for row in ws.iter_rows(min_row=2, values_only=False):
        name_cell = row[name_col - 1]
        name = name_cell.value
        if not name or not isinstance(name, str) or name == "__name__":
            continue
        for s_idx in range(n_scheme_cols):
            scheme = schemes[s_idx]
            value_cell = row[2 + s_idx]  # C 列起 + 偏移
            raw = _cell_value(value_cell)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            try:
                value = _scheme_field_parser(scheme_meta, name, raw)
            except ValueError as exc:
                label = next(
                    (f["label"] for f in scheme_meta["fields"] if f["name"] == name),
                    name,
                )
                msg = str(exc)
                errors.append(ParseError(scheme["name"], name, label, msg))
                continue
            if value is not None:
                scheme["params"][name] = value

    # 跳过空的默认列：用户没填任何字段、且没重命名（仍是"方案C"等默认名）。
    # 但有错误的方案要保留，方便上层把错误暴露给用户。
    error_schemes = {e.scheme for e in errors if e.scheme is not None}
    default_names = [f"方案{chr(ord('A') + i)}" for i in range(n_scheme_cols)]
    schemes = [
        s for s in schemes
        if s["params"] or s["name"] in error_schemes or s["name"] not in default_names
    ]

    return schemes, errors


def parse_workbook(source: str | Path | bytes) -> ParseResult:
    """解析 xlsx 文件，返回项目参数、方案列表与全部错误。

    ``source`` 可以是路径，也可以是字节流（HTTP 上传场景）。
    """
    project_meta, scheme_meta = _build_enriched()

    if isinstance(source, (str, Path)):
        wb = load_workbook(source, data_only=True)
    else:
        import io

        wb = load_workbook(io.BytesIO(source), data_only=True)

    result = ParseResult()

    if SHEET_PROJECT not in wb.sheetnames:
        result.errors.append(
            ParseError(None, None, "项目信息", "找不到「项目信息」工作表")
        )
        return result
    result.project_params, proj_errors = _parse_project_sheet(
        wb[SHEET_PROJECT], project_meta
    )
    result.errors.extend(proj_errors)

    if SHEET_SCHEMES not in wb.sheetnames:
        result.errors.append(
            ParseError(None, None, "方案参数", "找不到「方案参数」工作表")
        )
        return result

    # 主表 + 溢出表
    main_schemes, main_errors = _parse_scheme_sheet(
        wb[SHEET_SCHEMES], scheme_meta
    )
    result.errors.extend(main_errors)
    result.schemes.extend(main_schemes)

    for sheet_name in wb.sheetnames:
        if sheet_name == SHEET_SCHEMES:
            continue
        if not sheet_name.startswith(f"{SHEET_SCHEMES}_"):
            continue
        extra_schemes, extra_errors = _parse_scheme_sheet(
            wb[sheet_name], scheme_meta
        )
        result.errors.extend(extra_errors)
        result.schemes.extend(extra_schemes)

    return result
