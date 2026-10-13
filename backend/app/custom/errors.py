"""自定义内容的统一错误类型。

``CustomProblem`` 沿用 ``check_rules`` 与引擎加载器的措辞习惯：``message`` 说清哪里不对，
``fix`` 说清怎么改。两者都是中文，前端可以直接展示，不必自己翻译一遍。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomProblem:
    """一条可展示的问题。"""

    code: str
    message: str
    fix: str = ""


class CustomAddError(ValueError):
    """自定义内容不合法（字段不允许扩展、选项重复、模板校验不过等）。

    Attributes:
        problems: 全部问题；界面应逐条展示 ``message`` 与 ``fix``。
    """

    def __init__(self, problems: list[CustomProblem]) -> None:
        self.problems = problems
        super().__init__("；".join(p.message for p in problems))
