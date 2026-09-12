#!/usr/bin/env python3
"""
情感裁判层

"正面反馈程度"如果只用关键词打分，会漏掉"虽然是好词但整体在劝退"这类表达，
所以主路径用一个裁判模型对**品牌相关片段**做结构化判定，词典法只作兜底。

裁判只看提及点前后的上下文，不看整篇回答，避免被无关段落带偏。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import Provider
from extractor import label_of, rule_sentiment
from llm_client import LLMClient

ASPECTS = ["师资", "效果", "价格", "服务", "规模", "资质合规", "品牌声誉"]

JUDGE_PROMPT = """你是品牌口碑分析员。下面是某个AI助手回答里与「{brand}」相关的片段。

请只针对「{brand}」这个品牌本身的评价倾向做判断，忽略与该品牌无关的内容。

片段：
\"\"\"
{context}
\"\"\"

请输出严格的 JSON（不要任何额外文字、不要代码块标记）：
{{
  "sentiment": "正面|中性|负面",
  "score": -1到1之间的小数（-1极负面，0中性，1极正面）,
  "aspects": ["涉及的维度，从 {aspects} 中选，可多选，没有则空数组"],
  "positive_points": ["被夸的点，简短短语，最多3条"],
  "negative_points": ["被质疑或吐槽的点，简短短语，最多3条"],
  "is_recommended": true/false（该回答是否把这个品牌作为推荐项）,
  "risk": true/false（是否出现退费纠纷、虚假宣传、无资质、暴雷等风险表述）
}}"""


@dataclass
class Verdict:
    sentiment: str = "中性"
    score: float = 0.0
    aspects: List[str] = field(default_factory=list)
    positive_points: List[str] = field(default_factory=list)
    negative_points: List[str] = field(default_factory=list)
    is_recommended: bool = False
    risk: bool = False
    source: str = "rule"       # llm | rule
    error: str = ""

    def to_dict(self) -> Dict:
        return {
            "sentiment": self.sentiment,
            "score": self.score,
            "aspects": self.aspects,
            "positive_points": self.positive_points,
            "negative_points": self.negative_points,
            "is_recommended": self.is_recommended,
            "risk": self.risk,
            "source": self.source,
            "error": self.error,
        }


def rule_verdict(context: str) -> Verdict:
    """词典兜底：LLM 裁判不可用或解析失败时使用。"""
    score, pos, neg = rule_sentiment(context)
    return Verdict(
        sentiment=label_of(score),
        score=score,
        positive_points=sorted(set(pos))[:3],
        negative_points=sorted(set(neg))[:3],
        is_recommended=any(w in context for w in ["推荐", "可以考虑", "值得", "不妨"]),
        risk=any(w in context for w in ["退费难", "投诉", "纠纷", "跑路", "暴雷", "虚假宣传", "无资质", "维权"]),
        source="rule",
    )


def _extract_json(raw: str) -> Optional[Dict]:
    """裁判有时会套 ```json 代码块或加前后缀，这里做宽松解析。"""
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


async def judge_context(client: LLMClient, judge_provider: Provider,
                        brand: str, context: str) -> Verdict:
    """对单个上下文片段做情感判定，失败自动回落到词典法。"""
    if not context.strip():
        return Verdict(source="rule")

    prompt = JUDGE_PROMPT.format(brand=brand, context=context[:2500],
                                 aspects="/".join(ASPECTS))
    result = await client.chat(judge_provider, prompt, temperature=0.0,
                               max_tokens=500,
                               system="你只输出 JSON，不输出任何解释性文字。")
    if not result.ok:
        v = rule_verdict(context)
        v.error = f"裁判调用失败({result.error[:80]})，已回落词典法"
        return v

    data = _extract_json(result.text)
    if not isinstance(data, dict) or "sentiment" not in data:
        v = rule_verdict(context)
        v.error = "裁判输出无法解析为 JSON，已回落词典法"
        return v

    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(-1.0, min(1.0, score))

    sentiment = str(data.get("sentiment", "")).strip()
    if sentiment not in ("正面", "中性", "负面"):
        sentiment = label_of(score)

    def _strs(key: str) -> List[str]:
        val = data.get(key) or []
        if isinstance(val, str):
            val = [val]
        return [str(x)[:40] for x in val if str(x).strip()][:3]

    return Verdict(
        sentiment=sentiment,
        score=round(score, 3),
        aspects=[a for a in _strs("aspects")],
        positive_points=_strs("positive_points"),
        negative_points=_strs("negative_points"),
        is_recommended=bool(data.get("is_recommended", False)),
        risk=bool(data.get("risk", False)),
        source="llm",
    )
