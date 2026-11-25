from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TicketCategory, TicketStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="待智能整理")
    description: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_module: Mapped[str] = mapped_column(String(100))
    category: Mapped[TicketCategory | None] = mapped_column(
        Enum(TicketCategory), nullable=True, index=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.PENDING_ASSIGNMENT, index=True
    )
    submitter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    submitter = relationship("User", foreign_keys=[submitter_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    records = relationship(
        "TicketRecord", back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketRecord(Base):
    __tablename__ = "ticket_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(TicketStatus), nullable=True
    )
    to_status: Mapped[TicketStatus | None] = mapped_column(
        Enum(TicketStatus), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    ticket = relationship("Ticket", back_populates="records")
    operator = relationship("User")

