from __future__ import annotations

from fastapi import HTTPException, status

from app.models.enums import Role, TicketStatus

ALLOWED_TRANSITIONS: dict[TicketStatus, dict[Role, set[TicketStatus]]] = {
    TicketStatus.PENDING_ASSIGNMENT: {
        Role.ADMIN: {TicketStatus.PENDING},
    },
    TicketStatus.PENDING: {
        Role.AGENT: {TicketStatus.IN_PROGRESS},
        Role.ADMIN: {TicketStatus.IN_PROGRESS},
    },
    TicketStatus.IN_PROGRESS: {
        Role.AGENT: {TicketStatus.RESOLVED},
        Role.ADMIN: {TicketStatus.RESOLVED},
    },
    TicketStatus.RESOLVED: {
        Role.USER: {TicketStatus.CLOSED, TicketStatus.REOPENED},
        Role.ADMIN: {TicketStatus.CLOSED, TicketStatus.REOPENED},
    },
    TicketStatus.REOPENED: {
        Role.AGENT: {TicketStatus.IN_PROGRESS},
        Role.ADMIN: {TicketStatus.IN_PROGRESS},
    },
    TicketStatus.CLOSED: {},
}


def ensure_transition_allowed(
    current: TicketStatus, target: TicketStatus, role: Role
) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, {}).get(role, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"不允许由 {current.value} 转换为 {target.value}",
        )

