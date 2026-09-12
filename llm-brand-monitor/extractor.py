#!/usr/bin/env python3
"""
回答解析层：从模型回答里抽出「有没有提到 / 排第几 / 说得好不好」

三个能力：
1. find_mentions   —— 品牌提及识别（带中文子串消歧，避免"教学大纲"被算成"学大"）
2. rank_brands     —— 推荐清单排名解析（优先解析有序列表，退化为首次出现顺序）
3. rule_sentiment  —— 基于词典的情感兜底打分（LLM 裁判不可用时使用）
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from config import CONTEXT_WINDOW, Brand


# ============================================================
# 1. 品牌提及识别
# ============================================================

@dataclass
class Mention:
    brand: str
    alias: str
    start: int
    end: int


def _overlaps(start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
    return any(not (end <= s or start >= e) for s, e in spans)


def find_mentions(text: str, brand: Brand) -> List[Mention]:
    """找出 text 中某个品牌的全部有效提及。

    先匹配强别名（长词优先），再匹配需要消歧的短写法；
    短写法命中后用前后字符黑名单 + 限定词窗口过滤误伤。
    """
    if not text:
        return []

    mentions: List[Mention] = []
    spans: List[Tuple[int, int]] = []

    for alias in sorted(brand.aliases, key=len, reverse=True):
        for m in re.finditer(re.escape(alias), text):
            if _overlaps(m.start(), m.end(), spans):
                continue
            spans.append((m.start(), m.end()))
            mentions.append(Mention(brand.name, alias, m.start(), m.end()))

    for alias in sorted(brand.fuzzy, key=len, reverse=True):
        for m in re.finditer(re.escape(alias), text):
            if _overlaps(m.start(), m.end(), spans):
                continue  # 已被强别名覆盖（如"学大教育"里的"学大"）
            if not _fuzzy_ok(text, m.start(), m.end(), brand):
                continue
            spans.append((m.start(), m.end()))
            mentions.append(Mention(brand.name, alias, m.start(), m.end()))

    mentions.sort(key=lambda x: x.start)
    return mentions


def _fuzzy_ok(text: str, start: int, end: int, brand: Brand) -> bool:
    """短写法消歧：前后字符黑名单 + 限定词窗口。"""
    prev_char = text[start - 1] if start > 0 else ""
    next_char = text[end] if end < len(text) else ""

    if prev_char and brand.fuzzy_prev_block and prev_char in brand.fuzzy_prev_block:
        return False
    if next_char and brand.fuzzy_next_block and next_char in brand.fuzzy_next_block:
        return False

    if brand.fuzzy_require:
        window = text[max(0, start - 10):end + 10]
        if not any(word in window for word in brand.fuzzy_require):
            return False
    return True


def find_all_mentions(text: str, brands: List[Brand]) -> Dict[str, List[Mention]]:
    return {b.name: find_mentions(text, b) for b in brands}


def mentioned(text: str, brand: Brand) -> bool:
    return len(find_mentions(text, brand)) > 0


# ============================================================
# 2. 推荐清单排名解析
# ============================================================

# 逐行识别有序列表标记：1. / 1、/ （1）/ 一、/ ①
_ORDERED = [
    re.compile(r"^(\d{1,2})\s*[\.、\)）．:：]\s*"),
    re.compile(r"^[（(](\d{1,2})[)）]\s*"),
    re.compile(r"^([一二三四五六七八九十]{1,3})\s*[、\.]\s*"),
    re.compile(r"^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫])\s*"),
]
_UNORDERED = re.compile(r"^[-*•·]\s+")
# 行首的 markdown 装饰，先剥掉再判断是不是列表项
_DECOR = re.compile(r"^[\s>#\*]+")


@dataclass
class Block:
    rank: int
    start: int
    end: int
    text: str


def split_ranked_blocks(text: str) -> List[Block]:
    """把回答切成"第 N 条推荐"的块。

    一条推荐往往是「标题行 + 下面几行说明」，所以按列表标记切块而不是按行切，
    这样"1. 新东方\n   老师经验丰富"里的品牌仍归属第 1 条。
    返回空列表表示这段回答不是清单式的。
    """
    if not text:
        return []

    starts: List[int] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = _DECOR.sub("", line).lstrip()
        lead = len(line) - len(stripped) if stripped else 0
        if stripped and any(p.match(stripped) for p in _ORDERED):
            starts.append(offset + lead)
        offset += len(line)

    if len(starts) < 2:  # 少于两条不算清单
        starts = []
        offset = 0
        for line in text.splitlines(keepends=True):
            stripped = _DECOR.sub("", line).lstrip()
            lead = len(line) - len(stripped) if stripped else 0
            if stripped and _UNORDERED.match(stripped):
                starts.append(offset + lead)
            offset += len(line)

    if len(starts) < 2:
        return []

    blocks: List[Block] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        blocks.append(Block(rank=i + 1, start=s, end=e, text=text[s:e]))
    return blocks


@dataclass
class RankResult:
    ranks: Dict[str, Optional[int]] = field(default_factory=dict)  # 品牌 -> 名次
    method: str = "none"                                          # list | order | none
    list_size: int = 0


def rank_brands(text: str, brands: List[Brand]) -> RankResult:
    """判断各品牌在回答的推荐清单中排第几。

    method=list  按有序/无序清单的条目序号；
    method=order 回答不是清单式的，退化为按首次出现位置排序；
    未被提及的品牌不出现在 ranks 里，提及但不在清单条目中的品牌记为 None。
    """
    mentions = find_all_mentions(text, brands)
    present = {name: ms for name, ms in mentions.items() if ms}
    if not present:
        return RankResult({}, "none", 0)

    blocks = split_ranked_blocks(text)
    if blocks:
        ranks: Dict[str, Optional[int]] = {}
        for name, ms in present.items():
            hit = None
            for b in blocks:
                if any(b.start <= m.start < b.end for m in ms):
                    hit = b.rank
                    break
            ranks[name] = hit
        # 清单里一个品牌都没匹配上（纯步骤说明型清单），退化为出现顺序
        if any(v is not None for v in ranks.values()):
            return RankResult(ranks, "list", len(blocks))

    ordered = sorted(present.items(), key=lambda kv: kv[1][0].start)
    ranks = {name: i + 1 for i, (name, _) in enumerate(ordered)}
    return RankResult(ranks, "order", len(ordered))


# ============================================================
# 3. 情感兜底打分（词典法）
# ============================================================

POSITIVE_WORDS = [
    "靠谱", "专业", "口碑好", "口碑较好", "效果显著", "提分", "优质", "经验丰富", "值得推荐",
    "知名", "老牌", "正规", "资质齐全", "上市公司", "性价比高", "服务好", "个性化", "因材施教",
    "认可", "满意", "优势明显", "实力较强", "全国连锁", "规范", "透明", "负责",
]
NEGATIVE_WORDS = [
    "退费难", "投诉", "纠纷", "跑路", "暴雷", "虚假宣传", "夸大", "价格偏高", "收费高", "偏贵",
    "参差不齐", "不建议", "谨慎", "风险", "差评", "套路", "隐形消费", "效果一般", "流失",
    "资质存疑", "无资质", "维权", "亏损", "退市",
]
NEGATION = ["不", "没有", "未", "谈不上", "算不上"]


def context_of(text: str, mentions: List[Mention], window: int = CONTEXT_WINDOW) -> str:
    """取所有提及点前后各 window 字，拼成情感分析用的上下文。"""
    if not mentions:
        return ""
    pieces, last_end = [], -1
    for m in mentions:
        s, e = max(0, m.start - window), min(len(text), m.end + window)
        if s <= last_end:           # 与上一段重叠则合并
            pieces[-1] = (pieces[-1][0], e)
        else:
            pieces.append((s, e))
        last_end = e
    return " …… ".join(text[s:e] for s, e in pieces)


def rule_sentiment(context: str) -> Tuple[float, List[str], List[str]]:
    """返回 (得分 -1~1, 命中的正面词, 命中的负面词)。"""
    if not context:
        return 0.0, [], []

    pos_hits, neg_hits = [], []
    for w in POSITIVE_WORDS:
        for m in re.finditer(re.escape(w), context):
            prefix = context[max(0, m.start() - 2):m.start()]
            (neg_hits if any(n in prefix for n in NEGATION) else pos_hits).append(w)
    for w in NEGATIVE_WORDS:
        if w in context:
            neg_hits.append(w)

    total = len(pos_hits) + len(neg_hits)
    if total == 0:
        return 0.0, [], []
    score = (len(pos_hits) - len(neg_hits)) / total
    return round(max(-1.0, min(1.0, score)), 3), pos_hits, neg_hits


def label_of(score: float, pos_th: float = 0.2, neg_th: float = -0.2) -> str:
    if score >= pos_th:
        return "正面"
    if score <= neg_th:
        return "负面"
    return "中性"
