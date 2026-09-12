#!/usr/bin/env python3
"""
离线自测：不调用任何 API，验证提及识别 / 排名解析 / 指标计算的正确性。

    python test_smoke.py
"""

import sys

from config import BRAND, all_brands
from extractor import (context_of, find_mentions, label_of, rank_brands,
                       rule_sentiment, split_ranked_blocks)
from report import metrics_for, share_of_voice, visibility_index

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {extra}")


# ---------- 1. 提及识别：中文子串消歧 ----------
print("\n[1] 品牌提及识别")

check("命中 学大教育", len(find_mentions("推荐学大教育，一对一做得不错。", BRAND)) == 1)
check("命中 紫光学大", len(find_mentions("紫光学大是A股上市公司。", BRAND)) == 1)
check("命中 裸写的学大", len(find_mentions("学大在北京有很多校区。", BRAND)) == 1)
check("命中 学大一对一", len(find_mentions("学大一对一的课程体系。", BRAND)) == 1)

check("排除 教学大纲", find_mentions("按照教学大纲的要求安排课程。", BRAND) == [])
check("排除 数学大赛", find_mentions("他参加了数学大赛。", BRAND) == [])
check("排除 学大概", find_mentions("这门课学大概要三个月。", BRAND) == [])
check("排除 同学大多", find_mentions("班上同学大多选择了理科。", BRAND) == [])
check("排除 上学大约", find_mentions("上学大约需要二十分钟。", BRAND) == [])
check("排除 科学大会", find_mentions("全国科学大会召开。", BRAND) == [])

mixed = "教学大纲里没提补课，但学大教育确实是老牌机构。"
check("混合文本只算 1 次", len(find_mentions(mixed, BRAND)) == 1)

check("学大教育 不被重复计数",
      len(find_mentions("学大教育就是学大教育。", BRAND)) == 2,
      f"actual={len(find_mentions('学大教育就是学大教育。', BRAND))}")

# ---------- 2. 排名解析 ----------
print("\n[2] 推荐清单排名解析")

numbered = """推荐这几家：

1. 新东方：品牌知名度高。
2. 学大教育：个性化一对一，先测评再定方案。
3. 精锐教育：主打高端，价格偏高。
"""
blocks = split_ranked_blocks(numbered)
check("切出 3 个清单块", len(blocks) == 3, f"actual={len(blocks)}")
r = rank_brands(numbered, all_brands())
check("学大排第 2", r.ranks.get("学大教育") == 2, f"actual={r.ranks}")
check("新东方排第 1", r.ranks.get("新东方") == 1)
check("解析方式为 list", r.method == "list")

desc_line = """1. 学大教育
   老牌个性化机构，全职教师为主。
2. 新东方
   网点多。
"""
r2 = rank_brands(desc_line, all_brands())
check("多行块内品牌归属正确", r2.ranks.get("学大教育") == 1 and r2.ranks.get("新东方") == 2,
      f"actual={r2.ranks}")

unordered = """可以看看：

- 新东方：综合实力强
- 学大教育：一对一见长
- 掌门1对1：线上灵活
"""
r3 = rank_brands(unordered, all_brands())
check("无序清单也能排名", r3.ranks.get("学大教育") == 2, f"actual={r3.ranks}")

prose = "如果只看一对一，学大教育起步较早；新东方则是综合型的选择。"
r4 = rank_brands(prose, all_brands())
check("非清单退化为出现顺序", r4.method == "order" and r4.ranks.get("学大教育") == 1,
      f"actual={r4.method} {r4.ranks}")

none = "建议家长实地考察，核实办学资质。"
check("无品牌时 ranks 为空", rank_brands(none, all_brands()).ranks == {})

# ---------- 3. 竞品短写法消歧 ----------
print("\n[3] 竞品消歧")
check("精锐教育 命中", "精锐教育" in rank_brands("精锐教育主打高端一对一。", all_brands()).ranks)
check("精锐(无限定词) 不命中",
      "精锐教育" not in rank_brands("这支队伍作风精锐。", all_brands()).ranks)
check("卓越(无限定词) 不命中",
      "卓越教育" not in rank_brands("他的表现十分卓越。", all_brands()).ranks)

