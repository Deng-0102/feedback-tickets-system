from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import Role
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.analysis import AnalysisPreviewRequest, AnalysisView
from app.schemas.common import ApiResponse
from app.services.analysis_config import AnalysisConfigError, get_analysis_settings
from app.services.analysis_service import (
    analyse_ticket,
    latest_result,
    preview_suggestion,
    result_view,
)
from app.services.llm_client import AnalysisNotConfigured, ChatModel, build_chat_model

router = APIRouter()
preview_router = APIRouter()

RESULT_MESSAGES = {
    "SUCCESS": "智能整理完成，已写入工单，可人工修改",
    "DEGRADED": "智能整理完成，但置信度不高，请人工确认分类",
    "FAILED": "智能整理失败，已保留原始反馈，请人工填写分类",
}


def get_chat_model() -> ChatModel:
    """FastAPI 依赖：按 .env 配置构造模型；未配置时返回 503 而不是 500。"""

    try:
        return build_chat_model(get_analysis_settings())
    except AnalysisNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AnalysisConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"智能分析配置错误：{exc}"
        ) from exc


def _visible_ticket_or_404(db: Session, ticket_id: int, user: User) -> Ticket:
    """与工单接口一致的可见性规则：用户看自己的、处理人看分配给自己的、管理员看全部。"""

    ticket = db.get(Ticket, ticket_id)
    visible = ticket is not None and (
        user.role == Role.ADMIN
        or (user.role == Role.USER and ticket.submitter_id == user.id)
        or (user.role == Role.AGENT and ticket.assignee_id == user.id)
    )
    if not visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return ticket


@router.post("/{ticket_id}/analysis", response_model=ApiResponse[AnalysisView])
def analyse(
    ticket_id: int,
    force: bool = Query(default=False, description="是否忽略历史结果，重新调用模型"),
    apply: bool = Query(default=True, description="是否把整理结果写回工单"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    model: ChatModel = Depends(get_chat_model),
) -> ApiResponse[AnalysisView]:
    ticket = _visible_ticket_or_404(db, ticket_id, current_user)
    view = analyse_ticket(
        db,
        ticket,
        model=model,
        settings=get_analysis_settings(),
        operator=current_user,
        apply=apply,
        force=force,
    )
    return ApiResponse(message=RESULT_MESSAGES.get(view.status, "智能整理完成"), data=view)


@router.get("/{ticket_id}/analysis", response_model=ApiResponse[AnalysisView])
def get_analysis(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AnalysisView]:
    ticket = _visible_ticket_or_404(db, ticket_id, current_user)
    result = latest_result(db, ticket.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="该工单还没有智能分析结果"
        )
    return ApiResponse(data=result_view(result))


@preview_router.post("/preview", response_model=ApiResponse[AnalysisView])
def preview(
    payload: AnalysisPreviewRequest,
    _: User = Depends(get_current_user),
    model: ChatModel = Depends(get_chat_model),
) -> ApiResponse[AnalysisView]:
    """提交反馈前先看整理效果，不创建工单，供 5 号页面调用。"""

    view = preview_suggestion(
        model=model,
        settings=get_analysis_settings(),
        description=payload.description,
        feature_module=payload.feature_module,
    )
    return ApiResponse(message=RESULT_MESSAGES.get(view.status, "预览完成"), data=view)
