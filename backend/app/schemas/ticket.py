from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketCategory, TicketStatus


class TicketCreate(BaseModel):
    description: str = Field(min_length=10, max_length=5000)
    feature_module: str = Field(min_length=1, max_length=100)


class TicketAssign(BaseModel):
    assignee_id: int


class TicketStatusUpdate(BaseModel):
    status: TicketStatus
    content: str | None = Field(default=None, max_length=2000)


class TicketPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_no: str
    title: str
    description: str
    summary: str | None
    feature_module: str
    category: TicketCategory | None
    status: TicketStatus
    submitter_id: int
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

