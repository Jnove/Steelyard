"""自定义内容（覆盖层）。

内建内容（``backend/app/models/params.py`` 与 ``rules/*.yaml``）仍走**构建期生成**，
CI 会校验生成产物同步；这里放的是**运行期**由使用者添加的内容，加载时与内建内容合并。
设计与取舍见 ``docs/design-custom-add.md``。

**铁律：覆盖层只能追加，不能覆盖内建内容**——不覆盖内建字段名、派生量名、规则 ID、
角色键；冲突的一律拒绝，并给出中文原因与改法。
"""

from __future__ import annotations

from app.custom.errors import CustomAddError, CustomProblem

__all__ = ["CustomAddError", "CustomProblem"]