# ---------- 4. 情感 ----------
print("\n[4] 情感兜底打分")
pos_score, _, _ = rule_sentiment("学大教育口碑好，老师经验丰富，值得推荐。")
neg_score, _, _ = rule_sentiment("有家长反映学大教育退费难，还有投诉和纠纷。")
check("正面文本得正分", pos_score > 0.3, f"score={pos_score}")
check("负面文本得负分", neg_score < -0.3, f"score={neg_score}")
check("标签映射正确", label_of(pos_score) == "正面" and label_of(neg_score) == "负面")

ctx = context_of("前面一堆无关内容。" * 30 + "学大教育很专业。", find_mentions(
    "前面一堆无关内容。" * 30 + "学大教育很专业。", BRAND))
check("上下文窗口生效", "学大教育很专业" in ctx and len(ctx) < 400, f"len={len(ctx)}")

# ---------- 5. 指标计算 ----------
print("\n[5] 指标聚合")


def rec(mentioned, rank, sentiment_score, qtype="category", ok=True):
    return {
        "ok": ok, "type": qtype, "provider": "mock", "provider_label": "Mock",
        "model": "m", "question_id": "q", "question": "问", "scene": "s",
        "brand": {"mentioned": mentioned, "count": 1 if mentioned else 0,
                  "rank": rank, "is_first": rank == 1, "aliases_hit": []},
        "competitors": {"新东方": 1} if mentioned else {},
        "sentiment": {"score": sentiment_score,
                      "sentiment": label_of(sentiment_score), "risk": False,
                      "aspects": [], "positive_points": [], "negative_points": []},
        "brand_context": "",
    }


sample = [
    rec(True, 1, 0.8),
    rec(True, 3, 0.4),
    rec(False, None, 0.0),
    rec(False, None, 0.0),
    rec(True, 1, -0.6),
]
m = metrics_for(sample)
check("提及率 3/5", m["mention_rate"] == 0.6, f"actual={m['mention_rate']}")
check("首位率(提及口径) 2/3", abs(m["first_rate_in_mentioned"] - 0.6667) < 0.001,
      f"actual={m['first_rate_in_mentioned']}")
check("首位率(全量口径) 2/5", m["first_rate_overall"] == 0.4)
check("平均排名 (1+3+1)/3", abs(m["avg_rank"] - 1.67) < 0.01, f"actual={m['avg_rank']}")
check("正面 2 / 负面 1", m["positive_count"] == 2 and m["negative_count"] == 1,
      f"actual={m['positive_count']}/{m['negative_count']}")
check("可见度指数在 0-100", 0 <= m["visibility_index"] <= 100, f"actual={m['visibility_index']}")

brand_q = [rec(True, None, 0.5, qtype="brand")]
m2 = metrics_for(sample + brand_q)
check("品牌问不计入提及率分母", m2["category_answers"] == 5, f"actual={m2['category_answers']}")
check("品牌问计入情感分母", m2["judged_count"] == 4, f"actual={m2['judged_count']}")

sov = share_of_voice(sample)
xueda = next(r for r in sov if r["brand"] == "学大教育")
check("SOV 计算正确", abs(xueda["sov"] - 0.5) < 0.001, f"actual={xueda['sov']}")

check("指数单调性", visibility_index(0.8, 0.8, 0.8) > visibility_index(0.2, 0.2, 0.2))
check("全零指数", visibility_index(0, 0, -1) == 0.0, f"actual={visibility_index(0,0,-1)}")
check("零提及不白送情感分", visibility_index(0, 0, 0, has_sentiment=False) == 0.0,
      f"actual={visibility_index(0, 0, 0, has_sentiment=False)}")

nothing = [rec(False, None, 0.0) for _ in range(4)]
check("全未提及时指数为 0", metrics_for(nothing)["visibility_index"] == 0.0,
      f"actual={metrics_for(nothing)['visibility_index']}")

# ---------- 汇总 ----------
print(f"\n{'='*50}")
print(f"通过 {PASS}  失败 {FAIL}")
print(f"{'='*50}")
sys.exit(1 if FAIL else 0)
