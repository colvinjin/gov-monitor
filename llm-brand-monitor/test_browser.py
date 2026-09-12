#!/usr/bin/env python3
"""
浏览器通道驱动的端到端测试

不碰任何真实站点：起一个本地 HTTP 服务，用 testdata/fake_chat.html 模拟
「输入框 + 发送按钮 + 逐字流式输出」的聊天页，验证 browser_channel.ask()
能正确输入、发送、等到生成结束、抓回完整正文（不被截断在流式中途）。

    python test_browser.py
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
PORT = 8123
PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {extra}")


FAKE_SITE = {
    "key": "faketest",
    "label": "FakeChat",
    "url": f"http://127.0.0.1:{PORT}/testdata/fake_chat.html",
    "input_selectors": ["div[data-testid='chat-input']", "textarea"],
    "send_selectors": ["button[data-testid='send-btn']"],
    "response_selector": "div.msg-assistant",
    "boot_ms": 300,
    "stable_ms": 1200,
    "timeout_s": 30,
    "verified": True,
}


async def main():
    import browser_channel
    from extractor import find_mentions, rank_brands
    from config import BRAND, all_brands

    pw, ctx = await browser_channel._launch(FAKE_SITE, headless=True)
    page = await ctx.new_page()
    try:
        print("\n[1] 驱动逻辑")
        res = await browser_channel.ask(page, FAKE_SITE, "国内一对一辅导机构有哪些？")
        check("成功取回回答", res["ok"], res.get("error", ""))
        text = res["text"]
        check("等到生成结束，正文未被截断",
              text.endswith("建议实地考察并核实办学资质。"), f"tail={text[-20:]!r}")
        check("抓到的是回答而不是提问", "新东方" in text and "国内一对一辅导机构有哪些" not in text)
        check("耗时记录合理", 1000 < res["latency_ms"] < 40000, f"{res['latency_ms']}ms")

        print("\n[2] 抓回的内容能正常进入指标流水线")
        check("识别到学大教育", len(find_mentions(text, BRAND)) == 1)
        r = rank_brands(text, all_brands())
        check("学大排第 2", r.ranks.get("学大教育") == 2, f"actual={r.ranks}")

        print("\n[3] 选择器失效时能明确报错")
        bad = dict(FAKE_SITE, input_selectors=["textarea#nonexistent"], send_selectors=[])
        res2 = await browser_channel.ask(page, bad, "测试")
        check("报出需要校准选择器", not res2["ok"] and "校准" in res2["error"], res2.get("error", ""))
    finally:
        await ctx.close()
        await pw.stop()


if __name__ == "__main__":
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("跳过：未安装 playwright（pip install playwright && playwright install chromium）")
        sys.exit(0)

    server = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        asyncio.run(main())
    finally:
        server.terminate()
    print(f"\n{'='*50}\n通过 {PASS}  失败 {FAIL}\n{'='*50}")
    sys.exit(1 if FAIL else 0)
