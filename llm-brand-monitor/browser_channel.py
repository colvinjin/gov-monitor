#!/usr/bin/env python3
"""
浏览器通道：直接问各家**网页版**，采集用户真实看到的回答

为什么要这条通道：真实用户用的是网页版和 App，默认联网检索；
API 默认不联网，提及率会明显偏低。接口层能开检索的模型走 monitor.py 即可，
开不了的（DeepSeek / Kimi / MiniMax 等）只能从网页版取。

工作方式：
  · 用**你自己的账号**，登录态保存在本地 profile 目录（.browser-profile/），只需登录一次
  · 每题开一个新会话，避免上一题的上下文影响下一题
  · 默认每题间隔 8 秒，节奏保守；不做任何验证码绕过

三步走：
  1. python browser_channel.py --login doubao      # 打开浏览器，手动登录一次
  2. python browser_channel.py --probe doubao      # 打印页面上的候选选择器，校准 sites.json
  3. python browser_channel.py --sites doubao,kimi --types category --repeats 2

⚠️ sites.json 里的选择器是初始猜测（verified=false），各家前端改版很频繁，
   第一次用请务必跑 --probe 校准，校准完把 verified 改成 true。
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config
from llm_client import LLMClient
from pipeline import build_record, console_line
from questions import Question, select

ROOT = Path(__file__).parent
SITES_FILE = ROOT / "sites.json"
RAW_DIR = ROOT / "data" / "raw"


def load_sites() -> Dict[str, Dict]:
    if not SITES_FILE.exists():
        raise FileNotFoundError(f"缺少站点配置 {SITES_FILE}")
    return {s["key"]: s for s in json.loads(SITES_FILE.read_text(encoding="utf-8"))["sites"]}


async def _launch(site: Dict, headless: bool):
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    profile = ROOT / config.BROWSER_PROFILE_DIR / site["key"]
    profile.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "user_data_dir": str(profile),
        "headless": headless,
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    }
    exe = os.getenv("PLAYWRIGHT_CHROMIUM_PATH", "").strip()
    if exe:
        kwargs["executable_path"] = exe
    ctx = await pw.chromium.launch_persistent_context(**kwargs)
    return pw, ctx


async def _first_matching(page, selectors: List[str], timeout_ms: int = 8000):
    """按顺序找第一个真实存在的选择器。"""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    return el, sel
            except Exception:
                continue
        await page.wait_for_timeout(300)
    return None, None


async def ask(page, site: Dict, question: str) -> Dict:
    """在网页版里问一个问题，等生成结束，取回答全文。"""
    started = time.time()
    await page.goto(site["url"], wait_until="domcontentloaded")
    await page.wait_for_timeout(int(site.get("boot_ms", 2500)))

    box, sel = await _first_matching(page, site["input_selectors"])
    if not box:
        return {"ok": False, "text": "", "error": f"找不到输入框，请用 --probe {site['key']} 校准选择器"}

    await box.click()
    await page.keyboard.type(question, delay=18)
    await page.wait_for_timeout(400)

    send, _ = await _first_matching(page, site.get("send_selectors", []), timeout_ms=1500)
    if send:
        await send.click()
    else:
        await page.keyboard.press("Enter")

    text = await _wait_answer(page, site)
    if not text:
        return {"ok": False, "text": "", "error": "等待回答超时或未取到正文（选择器可能已失效）"}
    return {"ok": True, "text": text, "error": "",
            "latency_ms": int((time.time() - started) * 1000)}


async def _wait_answer(page, site: Dict) -> str:
    """轮询最后一条回答，直到内容连续 stable_ms 不变，视为生成完毕。"""
    resp_sel = site["response_selector"]
    stable_ms = int(site.get("stable_ms", config.BROWSER_STABLE_MS))
    deadline = time.time() + float(site.get("timeout_s", config.BROWSER_TIMEOUT_S))

    last, changed_at = "", time.time()
    while time.time() < deadline:
        try:
            texts = await page.eval_on_selector_all(
                resp_sel, "els => els.map(e => e.innerText || '')")
        except Exception:
            texts = []
        cur = texts[-1].strip() if texts else ""
        if cur != last:
            last, changed_at = cur, time.time()
        elif cur and (time.time() - changed_at) * 1000 >= stable_ms:
            return cur
        await page.wait_for_timeout(500)
    return last


async def probe(site_key: str, headless: bool = False):
    """打印页面上的候选输入框 / 按钮 / 消息容器，用于校准 sites.json。"""
    site = load_sites()[site_key]
    pw, ctx = await _launch(site, headless)
    page = await ctx.new_page()
    await page.goto(site["url"], wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)

    js = """() => {
      const sig = el => {
        const id = el.id ? '#' + el.id : '';
        const cls = (el.className && typeof el.className === 'string')
          ? '.' + el.className.trim().split(/\\s+/).slice(0, 3).join('.') : '';
        const dt = el.getAttribute('data-testid');
        return {tag: el.tagName.toLowerCase(), sel: el.tagName.toLowerCase() + id + cls,
                testid: dt || '', text: (el.innerText || el.placeholder || '').slice(0, 30)};
      };
      const inputs = [...document.querySelectorAll('textarea,[contenteditable="true"],input[type=text]')].map(sig);
      const buttons = [...document.querySelectorAll('button,[role=button]')].slice(0, 25).map(sig);
      return {inputs, buttons, title: document.title, url: location.href};
    }"""
    info = await page.evaluate(js)
    print(f"\n页面: {info['title']}  {info['url']}")
    print("\n候选输入框（填到 input_selectors）:")
    for i in info["inputs"]:
        print(f"  {i['sel']}   data-testid={i['testid']!r}  {i['text']!r}")
    print("\n候选发送按钮（填到 send_selectors，留空则按回车发送）:")
    for b in info["buttons"]:
        print(f"  {b['sel']}   data-testid={b['testid']!r}  {b['text']!r}")
    print("\n👉 现在手动问一句话，等回答出来后回到终端按回车，我再抓一次消息容器")
    input()
    msgs = await page.evaluate("""() => {
      const cand = [...document.querySelectorAll('div,article,section')]
        .filter(e => (e.innerText || '').length > 80 && e.children.length < 40)
        .slice(-12)
        .map(e => {
          const cls = (e.className && typeof e.className === 'string')
            ? '.' + e.className.trim().split(/\\s+/).slice(0, 3).join('.') : '';
          return {sel: e.tagName.toLowerCase() + cls, len: (e.innerText||'').length,
                  head: (e.innerText||'').slice(0, 60)};
        });
      return cand;
    }""")
    print("\n候选回答容器（挑最贴合单条回答的填到 response_selector）:")
    for m in msgs:
        print(f"  {m['sel']}  len={m['len']}  {m['head']!r}")
    await ctx.close()
    await pw.stop()


async def login(site_key: str):
    site = load_sites()[site_key]
    pw, ctx = await _launch(site, headless=False)
    page = await ctx.new_page()
    await page.goto(site["url"], wait_until="domcontentloaded")
    print(f"\n已打开 {site['label']}，请在浏览器里完成登录。")
    print("登录完成后回到终端按回车，登录态会保存在本地 profile，后续无需重复登录。")
    input()
    await ctx.close()
    await pw.stop()
    print("✅ 登录态已保存")


async def collect(args) -> List[Dict]:
    sites_cfg = load_sites()
    keys = [k.strip() for k in args.sites.split(",") if k.strip()]
    unknown = [k for k in keys if k not in sites_cfg]
    if unknown:
        raise SystemExit(f"未知站点: {unknown}，可选: {list(sites_cfg)}")

    types = [t.strip() for t in args.types.split(",")] if args.types else None
    questions = select(types=types, limit=args.limit)

    judge_provider, use_judge = None, not args.no_judge
    if use_judge:
        try:
            judge_provider = config.pick_judge()
        except RuntimeError as e:
            print(f"⚠️  {e}，本次用词典法打分")
            use_judge = False

    print(f"\n{'='*64}")
    print(f"🌐 网页版采集  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   站点 {len(keys)} 个 × 问题 {len(questions)} 个 × 重复 {args.repeats} 次")
    print(f"   每题间隔 {args.pacing}s｜情感裁判 {judge_provider.label if judge_provider else '词典法'}")
    print(f"{'='*64}\n")

    records: List[Dict] = []
    async with LLMClient(concurrency=2) as client:
        for key in keys:
            site = sites_cfg[key]
            if not site.get("verified"):
                print(f"⚠️  {site['label']} 的选择器尚未校准（verified=false），"
                      f"失败请先跑 --probe {key}\n")
            pw, ctx = await _launch(site, args.headless)
            page = await ctx.new_page()
            try:
                for q in questions:
                    for r in range(1, args.repeats + 1):
                        res = await ask(page, site, q.text)
                        rec = await build_record(
                            question=q, answer=res["text"],
                            provider_key=f"{key}_web", provider_label=f"{site['label']}(网页版)",
                            model=site.get("model_label", "web"), repeat=r,
                            channel="browser", mode="web",
                            ok=res["ok"], error=res.get("error", ""),
                            latency_ms=res.get("latency_ms", 0),
                            client=client, judge_provider=judge_provider, use_judge=use_judge,
                            search_evidence=True,   # 网页版默认联网
                        )
                        records.append(rec)
                        print(console_line(rec))
                        await asyncio.sleep(args.pacing)
            finally:
                await ctx.close()
                await pw.stop()
    return records


def save(records: List[Dict]):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n💾 已追加 {len(records)} 条到 {out}")


def main():
    ap = argparse.ArgumentParser(description="网页版采集通道")
    ap.add_argument("--login", metavar="SITE", help="打开浏览器手动登录一次并保存登录态")
    ap.add_argument("--probe", metavar="SITE", help="打印页面候选选择器，用于校准 sites.json")
    ap.add_argument("--sites", default="", help="逗号分隔的站点 key")
    ap.add_argument("--types", default="category", help="问题类型，默认只跑品类问题")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--pacing", type=float, default=config.BROWSER_PACING_SECONDS,
                    help="每题之间的间隔秒数，别调太小")
    ap.add_argument("--headless", action="store_true", help="无头模式（更容易被风控，默认关闭）")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--list", action="store_true", help="列出已配置站点")
    args = ap.parse_args()

    if args.list:
        for k, s in load_sites().items():
            mark = "✅已校准" if s.get("verified") else "⚠️ 待校准"
            print(f"  {k:<12} {s['label']:<18} {mark}  {s['url']}")
        return 0
    if args.login:
        asyncio.run(login(args.login))
        return 0
    if args.probe:
        asyncio.run(probe(args.probe))
        return 0
    if not args.sites:
        print("请用 --sites 指定站点，或 --list 查看可选站点")
        return 1

    records = asyncio.run(collect(args))
    if records:
        save(records)
        import report
        report.build(datetime.now().strftime("%Y-%m-%d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
