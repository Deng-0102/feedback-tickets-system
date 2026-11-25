from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import TicketCategory

AnalysisStatus = Literal["SUCCESS", "DEGRADED", "FAILED"]


class AnalysisSuggestion(BaseModel):
    """模型输出经校验、归一化后的结构。"""

    title: str
    category: TicketCategory | None
    summary: str | None
    keywords: list[str] = Field(default_factory=list)
    confidence: float | None = None
    reason: str | None = None


class AnalysisPreviewRequest(BaseModel):
    description: str = Field(min_length=10, max_length=5000)
    feature_module: str = Field(min_length=1, max_length=100)


class AnalysisView(BaseModel):
    """智能分析结果的统一返回结构，预览接口与工单分析接口共用。"""

    ticket_id: int | None = None
    result_id: int | None = None
    status: AnalysisStatus
    title: str
    category: TicketCategory | None
    category_label: str | None = None
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    confidence: float | None = None
    reason: str | None = None
    model_name: str
    prompt_version: str
    needs_manual_review: bool
    fallback_used: bool = False
    applied: bool = False
    cached: bool = False
    error: str | None = None
    elapsed_ms: int = 0
