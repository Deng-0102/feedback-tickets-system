"""用测试集批量评测智能分析效果（离线跑，不经过 HTTP 和数据库）。

用法（在 backend 目录执行）：
    # 1. 先用离线演示模型把流程跑通，不花钱
    python -m scripts.eval_analysis --provider mock --limit 5

    # 2. 全量 25 条（模型由 .env 决定；默认 0.8 秒间隔，避免触发限流）
    python -m scripts.eval_analysis

    # 3. 中断后继续跑（按“编号”跳过已有结果）
    python -m scripts.eval_analysis --resume

输出：
    docs/member3/测试结果.csv        每条样本的预测、耗时、错误
    docs/member3/测试结果-汇总.md    总体/分类准确率、状态分布，可直接贴进报告

说明：
- 输入文件默认 docs/member3/测试集-模板.csv，列名必须包含“编号/用户描述/功能模块/人工标准分类”；
- “是否分类正确”由脚本自动比对；"标题是否可用" 留空，需要人工看一遍再填（报告里写标题可用率）；
- 评测只调用模型，不写数据库、不建工单，失败也不会污染演示数据。
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from app.core.config import get_settings  # noqa: F401  触发项目根目录 .env 读取
from app.services.analysis_config import AnalysisSettings, get_analysis_settings
from app.services.analysis_service import CATEGORY_LABELS, run_analysis
from app.services.llm_client import ChatModel, build_chat_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "docs" / "member3" / "测试集-模板.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "member3" / "测试结果.csv"

REQUIRED_COLUMNS = ("编号", "用户描述", "功能模块", "人工标准分类")
OUTPUT_COLUMNS = (
    "编号",
    "用户描述",
    "功能模块",
    "人工标准分类",
    "模型分类",
    "是否分类正确",
    "置信度",
    "标题",
    "标题是否可用",
    "摘要",
    "耗时ms",
    "状态",
    "错误",
)


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"找不到测试集文件：{path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"测试集缺少列：{'、'.join(missing)}")
        rows = [row for row in reader if (row.get("用户描述") or "").strip()]
    if not rows:
        raise SystemExit("测试集里没有有效的用户描述")
    return rows


def load_existing(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["编号"]: row for row in csv.DictReader(handle) if row.get("编号")}


def normalise_label(value: str) -> str:
    text = (value or "").strip().upper()
    for code, label in CATEGORY_LABELS.items():
        if text == code or text == label:
            return code
    return text


def evaluate(
    rows: list[dict[str, str]],
    model: ChatModel,
    settings: AnalysisSettings,
    *,
    sleep_seconds: float,
    limit: int | None,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    selected = rows[:limit] if limit else rows
    total = len(selected)

    for index, row in enumerate(selected, start=1):
        description = row["用户描述"].strip()
        module = (row.get("功能模块") or "未指定").strip()
        expected = normalise_label(row.get("人工标准分类", ""))

        started = time.perf_counter()
        run = run_analysis(model, settings, description, module)
        wall_ms = int((time.perf_counter() - started) * 1000)

        predicted = run.suggestion.category.value if run.suggestion.category else ""
        correct = "是" if predicted and predicted == expected else "否"

        results.append(
            {
                "编号": row.get("编号", str(index)),
                "用户描述": description,
                "功能模块": module,
                "人工标准分类": expected,
                "模型分类": predicted,
                "是否分类正确": correct,
                "置信度": "" if run.suggestion.confidence is None else f"{run.suggestion.confidence:.2f}",
                "标题": run.suggestion.title,
                "标题是否可用": "",
                "摘要": run.suggestion.summary or "",
                "耗时ms": str(run.elapsed_ms or wall_ms),
                "状态": run.status,
                "错误": run.error or "",
            }
        )
        marker = "OK " if correct == "是" else "ERR"
        print(
            f"[{index}/{total}] {marker} {row.get('编号','?'):>3} "
            f"标准={expected or '-':<20} 预测={predicted or '-':<20} "
            f"{run.status:<8} {run.elapsed_ms or wall_ms:>6}ms"
        )
        if sleep_seconds and index < total:
            time.sleep(sleep_seconds)

    return results


def write_results(path: Path, results: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


def build_summary(results: list[dict[str, str]], model: ChatModel, settings: AnalysisSettings) -> str:
    total = len(results)
    judged = [row for row in results if row["人工标准分类"]]
    correct = [row for row in judged if row["是否分类正确"] == "是"]
    accuracy = len(correct) / len(judged) * 100 if judged else 0.0
    status_count: dict[str, int] = {}
    for row in results:
        status_count[row["状态"]] = status_count.get(row["状态"], 0) + 1

    per_category: dict[str, list[int]] = {}
    for row in judged:
        bucket = per_category.setdefault(row["人工标准分类"], [0, 0])
        bucket[1] += 1
        if row["是否分类正确"] == "是":
            bucket[0] += 1

    elapsed = [int(row["耗时ms"]) for row in results if row["耗时ms"].isdigit()]
    avg_elapsed = statistics.mean(elapsed) if elapsed else 0

    provider_note = "离线演示模型（mock），结果不能作为真实模型效果" if model.is_mock else f"真实模型 {model.name}"
    lines = [
        "# 智能分析测试结果汇总",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模型设置：`{provider_note}`；温度 {settings.temperature}；提示词版本见代码 `PROMPT_VERSION`",
        f"- 样本总数：{total} 条（有人工标准分类的 {len(judged)} 条）",
        f"- **分类准确率：{accuracy:.1f}%（{len(correct)}/{len(judged)}）**",
        f"- 状态分布：" + "、".join(f"{key} {value} 条" for key, value in sorted(status_count.items())),
        f"- 平均耗时：{avg_elapsed:.0f} ms",
        "",
        "## 各分类准确率",
        "",
        "| 分类 | 正确/总数 | 准确率 |",
        "|---|---|---|",
    ]
    for code, (hit, count) in sorted(per_category.items()):
        label = CATEGORY_LABELS.get(code, code)
        lines.append(f"| {code}（{label}） | {hit}/{count} | {hit / count * 100:.0f}% |")

    lines += [
        "",
        "## 需要人工补的部分",
        "",
        "1. 打开 `docs/member3/测试结果.csv`，逐行看“标题”列，在“标题是否可用”填“是/否”；",
        "2. 标题可用率 = 填“是”的条数 / 总条数，写进报告 4.4.9 节；",
        "3. 把分类错误的样本单独列出来，分析原因（提示词边界不清、描述太短、多问题混合等），作为“提示词迭代”的依据。",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="批量评测智能分析（测试集 → 准确率报告）")
    parser.add_argument("--file", type=Path, default=DEFAULT_INPUT, help="测试集 CSV 路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="结果 CSV 路径")
    parser.add_argument("--provider", choices=["deepseek", "mock"], help="临时覆盖 ANALYSIS_PROVIDER")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条，用于试跑")
    parser.add_argument("--sleep", type=float, default=0.8, help="每条之间的间隔秒数，默认 0.8")
    parser.add_argument("--resume", action="store_true", help="跳过结果 CSV 里已有的编号")
    parser.add_argument("--dry-run", action="store_true", help="只检查测试集并打印条数，不调用模型")
    args = parser.parse_args()

    rows = load_rows(args.file)
    if args.resume:
        existing = load_existing(args.output)
        rows = [row for row in rows if row.get("编号") not in existing]
    if args.dry_run:
        print(f"测试集共 {len(rows)} 条，列名检查通过；未调用模型。")
        return 0

    if args.provider:
        import os

        os.environ["ANALYSIS_PROVIDER"] = args.provider
        get_analysis_settings.cache_clear()

    settings = get_analysis_settings()
    try:
        model = build_chat_model(settings)
    except RuntimeError as exc:
        print(f"配置错误：{exc}")
        return 2

    if model.is_mock:
        print("注意：当前是离线演示模型（mock），只能验证流程，结果不能写进报告当真实效果。")

    results = evaluate(rows, model, settings, sleep_seconds=args.sleep, limit=args.limit)

    if args.resume:
        merged = list(load_existing(args.output).values()) + results
        merged.sort(key=lambda row: int(row["编号"]) if row["编号"].isdigit() else 0)
        results = merged

    write_results(args.output, results)
    summary = build_summary(results, model, settings)
    summary_path = args.output.with_name(f"{args.output.stem}-汇总.md")
    summary_path.write_text(summary, encoding="utf-8")

    print(f"\n结果已写入：{args.output}")
    print(f"汇总已写入：{summary_path}")
    for line in summary.splitlines():
        if "分类准确率" in line:
            print(line)
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
