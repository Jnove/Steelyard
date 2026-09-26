"""xlsx 解析与往返测试。

验收点：
- 往返：JSON → 导出 xlsx → 导入，结果与原 JSON 一致。
- 错误文件：文字进数字格、比例填成 82、枚举值拼错、空方案列。
- 错误信息面向非程序员（"方案B 的【层高】应为数字，实际填了「三米」"）。
- 一次列出所有错误，不在第一个错误处停止。
- 隐藏字段名允许用户调整行顺序。
"""

from __future__ import annotations

from typing import Any

import pytest
from app.excel import parse_workbook, write_export, write_template
from openpyxl import Workbook


def _make_wb() -> Workbook:
    """构造一个三工作表齐全的最小 xlsx（从模板拷贝后改值用）。

    只复制单元格值与列宽/隐藏，不复制样式表，避免 openpyxl 跨 workbook
    复制 style 时索引错位。
    """
    import tempfile
    from pathlib import Path

    from openpyxl import load_workbook

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp_path = Path(f.name)
    write_template(tmp_path)
    wb = Workbook()
    wb.remove(wb.active)
    src = load_workbook(tmp_path)
    for sheet_name in src.sheetnames:
        src_ws = src[sheet_name]
        new_ws = wb.create_sheet(sheet_name)
        for row in src_ws.iter_rows(values_only=False):
            for cell in row:
                new_ws.cell(row=cell.row, column=cell.column, value=cell.value)
        # 复制列宽与隐藏
        for col_letter, dim in src_ws.column_dimensions.items():
            if dim.width is not None or dim.hidden:
                new_ws.column_dimensions[col_letter].width = dim.width
                new_ws.column_dimensions[col_letter].hidden = dim.hidden
        # data validation 用 type=formula1 字符串重新构造；完整复制 list dv 易坏。
    tmp_path.unlink()
    return wb


def _by_name(wb: Workbook, sheet: str) -> dict[str, Any]:
    """把工作表转成 ``{name: {col_idx: value}}``，便于按列写入。"""
    ws = wb[sheet]
    name_col = None
    for c in ws[1]:
        if c.value == "__name__":
            name_col = c.column
            break
    assert name_col is not None
    out: dict[str, Any] = {}
    for r in range(2, ws.max_row + 1):
        n = ws.cell(row=r, column=name_col).value
        if n and isinstance(n, str) and n != "__name__":
            out[n] = r
    return out


# —— 往返 —— #


