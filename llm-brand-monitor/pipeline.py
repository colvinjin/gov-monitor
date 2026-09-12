#!/usr/bin/env python3
"""
采集通道共用的记录构建逻辑

三条通道产出**完全一致**的记录结构，指标口径才不会因为采集方式不同而漂移：

    api      调用各家 OpenAI 兼容接口（monitor.py）
    browser  驱动浏览器问网页版（browser_channel.py）
    manual   人工在 App 里问，把回答贴回来（import_manual.py）

同时记录 mode（web=联网检索 / api=纯模型），报表按 mode 分组，
两种模式的数据**不能混着比**。
"""

from datetime import datetime
from typing import Dict, Optional

from config import BRAND, COMPETITORS, all_brands
from extractor import context_of, find_mentions, rank_brands
from judge import Verdict, judge_context, rule_verdict
from questions import Question

CHANNELS = ("api", "browser", "manual")
MODES = ("web", "api")


def analyze(answer: str) -> Dict:
    """对一条回答做提及 / 排名 / 竞品解析。"""
    brand_mentions = find_mentions(answer, BRAND)
    rank_result = rank_brands(answer, all_brands())
    brand_rank = rank_result.ranks.get(BRAND.name)

    competitors = {c.name: rank_result.ranks[c.name]
                   for c in COMPETITORS if c.name in rank_result.ranks}

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


def empty_brand() -> Dict:
    return {"mentioned": False, "count": 0, "rank": None, "is_first": False, "aliases_hit": []}


async def build_record(*, question: Question, answer: str, provider_key: str,
                       provider_label: str, model: str, repeat: int,
                       channel: str, mode: str,
                       ok: bool = True, error: str = "", latency_ms: int = 0,
                       client=None, judge_provider=None, use_judge: bool = False,
                       search_evidence: bool = False,
                       citations: int = 0) -> Dict:
    """把一条回答加工成标准记录（含情感判定）。"""
    now = datetime.now()
    record = {
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "channel": channel,
        "mode": mode,
        "provider": provider_key,
        "provider_label": provider_label,
        "model": model,
        "question_id": question.id,
        "question": question.text,
        "type": question.type,
        "scene": question.scene,
        "repeat": repeat,
        "ok": ok,
        "error": error,
        "latency_ms": latency_ms,
        "search_evidence": bool(search_evidence),
        "citations": citations,
        "answer": answer or "",
    }

    if not ok or not answer:
        record.update({"brand": empty_brand(), "competitors": {},
                       "sentiment": Verdict().to_dict(), "brand_context": ""})
        return record

    record.update(analyze(answer))
    ctx = record.pop("context", "")

    if record["brand"]["mentioned"]:
        if use_judge and client is not None and judge_provider is not None:
            verdict = await judge_context(client, judge_provider, BRAND.name, ctx)
        else:
            verdict = rule_verdict(ctx)
    else:
        verdict = Verdict()       # 未提及则不参与情感统计

    record["sentiment"] = verdict.to_dict()
    record["brand_context"] = ctx[:800]
    return record


def console_line(record: Dict) -> str:
    """一条记录的单行日志。"""
    if not record["ok"]:
        return f"  ❌ [{record['provider']}] {record['question_id']} #{record['repeat']} {record['error'][:60]}"
    b = record["brand"]
    flag = "🎯" if b["is_first"] else ("✅" if b["mentioned"] else "➖")
    rank_txt = f"第{b['rank']}位" if b["rank"] else ("未进清单" if b["mentioned"] else "未提及")
    s = record["sentiment"]
    cite = f" 🔗{record['citations']}" if record.get("citations") else ""
    return (f"  {flag} [{record['provider']}] {record['question_id']} #{record['repeat']} "
            f"{rank_txt} / {s['sentiment']}({s['score']}){cite}")
