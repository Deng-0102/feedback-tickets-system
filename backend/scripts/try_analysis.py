"""命令行试跑智能分析，用于无前端时验证提示词效果、截图和写报告。

用法（在 backend 目录、已安装依赖的前提下）：
    python -m scripts.try_analysis "修改密码后一直无法登录，重新安装也没用"
    python -m scripts.try_analysis "报表打开要两分钟" --module 报表中心 --provider mock

默认读取项目根目录 .env 中的 ANALYSIS_PROVIDER / ANALYSIS_API_KEY；
--provider mock 时强制使用离线演示模型，不消耗额度。
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.config import get_settings  # noqa: F401  触发项目根目录 .env 读取
from app.services.analysis_config import get_analysis_settings
from app.services.analysis_prompts import PROMPT_VERSION
from app.services.analysis_service import run_analysis
from app.services.llm_client import LLMCallError, build_chat_model


def main() -> int:
    parser = argparse.ArgumentParser(description="试跑反馈整理，输出标题、分类、摘要和耗时")
    parser.add_argument("description", help="用户反馈原文")
    parser.add_argument("--module", default="未指定功能模块", help="所属功能模块")
    parser.add_argument("--provider", choices=["deepseek", "mock"], help="临时覆盖 ANALYSIS_PROVIDER")
    parser.add_argument("--json", action="store_true", help="输出完整 JSON，便于贴进报告")
    args = parser.parse_args()

    if args.provider:
        import os

        os.environ["ANALYSIS_PROVIDER"] = args.provider
        get_analysis_settings.cache_clear()

    try:
        settings = get_analysis_settings()
        model = build_chat_model(settings)
    except (RuntimeError, LLMCallError) as exc:
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    run = run_analysis(model, settings, args.description, args.module)
    payload = {
        "status": run.status,
        "title": run.suggestion.title,
        "category": run.suggestion.category.value if run.suggestion.category else None,
        "summary": run.suggestion.summary,
        "keywords": run.suggestion.keywords,
        "confidence": run.suggestion.confidence,
        "reason": run.suggestion.reason,
        "model": model.name,
        "prompt_version": PROMPT_VERSION,
        "elapsed_ms": run.elapsed_ms,
        "error": run.error,
        "issues": run.issues,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if run.status != "FAILED" else 1

    print(f"模型      ：{model.name}（提示词 {PROMPT_VERSION}）")
    print(f"状态      ：{run.status}")
    print(f"标题      ：{run.suggestion.title}")
    print(f"分类      ：{run.suggestion.category.value if run.suggestion.category else '未识别'}")
    print(f"摘要      ：{run.suggestion.summary or '-'}")
    print(f"关键词    ：{'、'.join(run.suggestion.keywords) or '-'}")
    print(f"置信度    ：{run.suggestion.confidence if run.suggestion.confidence is not None else '-'}")
    print(f"分类依据  ：{run.suggestion.reason or '-'}")
    print(f"耗时      ：{run.elapsed_ms} ms")
    if run.error:
        print(f"降级原因  ：{run.error}")
    return 0 if run.status != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
