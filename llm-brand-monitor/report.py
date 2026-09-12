#!/usr/bin/env python3
"""
指标聚合与报表生成

读取 data/raw/YYYY-MM-DD.jsonl，产出：
    data/daily/YYYY-MM-DD.json   当日聚合结果（同时作为趋势历史）
    web_data.json                看板数据（dashboard.html 直接读取）
    reports/YYYY-MM-DD.md        人读的日报

指标口径（重要，避免不同人算出不同数）：
    提及率   = 品类问题中提到学大的回答数 / 品类问题回答总数
               —— 只用 category 类问题，brand 类问题必然提及，计入会虚高。
    首位率   = 学大排第 1 的回答数 / 提及学大的回答数（口径A，默认展示）
               同时给出 / 品类问题回答总数（口径B，更严格）
    平均排名 = 进入推荐清单时的名次均值，未进清单不计入
    正面率   = 情感判定为正面的回答数 / 提及学大的回答数（全部问题类型）
    SOV      = 学大被提及的回答数 / 各监测品牌被提及回答数之和（品类+对比问题）
    可见度指数 = 100 × (0.45×提及率 + 0.30×排名得分 + 0.25×情感归一)

采集模式（mode）分开统计，绝不混算：
    web  网页版/App 口径（联网检索）—— **默认基线**，真实用户走的就是这条
    api  纯模型口径（不联网）—— 对照组，用来看提及率里有多少来自检索语料
同一天两种模式都有数据时，头条指标取 web，api 作为对照单列。
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from config import (BRAND, COMPETITORS, MENTION_NO_RANK_SCORE, RANK_SCORE,
                    RANK_SCORE_TAIL, WEIGHTS)

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
DAILY_DIR = ROOT / "data" / "daily"
REPORT_DIR = ROOT / "reports"
WEB_DATA = ROOT / "web_data.json"

HISTORY_DAYS = 14


# ============================================================
# 基础计算
# ============================================================

def _rate(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def rank_score(rec: Dict) -> float:
    """单条回答的排名得分：没提及 0 分，排得越靠前分越高。"""
    b = rec["brand"]
    if not b["mentioned"]:
        return 0.0
    rank = b.get("rank")
    if not rank:
        return MENTION_NO_RANK_SCORE
    return RANK_SCORE.get(rank, RANK_SCORE_TAIL)


def visibility_index(mention_rate: float, avg_rank_score: float, avg_sentiment: float,
                     has_sentiment: bool = True) -> float:
    """三项加权合成，0-100。情感从 -1~1 线性映射到 0~1。

    一条都没被提及时 has_sentiment=False，情感项记 0 分——否则"没人提"会被
    当成"中性评价"白送 12.5 分，指数就失去区分度了。
    """
    sentiment_norm = (avg_sentiment + 1) / 2 if has_sentiment else 0.0
    idx = (WEIGHTS["mention"] * mention_rate
           + WEIGHTS["rank"] * avg_rank_score
           + WEIGHTS["sentiment"] * sentiment_norm)
    return round(idx * 100, 1)


def metrics_for(records: List[Dict]) -> Dict:
    """对一组回答（同一模型，或全部模型）算全套指标。"""
    ok = [r for r in records if r.get("ok")]
    cat = [r for r in ok if r["type"] == "category"]
    mentioned_cat = [r for r in cat if r["brand"]["mentioned"]]
    first_cat = [r for r in mentioned_cat if r["brand"]["is_first"]]
    ranked = [r for r in mentioned_cat if r["brand"].get("rank")]

    # 情感在所有问题类型上统计（品牌问询类正是口碑主战场）
    judged = [r for r in ok if r["brand"]["mentioned"]]
    sent_scores = [float(r["sentiment"].get("score", 0.0)) for r in judged]
    labels = defaultdict(int)
    for r in judged:
        labels[r["sentiment"].get("sentiment", "中性")] += 1
    risk = [r for r in judged if r["sentiment"].get("risk")]

    mention_rate = _rate(len(mentioned_cat), len(cat))
    avg_rank_score = round(sum(rank_score(r) for r in cat) / len(cat), 4) if cat else 0.0
    avg_sentiment = round(sum(sent_scores) / len(sent_scores), 3) if sent_scores else 0.0

    return {
        "calls": len(records),
        "ok": len(ok),
        "fail": len(records) - len(ok),
        "category_answers": len(cat),
        "mention_count": len(mentioned_cat),
        "mention_rate": mention_rate,
        "first_count": len(first_cat),
        "first_rate_in_mentioned": _rate(len(first_cat), len(mentioned_cat)),
        "first_rate_overall": _rate(len(first_cat), len(cat)),
        "ranked_count": len(ranked),
        "avg_rank": round(sum(r["brand"]["rank"] for r in ranked) / len(ranked), 2) if ranked else None,
        "avg_rank_score": avg_rank_score,
        "judged_count": len(judged),
        "positive_count": labels["正面"],
        "neutral_count": labels["中性"],
        "negative_count": labels["负面"],
        "positive_rate": _rate(labels["正面"], len(judged)),
        "negative_rate": _rate(labels["负面"], len(judged)),
        "avg_sentiment": avg_sentiment,
        "risk_count": len(risk),
        "search_effective": len([r for r in ok if r.get("search_evidence")]),
        "search_effective_rate": _rate(len([r for r in ok if r.get("search_evidence")]), len(ok)),
        "visibility_index": visibility_index(mention_rate, avg_rank_score, avg_sentiment,
                                             has_sentiment=bool(judged)),
    }


def share_of_voice(records: List[Dict]) -> List[Dict]:
    """品类 + 对比问题里，各品牌被提及的回答数占比。"""
    scope = [r for r in records if r.get("ok") and r["type"] in ("category", "compare")]
    if not scope:
        return []

    counts = defaultdict(int)
    rank_sum = defaultdict(list)
    for r in scope:
        if r["brand"]["mentioned"]:
            counts[BRAND.name] += 1
            if r["brand"].get("rank"):
                rank_sum[BRAND.name].append(r["brand"]["rank"])
        for name, rank in (r.get("competitors") or {}).items():
            counts[name] += 1
            if rank:
                rank_sum[name].append(rank)

    total = sum(counts.values())
    rows = []
    for name, cnt in counts.items():
        ranks = rank_sum[name]
        rows.append({
            "brand": name,
            "is_self": name == BRAND.name,
            "mention_answers": cnt,
            "mention_rate": _rate(cnt, len(scope)),
            "sov": _rate(cnt, total),
            "avg_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
        })
    rows.sort(key=lambda x: (-x["mention_answers"], x["avg_rank"] or 99))
    return rows


def by_question(records: List[Dict]) -> List[Dict]:
    """按问题下钻：哪些问题模型完全不提学大，就是内容优化的靶子。"""
    groups = defaultdict(list)
    for r in records:
        if r.get("ok"):
            groups[r["question_id"]].append(r)

    rows = []
    for qid, recs in groups.items():
        cat_like = recs[0]["type"] == "category"
        mentioned = [r for r in recs if r["brand"]["mentioned"]]
        first = [r for r in mentioned if r["brand"]["is_first"]]
        judged_scores = [float(r["sentiment"].get("score", 0)) for r in mentioned]
        rows.append({
            "question_id": qid,
            "question": recs[0]["question"],
            "type": recs[0]["type"],
            "scene": recs[0]["scene"],
            "answers": len(recs),
            "mention_rate": _rate(len(mentioned), len(recs)) if cat_like else None,
            "mention_count": len(mentioned),
            "first_count": len(first),
            "avg_sentiment": round(sum(judged_scores) / len(judged_scores), 3) if judged_scores else None,
        })
    rows.sort(key=lambda x: (x["type"], -(x["mention_rate"] or 0)))
    return rows


def collect_highlights(records: List[Dict]) -> Dict:
    """挑出正/负面代表性片段和风险条目，供报告引用。"""
    judged = [r for r in records if r.get("ok") and r["brand"]["mentioned"]]
    judged.sort(key=lambda r: float(r["sentiment"].get("score", 0)))

    def brief(r: Dict) -> Dict:
        return {
            "provider": r["provider_label"],
            "question": r["question"],
            "sentiment": r["sentiment"].get("sentiment"),
            "score": r["sentiment"].get("score"),
            "positive_points": r["sentiment"].get("positive_points", []),
            "negative_points": r["sentiment"].get("negative_points", []),
            "snippet": (r.get("brand_context") or "").replace("\n", " ")[:220],
        }

    aspects = defaultdict(int)
    pos_points, neg_points = defaultdict(int), defaultdict(int)
    for r in judged:
        for a in r["sentiment"].get("aspects", []):
            aspects[a] += 1
        for p in r["sentiment"].get("positive_points", []):
            pos_points[p] += 1
        for n in r["sentiment"].get("negative_points", []):
            neg_points[n] += 1

    return {
        "worst": [brief(r) for r in judged[:3]],
        "best": [brief(r) for r in reversed(judged[-3:])],
        "risks": [brief(r) for r in judged if r["sentiment"].get("risk")][:5],
        "aspects": sorted(aspects.items(), key=lambda kv: -kv[1]),
        "top_positive_points": sorted(pos_points.items(), key=lambda kv: -kv[1])[:8],
        "top_negative_points": sorted(neg_points.items(), key=lambda kv: -kv[1])[:8],
    }


# ============================================================
# 读写
# ============================================================

def load_raw(date: str) -> List[Dict]:
    path = RAW_DIR / f"{date}.jsonl"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def load_history(days: int = HISTORY_DAYS) -> List[Dict]:
    history = []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        f = DAILY_DIR / f"{d}.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            o = data.get("overall", {})
            history.append({
                "date": d,
                "mention_rate": o.get("mention_rate", 0),
                "first_rate": o.get("first_rate_in_mentioned", 0),
                "positive_rate": o.get("positive_rate", 0),
                "visibility_index": o.get("visibility_index", 0),
                "has_data": True,
            })
        else:
            history.append({"date": d, "mention_rate": 0, "first_rate": 0,
                            "positive_rate": 0, "visibility_index": 0, "has_data": False})
    return history


def split_by_mode(records: List[Dict]) -> Dict[str, List[Dict]]:
    out = {"web": [], "api": []}
    for r in records:
        out.setdefault(r.get("mode", "api"), []).append(r)
    return out


def channel_rows(records: List[Dict]) -> List[Dict]:
    """按采集通道（接口 / 网页版 / App人工）汇总，用于看渠道间差值。"""
    names = {"api": "接口(API)", "browser": "网页版(浏览器)", "manual": "App(人工)"}
    rows = []
    for ch in ("api", "browser", "manual"):
        subset = [r for r in records if r.get("channel") == ch]
        if not subset:
            continue
        m = metrics_for(subset)
        m["channel"] = ch
        m["channel_label"] = names[ch]
        rows.append(m)
    return rows


def build(date: str = None) -> int:
    date = date or datetime.now().strftime("%Y-%m-%d")
    records = load_raw(date)
    if not records:
        print(f"❌ 没有找到 {date} 的采集数据（{RAW_DIR / (date + '.jsonl')}）")
        return 1

    by_mode = split_by_mode(records)
    # 基线取 web（网页版/App 口径）；当天只有 api 数据时退回 api 并标注
    baseline_mode = "web" if by_mode.get("web") else "api"
    baseline = by_mode[baseline_mode]

    overall = metrics_for(baseline)
    comparison = None
    if by_mode.get("web") and by_mode.get("api"):
        web_m, api_m = metrics_for(by_mode["web"]), metrics_for(by_mode["api"])
        comparison = {
            "web": web_m, "api": api_m,
            "mention_gap": round(web_m["mention_rate"] - api_m["mention_rate"], 4),
            "index_gap": round(web_m["visibility_index"] - api_m["visibility_index"], 1),
        }

    providers = []
    for key in sorted({(r["provider"], r.get("mode", "api")) for r in baseline}):
        pkey, pmode = key
        subset = [r for r in baseline if r["provider"] == pkey and r.get("mode", "api") == pmode]
        m = metrics_for(subset)
        m["provider"] = pkey
        m["provider_label"] = subset[0]["provider_label"]
        m["model"] = subset[0]["model"]
        m["mode"] = pmode
        m["channel"] = subset[0].get("channel", "api")
        providers.append(m)
    providers.sort(key=lambda x: -x["visibility_index"])

    payload = {
        "date": date,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "brand": BRAND.name,
        "competitors": [c.name for c in COMPETITORS],
        "baselineMode": baseline_mode,
        "modeCounts": {k: len(v) for k, v in by_mode.items() if v},
        "overall": overall,
        "comparison": comparison,
        "channels": channel_rows(baseline),
        "providers": providers,
        "sov": share_of_voice(baseline),
        "questions": by_question(baseline),
        "highlights": collect_highlights(baseline),
    }

    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    (DAILY_DIR / f"{date}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    payload_web = dict(payload)
    payload_web["history"] = load_history()
    WEB_DATA.write_text(json.dumps(payload_web, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"{date}.md"
    md_path.write_text(render_markdown(payload_web), encoding="utf-8")

    print(f"\n📈 报表已生成:")
    print(f"   聚合数据 {DAILY_DIR / (date + '.json')}")
    print(f"   看板数据 {WEB_DATA}")
    print(f"   日报     {md_path}")
    print_console(payload)
    return 0


# ============================================================
# 渲染
# ============================================================

def _pct(v) -> str:
    return "-" if v is None else f"{v:.1%}"


MODE_DESC = {"web": "网页版/App 口径（联网检索）", "api": "纯模型口径（不联网）"}


def print_console(p: Dict):
    o = p["overall"]
    print(f"\n{'='*64}")
    print(f"📊 {p['brand']} 大模型可见度日报 {p['date']}")
    print(f"   基线口径: {MODE_DESC.get(p['baselineMode'], p['baselineMode'])}")
    print(f"{'='*64}")
    print(f"  可见度指数   {o['visibility_index']}/100")
    print(f"  提及率       {_pct(o['mention_rate'])}  ({o['mention_count']}/{o['category_answers']} 条品类问答)")
    print(f"  首位率       {_pct(o['first_rate_in_mentioned'])} (提及口径) / {_pct(o['first_rate_overall'])} (全量口径)")
    print(f"  平均排名     {o['avg_rank'] if o['avg_rank'] else '-'}")
    print(f"  正面率       {_pct(o['positive_rate'])}  负面率 {_pct(o['negative_rate'])}  平均情感分 {o['avg_sentiment']}")
    if o["risk_count"]:
        print(f"  ⚠️ 风险表述   {o['risk_count']} 条")
    if p.get("comparison"):
        c = p["comparison"]
        print(f"\n  联网 vs 不联网：提及率 {_pct(c['web']['mention_rate'])} vs "
              f"{_pct(c['api']['mention_rate'])}（差 {c['mention_gap']*100:+.1f}pt），"
              f"指数差 {c['index_gap']:+.1f}")
    if len(p.get("channels", [])) > 1:
        print(f"\n  分通道：")
        for ch in p["channels"]:
            print(f"    {ch['channel_label']:<16} 提及 {_pct(ch['mention_rate']):>6}  "
                  f"首位 {_pct(ch['first_rate_in_mentioned']):>6}  指数 {ch['visibility_index']}")
    print(f"\n  分模型：")
    for m in p["providers"]:
        print(f"    {m['provider_label']:<18} 指数 {m['visibility_index']:>5}  "
              f"提及 {_pct(m['mention_rate']):>6}  首位 {_pct(m['first_rate_in_mentioned']):>6}  "
              f"正面 {_pct(m['positive_rate']):>6}")


def render_markdown(p: Dict) -> str:
    o = p["overall"]
    lines = [
        f"# {p['brand']} · 大模型可见度日报（{p['date']}）",
        "",
        f"> 生成时间 {p['generatedAt']}｜有效回答 {o['ok']}/{o['calls']} 条"
        f"｜监测模型 {len(p['providers'])} 个",
        "",
        f"**基线口径：{MODE_DESC.get(p['baselineMode'], p['baselineMode'])}**"
        f"（真实用户主要使用网页版和 App，因此以联网口径为准）"
        f"｜联网实际生效 {_pct(o.get('search_effective_rate'))}",
        "",
        "## 一、核心指标",
        "",
        "| 指标 | 数值 | 说明 |",
        "| --- | --- | --- |",
        f"| 可见度指数 | **{o['visibility_index']}** / 100 | 提及率45% + 排名30% + 情感25% 加权 |",
        f"| 提及率 | **{_pct(o['mention_rate'])}** | {o['mention_count']}/{o['category_answers']} 条品类推荐问答中被提到 |",
        f"| 首位率（提及口径） | **{_pct(o['first_rate_in_mentioned'])}** | 提及的 {o['mention_count']} 条里有 {o['first_count']} 条排第一 |",
        f"| 首位率（全量口径） | {_pct(o['first_rate_overall'])} | 全部品类问答中排第一的比例 |",
        f"| 平均排名 | {o['avg_rank'] or '-'} | 进入推荐清单时的平均名次 |",
        f"| 正面率 | **{_pct(o['positive_rate'])}** | 提及学大的 {o['judged_count']} 条回答中的正面占比 |",
        f"| 负面率 | {_pct(o['negative_rate'])} | 同上口径 |",
        f"| 平均情感分 | {o['avg_sentiment']} | -1 ~ 1 |",
        f"| 风险表述 | {o['risk_count']} 条 | 退费/投诉/资质等负面表述 |",
        "",
        "## 二、分模型表现",
        "",
        "| 模型 | 通道 | 可见度指数 | 提及率 | 首位率 | 平均排名 | 正面率 | 失败 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ch_names = {"api": "接口", "browser": "网页版", "manual": "App人工"}
    for m in p["providers"]:
        lines.append(
            f"| {m['provider_label']}（{m['model']}） | {ch_names.get(m.get('channel'), '-')} | "
            f"{m['visibility_index']} | "
            f"{_pct(m['mention_rate'])} | {_pct(m['first_rate_in_mentioned'])} | "
            f"{m['avg_rank'] or '-'} | {_pct(m['positive_rate'])} | {m['fail']} |")

    if p.get("comparison"):
        c = p["comparison"]
        lines += ["", "## 二之二、联网 vs 不联网对照", "",
                  "| 口径 | 提及率 | 首位率 | 平均排名 | 可见度指数 |",
                  "| --- | --- | --- | --- | --- |",
                  f"| 网页版/App（联网） | {_pct(c['web']['mention_rate'])} | "
                  f"{_pct(c['web']['first_rate_in_mentioned'])} | {c['web']['avg_rank'] or '-'} | "
                  f"{c['web']['visibility_index']} |",
                  f"| 纯模型（不联网） | {_pct(c['api']['mention_rate'])} | "
                  f"{_pct(c['api']['first_rate_in_mentioned'])} | {c['api']['avg_rank'] or '-'} | "
                  f"{c['api']['visibility_index']} |",
                  "",
                  f"提及率差 **{c['mention_gap']*100:+.1f}pt**，可见度指数差 **{c['index_gap']:+.1f}**。"
                  f"差值为正说明联网检索帮学大加了分（检索语料里有学大），"
                  f"差值为负说明模型自身知识里学大更靠前、而检索结果把竞品带了上来。", ""]

    if len(p.get("channels", [])) > 1:
        lines += ["", "## 二之三、分采集通道", "",
                  "| 通道 | 回答数 | 提及率 | 首位率 | 正面率 | 可见度指数 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for ch in p["channels"]:
            lines.append(f"| {ch['channel_label']} | {ch['ok']} | {_pct(ch['mention_rate'])} | "
                         f"{_pct(ch['first_rate_in_mentioned'])} | {_pct(ch['positive_rate'])} | "
                         f"{ch['visibility_index']} |")
        lines += ["", "> 接口与网页版/App 的差值就是校准系数：可以用接口做高频监测，"
                  "定期用网页版/App 采一批做校准。", ""]

    lines += ["", "## 三、竞品声量份额（SOV）", "",
              "| 品牌 | 被提及回答数 | 提及率 | SOV | 平均排名 |",
              "| --- | --- | --- | --- | --- |"]
    for row in p["sov"]:
        mark = " ⭐" if row["is_self"] else ""
        lines.append(f"| {row['brand']}{mark} | {row['mention_answers']} | "
                     f"{_pct(row['mention_rate'])} | {_pct(row['sov'])} | {row['avg_rank'] or '-'} |")

    h = p["highlights"]
    lines += ["", "## 四、口碑归因", ""]
    if h["top_positive_points"]:
        lines.append("**被夸的点**：" + "、".join(f"{k}({v})" for k, v in h["top_positive_points"]))
    if h["top_negative_points"]:
        lines.append("")
        lines.append("**被质疑的点**：" + "、".join(f"{k}({v})" for k, v in h["top_negative_points"]))
    if h["risks"]:
        lines += ["", "**⚠️ 风险片段**：", ""]
        for r in h["risks"]:
            lines.append(f"- [{r['provider']}] {r['question']} → {r['snippet']}")

    weak = [q for q in p["questions"] if q["type"] == "category" and (q["mention_rate"] or 0) == 0]
    lines += ["", "## 五、优化靶子（完全未被提及的品类问题）", ""]
    if weak:
        for q in weak:
            lines.append(f"- `{q['question_id']}` [{q['scene']}] {q['question']}")
    else:
        lines.append("- 无，全部品类问题均有提及。")

    lines += ["", "---", "", "*口径说明见 report.py 文件头注释。*", ""]
    return "\n".join(lines)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else None
    return build(date)


if __name__ == "__main__":
    raise SystemExit(main())
