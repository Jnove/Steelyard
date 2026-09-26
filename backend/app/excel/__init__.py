"""Excel 模板生成与解析。

提供：

- :func:`write_template` 生成空白录入模板（含三个工作表、数据有效性、隐藏英文列）。
- :func:`write_export` 把数据库里的项目 / 方案导出为同格式 xlsx，方便用户改后再导入。
- :func:`parse_workbook` 解析 xlsx，得到 ``ParseResult``；CLI 与 HTTP 接口共用。

设计要点：

- 英文字段名放在隐藏列，导入时按它对应；用户调整行顺序不影响解析。
- 错误信息面向非程序员（"方案B 的【层高】应为数字，实际填了'三米'"），
  一次列出所有错误，不在第一个错误处停止。
- 比例字段（0-1）单独走小数验证，避免用户填成 82 时 Excel 自动当日期。
- ``ParseResult.errors`` 仅用于展示；上层决定整文件拒绝还是 --allow-partial。
"""

from app.excel.io import (
    MAX_SCHEMES,
    SHEET_INSTRUCTIONS,
    SHEET_PROJECT,
    SHEET_SCHEMES,
    ParseError,
    ParseResult,
    parse_workbook,
    write_export,
    write_template,
)

__all__ = [
    "MAX_SCHEMES",
    "SHEET_INSTRUCTIONS",
    "SHEET_PROJECT",
    "SHEET_SCHEMES",
    "ParseError",
    "ParseResult",
    "parse_workbook",
    "write_export",
    "write_template",
]