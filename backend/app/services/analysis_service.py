"""智能分析核心服务：调用模型 → 校验结构化输出 → 写库 → 更新工单 → 失败降级。

分层约定（对应报告 4.4 节）：
- 路由层只做权限、参数和响应封装，不写提示词与解析逻辑；
- 本模块负责“模型输出不可信”这件事：截断、归一化、分类别名映射、置信度判定；
- 任何模型异常都不得抛出到工单主流程，失败时保留原始反馈并写入处理记录。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import AnalysisResult
from app.models.enums import TicketCategory
from app.models.ticket import Ticket, TicketRecord
from app.models.user import User
from app.schemas.analysis import AnalysisSuggestion, AnalysisView
from app.services.analysis_config import AnalysisSettings
from app.services.analysis_prompts import (
    CATEGORY_GUIDE,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.llm_client import ChatModel, LLMCallError

MAX_TITLE_CHARS = 40
MAX_SUMMARY_CHARS = 200
MAX_KEYWORDS = 6
MAX_KEYWORD_CHARS = 20
CONFIDENCE_THRESHOLD = 0.6

CATEGORY_LABELS: dict[str, str] = {
    code: str(item["label"]) for code, item in CATEGORY_GUIDE.items()
}

# 模型可能返回中文名、大小写混写或近义词，这里统一映射到固定枚举。
CATEGORY_ALIASES: dict[str, str] = {}
for _code, _label in CATEGORY_LABELS.items():
    CATEGORY_ALIASES[_code] = _code
    CATEGORY_ALIASES[_label] = _code
CATEGORY_ALIASES.update(
    {
        "ACCOUNT": "ACCOUNT_LOGIN",
        "LOGIN": "ACCOUNT_LOGIN",
        "登录": "ACCOUNT_LOGIN",
        "账号问题": "ACCOUNT_LOGIN",
        "登录问题": "ACCOUNT_LOGIN",
        "BUG": "FUNCTION_ERROR",
        "ERROR": "FUNCTION_ERROR",
        "故障": "FUNCTION_ERROR",
        "功能bug": "FUNCTION_ERROR",
        "性能": "PERFORMANCE",
        "卡顿": "PERFORMANCE",
        "咨询": "USAGE_CONSULTATION",
        "使用方法": "USAGE_CONSULTATION",
        "建议": "FEATURE_SUGGESTION",
        "需求": "FEATURE_SUGGESTION",
        "新功能": "FEATURE_SUGGESTION",
    }
)

_WHITESPACE = re.compile(r"\s+")
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class SuggestionParseError(ValueError):
    """模型文本无法解析为约定的 JSON 结构。"""


@dataclass(slots=True)
class RunResult:
    status: str
    suggestion: AnalysisSuggestion
    error: str | None
    elapsed_ms: int
    fallback_used: bool
    needs_manual_review: bool
    raw_text: str = ""
    issues: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _fallback_title(description: str, feature_module: str) -> str:
    """模型失败时的兜底标题：只截取用户原话，不添加推测内容。"""

    first_sentence = re.split(r"[。！？!?\n]", description.strip(), maxsplit=1)[0]
    candidate = _clean(first_sentence) or _clean(description)
    if not candidate:
        candidate = f"{feature_module or '产品'}问题反馈"
    return candidate[:20]


def extract_json_object(text: str) -> dict:
    """从模型返回文本中提取第一个完整的 JSON 对象。

    兼容三种情况：纯 JSON、带 ```json 代码块、前后夹带解释文字。
    """

    candidate = text.strip()
    fenced = _FENCE.search(candidate)
    if fenced:
        candidate = fenced.group(1).strip()

    start = candidate.find("{")
    if start == -1:
        raise SuggestionParseError("模型输出中没有 JSON 对象")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(candidate)):
        char = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                chunk = candidate[start : index + 1]
                try:
                    data = json.loads(chunk)
                except json.JSONDecodeError as exc:
                    raise SuggestionParseError(f"JSON 解析失败：{exc.msg}") from exc
                if not isinstance(data, dict):
                    raise SuggestionParseError("JSON 顶层必须是对象")
                return data

    raise SuggestionParseError("JSON 括号不完整")


def normalise_suggestion(data: dict) -> tuple[AnalysisSuggestion, list[str]]:
    """把模型返回的字典收敛成可入库、可展示的结构，并记录被修正的问题。"""

    issues: list[str] = []

    title = _clean(str(data.get("title") or ""))
    if not title:
        issues.append("缺少标题")
    if len(title) > MAX_TITLE_CHARS:
        title = title[:MAX_TITLE_CHARS]
        issues.append("标题超长已截断")

    summary_raw = _clean(str(data.get("summary") or ""))
    summary: str | None = summary_raw or None
    if summary and len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS]
        issues.append("摘要超长已截断")

    category_raw = _clean(str(data.get("category") or "")).upper()
    category_code = CATEGORY_ALIASES.get(category_raw) or CATEGORY_ALIASES.get(
        _clean(str(data.get("category") or ""))
    )
    category: TicketCategory | None = None
    if category_code:
        category = TicketCategory(category_code)
        if category_raw != category.value:
            issues.append(f"分类已归一化：{category_raw} -> {category.value}")
    else:
        issues.append(f"分类不合法：{category_raw or '空'}")

    keywords: list[str] = []
    raw_keywords = data.get("keywords") or []
    if isinstance(raw_keywords, str):
        raw_keywords = re.split(r"[,，、;；]", raw_keywords)
    if isinstance(raw_keywords, list):
        for item in raw_keywords:
            word = _clean(str(item))[:MAX_KEYWORD_CHARS]
            if word and word not in keywords:
                keywords.append(word)
    keywords = keywords[:MAX_KEYWORDS]

    confidence: float | None = None
    raw_confidence = data.get("confidence")
    if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool):
        confidence = min(max(float(raw_confidence), 0.0), 1.0)
    elif isinstance(raw_confidence, str):
        try:
            confidence = min(max(float(raw_confidence.strip()), 0.0), 1.0)
        except ValueError:
            issues.append("置信度不是数字")

    reason = _clean(str(data.get("reason") or ""))[:60] or None

    suggestion = AnalysisSuggestion(
        title=title,
        category=category,
        summary=summary,
        keywords=keywords,
        confidence=confidence,
        reason=reason,
    )
    return suggestion, issues


def _fallback_suggestion(description: str, feature_module: str) -> AnalysisSuggestion:
    return AnalysisSuggestion(
        title=_fallback_title(description, feature_module),
        category=None,
        summary=None,
        keywords=[],
        confidence=None,
        reason=None,
    )


def run_analysis(
    model: ChatModel,
    settings: AnalysisSettings,
    description: str,
    feature_module: str,
) -> RunResult:
    """执行一次“调用 + 解析 + 判定”，不接触数据库，便于单测和预览接口复用。"""

    started = time.perf_counter()
    try:
        raw_text = model.complete(
            SYSTEM_PROMPT,
            build_user_prompt(description, feature_module, settings.max_input_chars),
        )
    except LLMCallError as exc:
        return RunResult(
            status="FAILED",
            suggestion=_fallback_suggestion(description, feature_module),
            error=f"{exc.kind}: {exc.message}",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            fallback_used=True,
            needs_manual_review=True,
        )
    except Exception as exc:  # 未预期异常同样不得影响工单主流程
        return RunResult(
            status="FAILED",
            suggestion=_fallback_suggestion(description, feature_module),
            error=f"UNEXPECTED: {type(exc).__name__}",
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            fallback_used=True,
            needs_manual_review=True,
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        data = extract_json_object(raw_text)
    except SuggestionParseError as exc:
        return RunResult(
            status="FAILED",
            suggestion=_fallback_suggestion(description, feature_module),
            error=f"BAD_FORMAT: {exc}",
            elapsed_ms=elapsed_ms,
            fallback_used=True,
            needs_manual_review=True,
            raw_text=raw_text[:2000],
        )

    suggestion, issues = normalise_suggestion(data)
    if not suggestion.title:
        suggestion.title = _fallback_title(description, feature_module)
        issues.append("标题为空已用原话兜底")

    # 分类不合法意味着无法可靠入库，按失败处理，交人工选择分类。
    if suggestion.category is None:
        return RunResult(
            status="FAILED",
            suggestion=suggestion,
            error=f"BAD_FORMAT: {'；'.join(issues) or '分类缺失'}",
            elapsed_ms=elapsed_ms,
            fallback_used=False,
            needs_manual_review=True,
            raw_text=raw_text[:2000],
            issues=issues,
        )

    confidence = suggestion.confidence
    degraded = (
        confidence is None
        or confidence < CONFIDENCE_THRESHOLD
        or any(issue.startswith(("标题超长", "摘要超长", "分类已归一化")) for issue in issues)
    )
    return RunResult(
        status="DEGRADED" if degraded else "SUCCESS",
        suggestion=suggestion,
        error=None,
        elapsed_ms=elapsed_ms,
        fallback_used=False,
        needs_manual_review=degraded,
        raw_text=raw_text[:2000],
        issues=issues,
    )


def _envelope(run: RunResult, provider: str, model_name: str) -> str:
    return json.dumps(
        {
            "status": run.status,
            "prompt_version": PROMPT_VERSION,
            "provider": provider,
            "model": model_name,
            "issues": run.issues,
            "elapsed_ms": run.elapsed_ms,
            "raw_text": run.raw_text,
        },
        ensure_ascii=False,
    )


def _read_envelope(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def latest_result(db: Session, ticket_id: int) -> AnalysisResult | None:
    statement = (
        select(AnalysisResult)
        .where(AnalysisResult.ticket_id == ticket_id)
        .order_by(AnalysisResult.id.desc())
        .limit(1)
    )
    return db.scalars(statement).first()


def _read_keywords(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [str(item) for item in data if str(item).strip()] if isinstance(data, list) else []


def result_view(result: AnalysisResult, *, cached: bool = False, applied: bool = False) -> AnalysisView:
    envelope = _read_envelope(result.raw_response)
    status = str(envelope.get("status") or "SUCCESS")
    if status not in ("SUCCESS", "DEGRADED", "FAILED"):
        status = "SUCCESS"
    return AnalysisView(
        ticket_id=result.ticket_id,
        result_id=result.id,
        status=status,  # type: ignore[arg-type]
        title=result.generated_title,
        category=result.suggested_category,
        category_label=CATEGORY_LABELS.get(result.suggested_category.value)
        if result.suggested_category
        else None,
        summary=result.generated_summary or None,
        keywords=_read_keywords(result.keywords_json),
        confidence=result.confidence,
        model_name=result.model_name or "unknown",
        prompt_version=str(envelope.get("prompt_version") or PROMPT_VERSION),
        needs_manual_review=status != "SUCCESS" or (result.confidence or 0) < CONFIDENCE_THRESHOLD,
        applied=applied,
        cached=cached,
        error=str(envelope["error"]) if envelope.get("error") else None,
        elapsed_ms=int(envelope.get("elapsed_ms") or 0),
    )


def analyse_ticket(
    db: Session,
    ticket: Ticket,
    *,
    model: ChatModel,
    settings: AnalysisSettings,
    operator: User,
    apply: bool = True,
    force: bool = False,
) -> AnalysisView:
    """对已有工单执行智能整理：可复用历史结果，也可强制重新调用模型。"""

    if not force:
        previous = latest_result(db, ticket.id)
        if previous is not None:
            return result_view(previous, cached=True, applied=True)

    run = run_analysis(model, settings, ticket.description, ticket.feature_module)

    if run.status == "FAILED" or run.suggestion.category is None:
        # 失败不写 analysis_results（该表要求分类非空），但必须在处理记录中留痕。
        db.add(
            TicketRecord(
                ticket_id=ticket.id,
                operator_id=operator.id,
                action="AI_ANALYSIS_FAILED",
                content=f"智能整理失败：{run.error or '未知原因'}；已保留原始反馈，等待人工分类。",
            )
        )
        db.commit()
        return AnalysisView(
            ticket_id=ticket.id,
            status="FAILED",
            title=run.suggestion.title,
            category=None,
            summary=run.suggestion.summary,
            keywords=run.suggestion.keywords,
            confidence=run.suggestion.confidence,
            reason=run.suggestion.reason,
            model_name=model.name,
            prompt_version=PROMPT_VERSION,
            needs_manual_review=True,
            fallback_used=run.fallback_used,
            applied=False,
            error=run.error,
            elapsed_ms=run.elapsed_ms,
        )

    suggestion = run.suggestion
    result = AnalysisResult(
        ticket_id=ticket.id,
        generated_title=suggestion.title,
        suggested_category=suggestion.category,
        generated_summary=suggestion.summary or "",
        keywords_json=json.dumps(suggestion.keywords, ensure_ascii=False),
        confidence=suggestion.confidence,
        model_name=model.name,
        raw_response=_envelope(run, settings.provider, model.name),
    )
    db.add(result)

    if apply:
        ticket.title = suggestion.title
        ticket.summary = suggestion.summary
        ticket.category = suggestion.category

    confidence_text = "未知" if suggestion.confidence is None else f"{suggestion.confidence:.2f}"
    db.add(
        TicketRecord(
            ticket_id=ticket.id,
            operator_id=operator.id,
            action="AI_ANALYSIS",
            content=(
                f"智能整理结果：分类={CATEGORY_LABELS.get(suggestion.category.value)}，"
                f"置信度={confidence_text}，状态={run.status}，模型={model.name}，提示词={PROMPT_VERSION}。"
                + ("已写入工单，可人工修改。" if apply else "仅生成建议，未写入工单。")
            ),
        )
    )
    db.commit()
    db.refresh(result)
    return result_view(result, cached=False, applied=apply)


def preview_suggestion(
    *,
    model: ChatModel,
    settings: AnalysisSettings,
    description: str,
    feature_module: str,
) -> AnalysisView:
    """提交页预览：不写库、不建工单，方便前端展示后再由用户修改。"""

    run = run_analysis(model, settings, description, feature_module)
    return AnalysisView(
        status=run.status,  # type: ignore[arg-type]
        title=run.suggestion.title,
        category=run.suggestion.category,
        category_label=CATEGORY_LABELS.get(run.suggestion.category.value)
        if run.suggestion.category
        else None,
        summary=run.suggestion.summary,
        keywords=run.suggestion.keywords,
        confidence=run.suggestion.confidence,
        reason=run.suggestion.reason,
        model_name=model.name,
        prompt_version=PROMPT_VERSION,
        needs_manual_review=run.needs_manual_review,
        fallback_used=run.fallback_used,
        error=run.error,
        elapsed_ms=run.elapsed_ms,
    )
