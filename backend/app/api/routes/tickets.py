from __future__ import annotations

from datetime import datetime, timezone
from secrets import token_hex

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import Role, TicketStatus
from app.models.ticket import Ticket, TicketRecord
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.ticket import (
    TicketAssign,
    TicketCreate,
    TicketPublic,
    TicketStatusUpdate,
)
from app.services.ticket_workflow import ensure_transition_allowed

router = APIRouter()


def _ticket_no() -> str:
    return f"TK{datetime.now(timezone.utc):%Y%m%d%H%M%S}{token_hex(8).upper()}"


def _visible_ticket_or_404(db: Session, ticket_id: int, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    visible = ticket is not None and (
        user.role == Role.ADMIN
        or (user.role == Role.USER and ticket.submitter_id == user.id)
        or (user.role == Role.AGENT and ticket.assignee_id == user.id)
    )
    if not visible:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return ticket


@router.post("", response_model=ApiResponse[TicketPublic], status_code=201)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(require_roles(Role.USER, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> ApiResponse[TicketPublic]:
    ticket = Ticket(
        ticket_no=_ticket_no(),
        description=payload.description,
        feature_module=payload.feature_module,
        submitter_id=current_user.id,
    )
    db.add(ticket)
    db.flush()
    db.add(
        TicketRecord(
            ticket_id=ticket.id,
            operator_id=current_user.id,
            action="CREATE",
            to_status=TicketStatus.PENDING_ASSIGNMENT,
        )
    )
    db.commit()
    db.refresh(ticket)
    return ApiResponse(message="反馈提交成功", data=TicketPublic.model_validate(ticket))


@router.get("", response_model=ApiResponse[list[TicketPublic]])
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[TicketPublic]]:
    statement = select(Ticket)
    if current_user.role == Role.USER:
        statement = statement.where(Ticket.submitter_id == current_user.id)
    elif current_user.role == Role.AGENT:
        statement = statement.where(Ticket.assignee_id == current_user.id)
    tickets = db.scalars(statement.order_by(Ticket.created_at.desc())).all()
    return ApiResponse(data=[TicketPublic.model_validate(item) for item in tickets])


@router.get("/{ticket_id}", response_model=ApiResponse[TicketPublic])
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TicketPublic]:
    ticket = _visible_ticket_or_404(db, ticket_id, current_user)
    return ApiResponse(data=TicketPublic.model_validate(ticket))


@router.patch("/{ticket_id}/assign", response_model=ApiResponse[TicketPublic])
def assign_ticket(
    ticket_id: int,
    payload: TicketAssign,
    admin: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> ApiResponse[TicketPublic]:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    assignee = db.get(User, payload.assignee_id)
    if assignee is None or not assignee.is_active or assignee.role != Role.AGENT:
        raise HTTPException(status_code=400, detail="负责人必须是有效的处理人员")
    previous = ticket.status
    if ticket.status == TicketStatus.PENDING_ASSIGNMENT:
        ensure_transition_allowed(previous, TicketStatus.PENDING, admin.role)
        ticket.status = TicketStatus.PENDING
    ticket.assignee_id = assignee.id
    db.add(
        TicketRecord(
            ticket_id=ticket.id,
            operator_id=admin.id,
            action="ASSIGN",
            content=f"分配给 {assignee.display_name}",
            from_status=previous,
            to_status=ticket.status,
        )
    )
    db.commit()
    db.refresh(ticket)
    return ApiResponse(message="分配成功", data=TicketPublic.model_validate(ticket))


@router.patch("/{ticket_id}/status", response_model=ApiResponse[TicketPublic])
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[TicketPublic]:
    ticket = _visible_ticket_or_404(db, ticket_id, current_user)
    if ticket.status == TicketStatus.PENDING_ASSIGNMENT and payload.status == TicketStatus.PENDING:
        raise HTTPException(status_code=409, detail="请通过分配接口指定负责人")

    previous = ticket.status
    ensure_transition_allowed(previous, payload.status, current_user.role)
    ticket.status = payload.status
    now = datetime.now(timezone.utc)
    if payload.status == TicketStatus.RESOLVED:
        ticket.resolved_at = now
    elif payload.status == TicketStatus.CLOSED:
        ticket.closed_at = now
    elif payload.status == TicketStatus.REOPENED:
        ticket.resolved_at = None

    db.add(
        TicketRecord(
            ticket_id=ticket.id,
            operator_id=current_user.id,
            action="STATUS_CHANGE",
            content=payload.content,
            from_status=previous,
            to_status=payload.status,
        )
    )
    db.commit()
    db.refresh(ticket)
    return ApiResponse(message="状态更新成功", data=TicketPublic.model_validate(ticket))

