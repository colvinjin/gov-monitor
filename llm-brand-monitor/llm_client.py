#!/usr/bin/env python3
"""
统一大模型调用层

国内主流模型基本都提供 OpenAI 兼容的 /chat/completions，所以一套客户端全覆盖，
新增模型只要在 config.PROVIDERS 里加一行即可。

另外提供 mock provider：不需要任何 API Key 就能跑通全流程（--dry-run），
用于验证指标口径和看板渲染。
"""

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import httpx

from config import MAX_RETRIES, MAX_TOKENS, SYSTEM_PROMPT, TEMPERATURE, Provider


@dataclass
class ChatResult:
    provider: str
    model: str
    ok: bool
    text: str = ""
    error: str = ""
    latency_ms: int = 0
    usage: Dict = field(default_factory=dict)


class LLMClient:
    def __init__(self, concurrency: int = 4):
        self._sem = asyncio.Semaphore(concurrency)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(180.0))
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()

    async def chat(self, provider: Provider, prompt: str,
                   temperature: float = TEMPERATURE,
                   max_tokens: int = MAX_TOKENS,
                   system: str = SYSTEM_PROMPT) -> ChatResult:
        if provider.key == "mock":
            return mock_answer(prompt)

        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        payload.update(provider.extra_body or {})
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{provider.base_url.rstrip('/')}/chat/completions"

        last_err = ""
        async with self._sem:
            for attempt in range(MAX_RETRIES):
                started = time.time()
                try:
                    resp = await self._client.post(
                        url, headers=headers, json=payload, timeout=provider.timeout
                    )
                    latency = int((time.time() - started) * 1000)
                    if resp.status_code == 200:
                        text, usage = _parse_openai_response(resp.json())
                        if text:
                            return ChatResult(provider.key, provider.model, True,
                                              text=text, latency_ms=latency, usage=usage)
                        last_err = "响应中未取到正文"
                    else:
                        last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        if resp.status_code in (400, 401, 403, 404):
                            break  # 配置类错误，重试无意义
                except Exception as e:  # 网络波动 / 超时
                    last_err = f"{type(e).__name__}: {e}"

                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt + random.random())

        return ChatResult(provider.key, provider.model, False, error=last_err)


def _parse_openai_response(data: Dict) -> Tuple[str, Dict]:
    """兼容各家差异：content 可能为空而内容在 reasoning_content 里。"""
    usage = data.get("usage") or {}
    choices = data.get("choices") or []
    if not choices:
        return "", usage
    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        text = (message.get("reasoning_content") or "").strip()
    if not text:
        text = (choices[0].get("text") or "").strip()
    return text, usage


# ============================================================
# 离线 mock：让整条流水线在没有 API Key 时也能跑通
# ============================================================

MOCK_ANSWERS = [
    """国内做中小学一对一辅导的机构，比较有代表性的有这几家：

1. 学大教育：老牌个性化教育机构，全国有几百个学习中心，一对一起家，学情诊断和个性化方案做得比较系统，师资以全职教师为主，口碑总体不错。
2. 新东方：综合实力强，品牌知名度高，网点多，一对一和班课都有。
3. 精锐教育：主打高端一对一，价格偏高。
4. 京翰教育：一对一辅导老牌机构，在北京等城市有布局。

建议家长实地考察，确认机构办学资质后再报名。""",
    """给你几个方向的建议：

- 新东方：品牌大、师资稳定，适合大多数家庭。
- 学而思（好未来）：教研体系强，理科见长。
- 学大教育：个性化一对一是强项，会先做学情测评再定方案，适合偏科明显的孩子。
- 掌门1对1：线上为主，时间灵活。

选择时重点看老师匹配度和退费条款。""",
    """高中数学想提分，可以考虑这些正规机构：

1. 新东方
2. 学而思培优
3. 精锐教育

另外，各地也有一些本地机构口碑不错。注意核实办学许可证，警惕预付费过多的情况。""",
    """学大教育是国内较早做个性化一对一辅导的机构，母公司为紫光学大（A股上市公司）。

优势：
- 一对一个性化教学经验丰富，先测评后定方案；
- 全职教师比例较高，教学管理相对规范；
- 全国网点多，线下服务覆盖广。

不足：
- 一对一模式收费相对偏高；
- 不同城市校区的师资水平存在差异。

总体口碑正面，报名前建议试听并看清退费条款。""",
    """教学大纲里并没有规定必须补课。学大概率不是唯一选择，家长可以先评估孩子的实际需求，
再考虑是否报班。如果确实需要，建议选择有办学资质的正规机构。""",
]


def mock_answer(prompt: str) -> ChatResult:
    """按 prompt 哈希稳定取一条 mock 回答，保证 --dry-run 结果可复现。"""
    idx = int(hashlib.md5(prompt.encode("utf-8")).hexdigest(), 16) % len(MOCK_ANSWERS)
    return ChatResult("mock", "mock-1", True, text=MOCK_ANSWERS[idx], latency_ms=1)


MOCK_PROVIDER = Provider(
    key="mock", label="Mock(离线自测)",
    base_url="", default_model="mock-1", api_key_env="MOCK_API_KEY",
    note="不调用真实 API，用于验证流水线",
)


async def _selftest():
    """python llm_client.py 会对每个已配置的模型打一次连通性测试。"""
    from config import available_providers

    providers = available_providers()
    if not providers:
        print("未检测到任何已配置的模型 API Key，请参考 .env.example 配置")
        return
    async with LLMClient(concurrency=len(providers)) as client:
        results = await asyncio.gather(*[
            client.chat(p, "你好，请用一句话介绍你自己。", max_tokens=100) for p in providers
        ])
    for p, r in zip(providers, results):
        flag = "✅" if r.ok else "❌"
        detail = (r.text[:40].replace("\n", " ") if r.ok else r.error[:80])
        print(f"{flag} {p.label:<16} {p.model:<28} {r.latency_ms:>6}ms  {detail}")


if __name__ == "__main__":
    asyncio.run(_selftest())
