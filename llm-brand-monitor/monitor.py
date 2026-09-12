#!/usr/bin/env python3
"""
学大教育 · 大模型品牌可见度监测 Agent —— 采集主流程

一次运行 = 问题集 × 模型 × 重复采样次数，每条回答依次经过：
    调用模型 → 提及识别 → 排名解析 → 情感裁判 → 落盘

原始结果写入 data/raw/YYYY-MM-DD.jsonl（每行一条回答，保留全文便于复核），
指标聚合交给 report.py。

模式（重要）：
    --mode web  默认。尽量开启各家的联网检索，贴近用户真实使用的网页版/App。
    --mode api  纯模型能力，不联网，用于对照。
真实用户走的是网页版和 App，所以基线用 web 模式；两种模式的数据不能混着比。
接口层开不了联网的模型（DeepSeek / Kimi / MiniMax），用 browser_channel.py
或 import_manual.py 采集网页版结果。

用法：
    python monitor.py --dry-run                 # 不用 API Key，跑通全流程
    python monitor.py                           # web 模式跑全部已配置模型
    python monitor.py --mode api                # 对照组
    python monitor.py --providers doubao,qwen --types category --repeats 3
    python monitor.py --limit 5 --no-judge      # 快速冒烟
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import config
from llm_client import MOCK_PROVIDER, LLMClient
from pipeline import build_record, console_line
from questions import Question, select

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"


def resolve_providers(spec: str, dry_run: bool) -> List[config.Provider]:
    if dry_run:
        return [MOCK_PROVIDER]
    if spec and spec != "all":
        picked = [config.get_provider(k.strip()) for k in spec.split(",") if k.strip()]
        missing = [p.label for p in picked if not p.available]
        if missing:
            print(f"⚠️  以下模型缺少 API Key，将被跳过: {', '.join(missing)}")
        return [p for p in picked if p.available]
    providers = config.available_providers()
    if not providers:
        print("⚠️  未检测到任何模型 API Key，自动切换到 --dry-run 模式（mock 数据）")
        return [MOCK_PROVIDER]
    return providers


async def run_one(client: LLMClient, provider: config.Provider, question: Question,
                  repeat: int, mode: str, judge_provider, use_judge: bool) -> Dict:
    result = await client.chat(provider, question.text, mode=mode)

    record = await build_record(
        question=question, answer=result.text,
        provider_key=provider.key, provider_label=provider.label,
        model=result.model or provider.model, repeat=repeat,
        channel="api", mode=mode,
        ok=result.ok, error=result.error, latency_ms=result.latency_ms,
        client=client, judge_provider=judge_provider, use_judge=use_judge,
        search_evidence=result.search_evidence, citations=result.citations,
    )
    print(console_line(record))
    return record


async def run(args) -> List[Dict]:
    providers = resolve_providers(args.providers, args.dry_run)
    if not providers:
        print("❌ 没有可用模型，退出")
        return []

    types = [t.strip() for t in args.types.split(",")] if args.types else None
    questions = select(types=types, limit=args.limit)

    judge_provider = None
    use_judge = not args.no_judge and not args.dry_run
    if use_judge:
        try:
            judge_provider = config.pick_judge()
        except RuntimeError as e:
            print(f"⚠️  {e}，本次使用词典法打分")
            use_judge = False

    total = len(providers) * len(questions) * args.repeats
    mode_desc = "web（开联网检索，贴近网页版/App）" if args.mode == "web" else "api（纯模型，不联网）"
    print(f"\n{'='*64}")
    print(f"🚀 学大教育 · 大模型可见度监测  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   采集模式: {mode_desc}")
    print(f"   模型 {len(providers)} 个: {', '.join(p.label for p in providers)}")
    print(f"   问题 {len(questions)} 个 × 重复 {args.repeats} 次 = {total} 次调用")
    print(f"   情感裁判: {judge_provider.label if judge_provider else '词典法'}")
    print(f"{'='*64}\n")

    if args.mode == "web":
        no_search = [p for p in providers
                     if not p.supports_api_search and p.key not in ("mock",)
                     and not (p.key == "doubao" and os.getenv("ARK_BOT_ID", "").strip())]
        if no_search:
            print("⚠️  以下模型接口层开不了联网检索，结果会低估网页版/App 表现：")
            for p in no_search:
                print(f"     · {p.label}：{p.search_note or '暂不支持'}")
            print("   建议对这几家改用 browser_channel.py 或 import_manual.py。\n")

    tasks = []
    async with LLMClient(concurrency=args.concurrency) as client:
        for provider in providers:
            for q in questions:
                for r in range(1, args.repeats + 1):
                    tasks.append(run_one(client, provider, q, r, args.mode,
                                         judge_provider, use_judge))
        records = await asyncio.gather(*tasks)

    return list(records)


def save(records: List[Dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    out = RAW_DIR / f"{date}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n💾 原始记录已追加到 {out}（本次 {len(records)} 条）")
    return out


def quick_summary(records: List[Dict]):
    ok = [r for r in records if r["ok"]]
    cat = [r for r in ok if r["type"] == "category"]
    if not ok:
        print("\n❌ 全部调用失败，请检查 API Key 与网络")
        return
    mentioned = [r for r in cat if r["brand"]["mentioned"]]
    first = [r for r in mentioned if r["brand"]["is_first"]]
    judged = [r for r in ok if r["brand"]["mentioned"]]
    positive = [r for r in judged if r["sentiment"]["sentiment"] == "正面"]

    with_cite = [r for r in ok if r.get("search_evidence")]
    print("\n📊 本次快照（完整报表请运行 report.py）")
    print(f"  有效回答      : {len(ok)}/{len(records)}")
    if records and records[0].get("mode") == "web":
        print(f"  联网实际生效   : {len(with_cite)}/{len(ok)}（响应里带回检索引用的比例）")
    if cat:
        print(f"  提及率(品类问) : {len(mentioned)}/{len(cat)} = {len(mentioned)/len(cat):.1%}")
    if mentioned:
        print(f"  首位率(提及内) : {len(first)}/{len(mentioned)} = {len(first)/len(mentioned):.1%}")
    if judged:
        print(f"  正面率        : {len(positive)}/{len(judged)} = {len(positive)/len(judged):.1%}")


def main():
    parser = argparse.ArgumentParser(description="学大教育大模型可见度监测")
    parser.add_argument("--mode", default=config.DEFAULT_MODE, choices=["web", "api"],
                        help="web=开联网检索贴近网页版/App（默认）；api=纯模型对照")
    parser.add_argument("--providers", default="all", help="逗号分隔的模型标识，默认全部已配置模型")
    parser.add_argument("--types", default="", help="问题类型过滤: category,brand,compare")
    parser.add_argument("--repeats", type=int, default=config.REPEATS, help="每题重复采样次数")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个问题（冒烟用）")
    parser.add_argument("--concurrency", type=int, default=config.CONCURRENCY, help="并发数")
    parser.add_argument("--dry-run", action="store_true", help="使用 mock 回答，不调用真实 API")
    parser.add_argument("--no-judge", action="store_true", help="跳过 LLM 裁判，只用词典法打分")
    parser.add_argument("--no-report", action="store_true", help="采集后不自动生成报表")
    args = parser.parse_args()

    records = asyncio.run(run(args))
    if not records:
        return 1

    save(records)
    quick_summary(records)

    if not args.no_report:
        import report
        report.build(datetime.now().strftime("%Y-%m-%d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
