from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TicketCategory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisResult(Base):
    """保留模型原始建议，人工确认结果仍写入 Ticket。"""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    generated_title: Mapped[str] = mapped_column(String(200))
    suggested_category: Mapped[TicketCategory] = mapped_column(Enum(TicketCategory))
    generated_summary: Mapped[str] = mapped_column(Text)
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    ticket = relationship("Ticket")

