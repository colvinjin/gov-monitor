#!/usr/bin/env python3
"""
学大教育 · 大模型品牌可见度监测 Agent —— 采集主流程

一次运行 = 问题集 × 模型 × 重复采样次数，每条回答依次经过：
    调用模型 → 提及识别 → 排名解析 → 情感裁判 → 落盘

原始结果写入 data/raw/YYYY-MM-DD.jsonl（每行一条回答，保留全文便于复核），
指标聚合交给 report.py。

用法：
    python monitor.py --dry-run                 # 不用 API Key，跑通全流程
    python monitor.py                           # 跑全部已配置模型 × 全部问题
    python monitor.py --providers doubao,qwen --types category --repeats 3
    python monitor.py --limit 5 --no-judge      # 快速冒烟
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import config
from config import BRAND, COMPETITORS, all_brands
from extractor import context_of, find_mentions, rank_brands
from judge import Verdict, judge_context, rule_verdict
from llm_client import MOCK_PROVIDER, LLMClient
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


def analyze(answer: str) -> Dict:
    """对一条回答做提及 / 排名 / 竞品解析。"""
    brand_mentions = find_mentions(answer, BRAND)
    rank_result = rank_brands(answer, all_brands())
    brand_rank = rank_result.ranks.get(BRAND.name)

    competitors = {}
    for c in COMPETITORS:
        if c.name in rank_result.ranks:
            competitors[c.name] = rank_result.ranks[c.name]

    return {
        "brand": {
            "mentioned": bool(brand_mentions),
            "count": len(brand_mentions),
            "rank": brand_rank,
            "is_first": brand_rank == 1,
            "aliases_hit": sorted({m.alias for m in brand_mentions}),
        },
        "rank_method": rank_result.method,
        "list_size": rank_result.list_size,
        "competitors": competitors,
        "context": context_of(answer, brand_mentions),
    }


async def run_one(client: LLMClient, provider: config.Provider, question: Question,
                  repeat: int, judge_provider, use_judge: bool) -> Dict:
    result = await client.chat(provider, question.text)

    record = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "provider": provider.key,
        "provider_label": provider.label,
        "model": result.model or provider.model,
        "question_id": question.id,
        "question": question.text,
        "type": question.type,
        "scene": question.scene,
        "repeat": repeat,
        "ok": result.ok,
        "error": result.error,
        "latency_ms": result.latency_ms,
        "answer": result.text,
    }

    if not result.ok:
        record.update({"brand": {"mentioned": False, "count": 0, "rank": None,
                                 "is_first": False, "aliases_hit": []},
                       "competitors": {}, "sentiment": Verdict().to_dict()})
        return record

    record.update(analyze(result.text))

    ctx = record.pop("context", "")
    if record["brand"]["mentioned"]:
        if use_judge and judge_provider is not None:
            verdict = await judge_context(client, judge_provider, BRAND.name, ctx)
        else:
            verdict = rule_verdict(ctx)
    else:
        verdict = Verdict()          # 未提及则不参与情感统计
    record["sentiment"] = verdict.to_dict()
    record["brand_context"] = ctx[:800]

    flag = "🎯" if record["brand"]["is_first"] else ("✅" if record["brand"]["mentioned"] else "➖")
    rank_txt = f"第{record['brand']['rank']}位" if record["brand"]["rank"] else "未进清单"
    print(f"  {flag} [{provider.key}] {question.id} #{repeat} "
          f"{rank_txt} / {verdict.sentiment}({verdict.score})")
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
    print(f"\n{'='*64}")
    print(f"🚀 学大教育 · 大模型可见度监测  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   模型 {len(providers)} 个: {', '.join(p.label for p in providers)}")
    print(f"   问题 {len(questions)} 个 × 重复 {args.repeats} 次 = {total} 次调用")
    print(f"   情感裁判: {judge_provider.label if judge_provider else '词典法'}")
    print(f"{'='*64}\n")

    tasks = []
    async with LLMClient(concurrency=args.concurrency) as client:
        for provider in providers:
            for q in questions:
                for r in range(1, args.repeats + 1):
                    tasks.append(run_one(client, provider, q, r, judge_provider, use_judge))
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

    print("\n📊 本次快照（完整报表请运行 report.py）")
    print(f"  有效回答      : {len(ok)}/{len(records)}")
    if cat:
        print(f"  提及率(品类问) : {len(mentioned)}/{len(cat)} = {len(mentioned)/len(cat):.1%}")
    if mentioned:
        print(f"  首位率(提及内) : {len(first)}/{len(mentioned)} = {len(first)/len(mentioned):.1%}")
    if judged:
        print(f"  正面率        : {len(positive)}/{len(judged)} = {len(positive)/len(judged):.1%}")


def main():
    parser = argparse.ArgumentParser(description="学大教育大模型可见度监测")
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
