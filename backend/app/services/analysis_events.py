"""智能分析完成后的扩展点（留给 4 号检索、6 号统计、消息通知等模块接入）。

现在分析服务只做“整理 + 落库 + 回写工单”。相似检索、看板刷新、站内信这些
后续能力不应该反向修改分析服务内部，而是在这里注册一个回调即可。

用法（例如 4 号在 `app/services/similarity.py` 里）：

    from app.services.analysis_events import register_post_analysis_hook

    def index_ticket_for_search(db, ticket, view):
        # view.title / view.summary 就是整理后的文本，可直接用于 TF-IDF 建索引
        save_document(ticket.id, view.title, view.summary)

    register_post_analysis_hook(index_ticket_for_search)

约定：
- 回调在工单字段写回、事务提交之后执行，能读到最新的 ticket 数据；
- 单个回调抛异常只记 warning，不影响分析结果返回，也不回滚工单；
- 回调里可以做自己的事务，但不要修改 ticket 的关键字段（避免与人工修改冲突）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅用于类型提示，避免循环导入
    from sqlalchemy.orm import Session

    from app.models.ticket import Ticket
    from app.schemas.analysis import AnalysisView

logger = logging.getLogger(__name__)

PostAnalysisHook = Callable[["Session", "Ticket", "AnalysisView"], None]

_hooks: list[PostAnalysisHook] = []


def register_post_analysis_hook(hook: PostAnalysisHook) -> PostAnalysisHook:
    """注册回调；重复注册同一个函数只生效一次。"""

    if hook not in _hooks:
        _hooks.append(hook)
    return hook


def clear_post_analysis_hooks() -> None:
    """清空回调，测试用。"""

    _hooks.clear()


def emit_post_analysis(db: Session, ticket: Ticket, view: AnalysisView) -> None:
    """按注册顺序执行回调，任何异常都不得影响主流程。"""

    for hook in list(_hooks):
        try:
            hook(db, ticket, view)
        except Exception:  # noqa: BLE001 - 后置逻辑失败不能影响分析结果
            logger.warning(
                "分析后置回调失败：%s", getattr(hook, "__name__", repr(hook)), exc_info=True
            )