class TestRoundTrip:
    def test_round_trip_via_export_then_parse(self, tmp_path) -> None:
        """JSON → export xlsx → parse → 与原 JSON 一致。"""
        project_params = {
            "site_area": 18000,
            "far_max": 2.2,
            "density_max": 0.28,
            "height_max": 54,
            "climate_zone": "夏热冬冷",
        }
        schemes = [
            {
                "name": "高层 A",
                "params": {
                    "structure_type": "框架-剪力墙",
                    "units": 120,
                    "unit_mix": {"两室": 60, "三室": 60},
                    "floor_height": 3.0,
                    "inner_area_ratio": 0.78,
                    "south_room_ratio": 0.65,
                    "window_floor_ratio": 0.25,
                    "window_wall_ratio": {"南": 0.40, "北": 0.25},
                    "elevators_per_unit": 2,
                    "gfa": 18000,
                    "footprint": 2400,
                    "buildings": 4,
                    "floors": 18,
                    "envelope_area": 9000,
                    "volume": 54000,
                    "std_floor_repeat": 0.82,
                    "component_types": 12,
                    "risk_features": ["大悬挑", "深基坑"],
                    "prefab_ratio_est": 0.35,
                },
            },
            {
                "name": "小高层 B",
                "params": {
                    "structure_type": "剪力墙",
                    "units": 80,
                    "floor_height": 3.0,
                    "inner_area_ratio": 0.80,
                    "gfa": 12000,
                    "floors": 12,
                    "std_floor_repeat": 0.90,
                    "prefab_ratio_est": 0.45,
                },
            },
        ]

        xlsx_path = write_export(tmp_path / "export.xlsx", project_params, schemes)
        result = parse_workbook(xlsx_path)
        assert result.errors == []
        assert result.project_params == project_params

        # scheme 名按 xlsx 列顺序，方案 A 在前 B 在后
        assert [s["name"] for s in result.schemes] == ["高层 A", "小高层 B"]
        assert result.schemes[0]["params"]["structure_type"] == "框架-剪力墙"
        assert result.schemes[0]["params"]["units"] == 120
        assert result.schemes[0]["params"]["unit_mix"] == {"两室": 60, "三室": 60}
        assert result.schemes[0]["params"]["inner_area_ratio"] == 0.78
        assert result.schemes[0]["params"]["window_wall_ratio"] == {"南": 0.40, "北": 0.25}
        assert result.schemes[0]["params"]["risk_features"] == ["大悬挑", "深基坑"]
        assert result.schemes[1]["params"]["prefab_ratio_est"] == 0.45

    def test_round_trip_through_template(self, tmp_path) -> None:
        """用户手工填模板 → 解析，应该拿到正确结果。"""
        wb = _make_wb()
        proj = _by_name(wb, "项目信息")
        # 写项目参数
        ws = wb["项目信息"]
        ws.cell(row=proj["site_area"], column=2, value=20000)
        ws.cell(row=proj["climate_zone"], column=2, value="夏热冬冷")

        schemes_ws = wb["方案参数"]
        scheme_idx = _by_name(wb, "方案参数")
        # 方案A 列
        schemes_ws.cell(row=1, column=3, value="高层 A")
        schemes_ws.cell(row=scheme_idx["structure_type"], column=3, value="剪力墙")
        schemes_ws.cell(row=scheme_idx["units"], column=3, value=120)
        schemes_ws.cell(row=scheme_idx["gfa"], column=3, value=15000)
        schemes_ws.cell(row=scheme_idx["floors"], column=3, value=18)
        schemes_ws.cell(row=scheme_idx["inner_area_ratio"], column=3, value=0.78)
        schemes_ws.cell(
            row=scheme_idx["risk_features"], column=3, value="大悬挑，深基坑"
        )

        path = tmp_path / "filled.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert result.errors == []
        assert result.project_params["site_area"] == 20000
        assert result.project_params["climate_zone"] == "夏热冬冷"
        assert len(result.schemes) == 1
        s = result.schemes[0]
        assert s["name"] == "高层 A"
        assert s["params"]["structure_type"] == "剪力墙"
        assert s["params"]["units"] == 120
        assert s["params"]["inner_area_ratio"] == 0.78
        assert s["params"]["risk_features"] == ["大悬挑", "深基坑"]


