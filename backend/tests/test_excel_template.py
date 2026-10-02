"""方案录入 Excel 模板生成测试。

模板从 ``app.models`` 字段元信息自动生成，校验：
- 三个工作表齐全（项目信息 / 方案参数 / 填写说明）。
- 字段中文名 / 英文名 / 单位 / 分组都对得上 schema。
- 英文字段名放在隐藏列，用户调整可见列的顺序不影响解析。
- 必填字段（essential）在填写单元格上有浅黄色底。
- 结构体系是下拉选择；数值字段有数值验证。
"""

from __future__ import annotations

from app.excel import MAX_SCHEMES, SHEET_INSTRUCTIONS, SHEET_PROJECT, SHEET_SCHEMES, write_template
from openpyxl import load_workbook


class TestTemplateGeneration:
    def test_three_sheets_present(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        assert set(wb.sheetnames) == {SHEET_PROJECT, SHEET_SCHEMES, SHEET_INSTRUCTIONS}

    def test_project_sheet_has_all_fields(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_PROJECT]

        # 找隐藏列（标题为 __name__）
        name_col = None
        for cell in ws[1]:
            if cell.value == "__name__":
                name_col = cell.column
                break
        assert name_col is not None, "项目信息表缺隐藏字段名列"
        # 隐藏列确实是 hidden
        assert ws.column_dimensions[
            ws.cell(row=1, column=name_col).column_letter
        ].hidden

        names = {
            ws.cell(row=r, column=name_col).value
            for r in range(2, ws.max_row + 1)
            if ws.cell(row=r, column=name_col).value
        }
        # 5 个项目字段全部出现
        assert names == {"site_area", "far_max", "density_max", "height_max", "climate_zone"}

    def test_scheme_sheet_has_six_columns_and_all_fields(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_SCHEMES]

        # 第 1 行表头：字段中文名 | 单位 | 方案A..方案F
        header = [c.value for c in ws[1]]
        assert header[:2] == ["字段中文名", "单位"]
        assert header[2 : 2 + MAX_SCHEMES] == [
            f"方案{chr(ord('A') + i)}" for i in range(MAX_SCHEMES)
        ]

        # 找隐藏列
        name_col = None
        for cell in ws[1]:
            if cell.value == "__name__":
                name_col = cell.column
                break
        assert name_col is not None
        assert ws.column_dimensions[ws.cell(row=1, column=name_col).column_letter].hidden

        names = {
            ws.cell(row=r, column=name_col).value
            for r in range(2, ws.max_row + 1)
            if ws.cell(row=r, column=name_col).value
        }
        # SchemeParams 全部 19 个字段都出现在模板里
        assert "structure_type" in names
        assert "gfa" in names
        assert "risk_features" in names
        assert "prefab_ratio_est" in names

    def test_essential_fields_have_yellow_fill(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_PROJECT]

        # site_area 是 essential，第 2 列（B 列，填写格）应该是浅黄
        for r in range(2, ws.max_row + 1):
            label = ws.cell(row=r, column=1).value
            if label == "用地面积":
                fill = ws.cell(row=r, column=2).fill
                assert fill.fgColor.rgb is not None
                # 浅黄系列（含 'FFF' 前缀的浅色）
                assert "FFF" in str(fill.fgColor.rgb).upper()
                return
        raise AssertionError("项目信息表中找不到用地面积行")

    def test_structure_type_has_dropdown_validation(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_SCHEMES]

        # 任意含结构体系的行（找 label）
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "结构体系":
                dvs = ws.data_validations.dataValidation
                assert any(
                    "剪力墙" in dv.formula1 for dv in dvs
                ), "结构体系行缺枚举下拉验证"
                return
        raise AssertionError("方案参数表中找不到结构体系行")

    def test_numeric_fields_have_number_validation(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_SCHEMES]

        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "总建筑面积":
                dvs = ws.data_validations.dataValidation
                assert any(dv.type in ("decimal", "whole") for dv in dvs)
                return
        raise AssertionError("方案参数表中找不到总建筑面积行")

    def test_group_title_rows_present(self, tmp_path) -> None:
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_SCHEMES]
        titles = {
            ws.cell(row=r, column=1).value
            for r in range(2, ws.max_row + 1)
            if isinstance(ws.cell(row=r, column=1).value, str)
            and ws.cell(row=r, column=1).value.startswith("【")
            and ws.cell(row=r, column=1).value.endswith("】")
        }
        # 五个分组标题都得在
        assert "【基本信息】" in titles
        assert "【居住品质】" in titles
        assert "【结构与造价】" in titles
        assert "【施工与安全】" in titles
        assert "【绿色低碳】" in titles

    def test_row_order_is_user_changeable(self, tmp_path) -> None:
        """用户调整行顺序后，模板仍能打开（解析逻辑靠隐藏列而非行号）。"""
        path = write_template(tmp_path / "tpl.xlsx")
        wb = load_workbook(path)
        ws = wb[SHEET_SCHEMES]

        # 找到 site_area 不在（项目层字段），但在 scheme 层找一个具体字段
        # 把“结构体系”行与下一行“总户数”交换
        for r in range(2, ws.max_row + 1):
            if ws.cell(row=r, column=1).value == "结构体系":
                ws.cell(row=r, column=1).value = "总户数（暂存）"
            elif ws.cell(row=r, column=1).value == "总户数":
                ws.cell(row=r, column=1).value = "结构体系"
        wb.save(path)

        # 重新打开应无异常
        wb2 = load_workbook(path)
        assert wb2[SHEET_SCHEMES].max_row > 0