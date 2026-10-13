"""覆盖层的变更留痕（审计）。

**为什么单独一张表**：自定义内容是运行期加的草稿，它不在 git 里、不经过 CI，
所以"谁在什么时候加了什么、又删了什么"必须自己记下来。报告与界面都要能回答
"这个字段/规则/模板是哪来的"——这既是复核依据，也是这套覆盖层能被信任的前提。

**三条纪律**：

1. **追加写**：只提供 :func:`record` 与 :func:`list_entries`，
   没有修改与删除接口——留痕能被改就失去意义；
2. **与业务同事务**：``record`` 只 ``add`` + ``flush``，**不 commit**，
   由调用方那次写操作一起提交。于是"改成功但没留痕"或"留痕了但没改成功"都不会发生；
3. **操作者标识是占位实现**：当前取自可选的 ``X-Operator`` 头，接入登录后替换成真实身份。
   头可以被伪造，所以生产环境**写接口本身是关的**（``APP_ENV != dev`` 一律 403），
   这个标识用于开发环境内的自查与演示，不作为权限判据。
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from sqlmodel import Session, col, select

from app.custom.models import CustomAudit

__all__ = [
    "ACTIONS",
    "KINDS",
    "OPERATOR_ANONYMOUS",
    "OPERATOR_MAX_LENGTH",
    "KIND_LABELS",
    "list_entries",
    "normalize_operator",
    "record",
]

#: 允许的动作。加新动作时要同时想清楚"它是否可逆"。
ACTIONS: tuple[str, ...] = ("create", "delete")

#: 允许的对象类别，与四张覆盖层表一一对应。
KINDS: tuple[str, ...] = ("option", "template", "rule", "field")

#: 类别的中文名，给界面与报告直接用，免得各处再拼一遍。
KIND_LABELS: dict[str, str] = {
    "option": "自定义枚举选项",
    "template": "自定义角色权重模板",
    "rule": "自定义规则",
    "field": "自定义字段",
}

#: 没带操作者时用它。**不写 None**：留痕里的空值最难解释。
OPERATOR_ANONYMOUS = "anonymous"

#: 操作者标识长度上限：防止有人把整段文本塞进头里。
OPERATOR_MAX_LENGTH = 64

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_operator(raw: str | None) -> str:
    """把 ``X-Operator`` 头归一成一个可留痕的短标识。

    - **百分号编码先解回 UTF-8**：HTTP 头按规范只能是 ASCII（httpx 直接拒绝非 ASCII 头），
      所以中文名要由客户端编码后传（浏览器里 ``encodeURIComponent('张三')`` 即可）。
      不含 ``%`` 的纯 ASCII 标识（工号、拼音）原样通过；
      所以推荐直接用**工号**这类 ASCII 标识，中文名则用百分号编码。
    - 去掉首尾空白与**控制字符**（换行、制表符等塞进日志会破坏可读性）；
    - 空白折叠成单个空格（"张三  土木" → "张三 土木"）；
    - 超长截断（见 :data:`OPERATOR_MAX_LENGTH`）；
    - 空值统一成 :data:`OPERATOR_ANONYMOUS`。

    这样做不是为了安全（头本身可以伪造），而是为了让留痕**始终可读、可比对**。
    """
    if raw is None:
        return OPERATOR_ANONYMOUS
    text = unquote(raw, encoding="utf-8", errors="replace") if "%" in raw else raw
    text = _CONTROL_CHARS.sub(" ", text)
    text = " ".join(text.split())
    if not text:
        return OPERATOR_ANONYMOUS
    return text[:OPERATOR_MAX_LENGTH]


def record(
    session: Session,
    *,
    operator: str | None,
    action: str,
    kind: str,
    target: str,
    summary: str = "",
    detail: dict[str, object] | None = None,
) -> CustomAudit:
    """记一条留痕。

    ``session`` 由调用方负责提交——与业务写操作同事务（见模块文档的纪律 2）。

    Raises:
        ValueError: 动作或类别不在白名单里。宁可当场炸，也不要写进一条
            "看起来像留痕、其实没人认识"的记录。
    """
    if action not in ACTIONS:
        raise ValueError(f"未知的审计动作 {action!r}，允许：{', '.join(ACTIONS)}")
    if kind not in KINDS:
        raise ValueError(f"未知的审计类别 {kind!r}，允许：{', '.join(KINDS)}")
    entry = CustomAudit(
        operator=normalize_operator(operator),
        action=action,
        kind=kind,
        target=target,
        summary=summary,
        detail=dict(detail or {}),
    )
    session.add(entry)
    session.flush()
    return entry


def list_entries(session: Session, *, limit: int = 100) -> list[CustomAudit]:
    """最近的留痕，**新的在前**。"""
    safe_limit = max(1, min(int(limit), 500))
    statement = (
        select(CustomAudit)
        .order_by(col(CustomAudit.at).desc(), col(CustomAudit.id).desc())
        .limit(safe_limit)
    )
    return list(session.exec(statement).all())