class TestRowReordering:
    def test_user_can_reorder_rows(self, tmp_path) -> None:
        """调整行顺序（隐藏列不变）后解析仍能识别。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")

        # 互换 structure_type 与 gfa 两行的 label（可见的字段中文名）
        ws.cell(row=idx["structure_type"], column=1, value="（已交换）总建筑面积")
        ws.cell(row=idx["gfa"], column=1, value="结构体系")
        # 隐藏列（field 名）保持不变；值按隐藏列对应的字段填
        # structure_type 行（label 改成了"总建筑面积"）：值是"剪力墙"
        ws.cell(row=idx["structure_type"], column=3, value="剪力墙")
        # gfa 行（label 改成了"结构体系"）：值是 15000
        ws.cell(row=idx["gfa"], column=3, value=15000)

        path = tmp_path / "reorder.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert result.errors == []
        # 但隐藏列没变，所以解析仍按字段名正确映射
        s = result.schemes[0]
        assert s["params"]["gfa"] == 15000
        assert s["params"]["structure_type"] == "剪力墙"


# —— 错误文件 —— #


class TestErrors:
    def test_text_in_number_field(self, tmp_path) -> None:
        """数字字段填了文字（"三米"）。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        ws.cell(row=idx["floor_height"], column=3, value="三米")

        path = tmp_path / "bad.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert any(
            "层高" in e.label and "三米" in e.message for e in result.errors
        ), result.errors

    def test_ratio_as_percentage_82(self, tmp_path) -> None:
        """比例字段填成 82，应明确提示。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        # Excel 会把 82 解释为日期；改用字符串避开自动转换
        ws.cell(row=idx["inner_area_ratio"], column=3, value="82")

        path = tmp_path / "bad.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        msgs = "\n".join(e.message for e in result.errors)
        assert "得房率" in msgs
        assert "0-1" in msgs or "小数" in msgs

    def test_enum_typo(self, tmp_path) -> None:
        """枚举值拼错（木结构）。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        ws.cell(row=idx["structure_type"], column=3, value="木结构")

        path = tmp_path / "bad.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert any(
            "结构体系" in e.label and "木结构" in e.message for e in result.errors
        ), result.errors

    def test_empty_scheme_columns_are_ignored(self, tmp_path) -> None:
        """方案A 留空应正常解析（不报错）。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        # 方案A 列（C 列）什么都不填；只在方案B 列（D 列）填
        ws.cell(row=1, column=4, value="方案 B")
        ws.cell(row=idx["gfa"], column=4, value=10000)

        path = tmp_path / "one.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert result.errors == []
        # 只生成一个方案（方案A 列空，跳过）
        assert len(result.schemes) == 1
        assert result.schemes[0]["name"] == "方案 B"
        assert result.schemes[0]["params"]["gfa"] == 10000

    def test_collects_all_errors_at_once(self, tmp_path) -> None:
        """一次列出所有错误，不在第一个错误处停止。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        # 同一行多个字段错
        ws.cell(row=idx["floor_height"], column=3, value="三米")
        ws.cell(row=idx["gfa"], column=3, value="一万八千")
        ws.cell(row=idx["structure_type"], column=3, value="木结构")
        # 比例字段
        ws.cell(row=idx["inner_area_ratio"], column=3, value="82")

        path = tmp_path / "many.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        # 4 个错误都被报告
        labels = [e.label for e in result.errors]
        assert "层高" in labels
        assert "总建筑面积" in labels
        assert "结构体系" in labels
        assert "得房率" in labels

    def test_error_message_names_scheme(self, tmp_path) -> None:
        """错误信息包含方案名（"方案B 的【层高】..."）。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        idx = _by_name(wb, "方案参数")
        # 重命名方案B 列
        ws.cell(row=1, column=4, value="高层 B")
        ws.cell(row=idx["floor_height"], column=4, value="三米")

        path = tmp_path / "named.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        match = next(e for e in result.errors if e.label == "层高")
        assert match.scheme == "高层 B"
        assert "三米" in match.message

    def test_blank_cell_is_not_an_error(self, tmp_path) -> None:
        """空单元格视为缺项，不报错。"""
        wb = _make_wb()
        path = tmp_path / "blank.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert result.errors == []


# —— 反向：用 ParseResult / parse_workbook 的直接覆盖 —— #


class TestEdgeCases:
    def test_missing_sheets_reports_error(self, tmp_path) -> None:
        """模板被破坏，缺工作表。"""
        wb = Workbook()
        wb.remove(wb.active)
        wb.create_sheet("项目信息")  # 缺 方案参数
        path = tmp_path / "broken.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        assert any("方案参数" in e.message for e in result.errors)

    def test_unknown_field_name_ignored(self, tmp_path) -> None:
        """模板里出现未知的英文字段名（用户改了不该改的列）应跳过。"""
        wb = _make_wb()
        ws = wb["方案参数"]
        # 把一行隐藏列改成未知字段名
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "结构体系":
                ws.cell(row=r, column=9, value="unknown_field")
                break
        path = tmp_path / "unknown.xlsx"
        wb.save(path)
        result = parse_workbook(path)
        # 不应报错；只是该行被忽略
        assert result.errors == []


@pytest.fixture
def parse_result_factory() -> Any:
    return parse_workbook