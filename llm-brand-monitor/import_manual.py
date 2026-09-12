#!/usr/bin/env python3
"""
人工采集通道：把 App 里问到的回答贴回来，走同一套指标流水线

手机 App（豆包、元宝、Kimi、通义…）没法自动化，但 App 恰恰是用户量最大的入口。
这条通道让人工采集的成本降到最低：生成模板 → 在 App 里逐题问、粘贴回答 → 一条命令入库。

它同时是**校准基准**：同一批问题分别用 App 人工采一次、API 自动采一次，
就能算出两个渠道的差值，之后用 API 做高频监测、用 App 做低频校准。

用法：
    python import_manual.py --template --provider doubao_app --label 豆包App
    # → 生成 data/manual/2026-09-12_doubao_app.md，在 App 里逐题问并粘贴回答

    python import_manual.py data/manual/2026-09-12_doubao_app.md
"""

import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import config
from llm_client import LLMClient
from pipeline import build_record, console_line
from questions import QUESTIONS, select

ROOT = Path(__file__).parent
MANUAL_DIR = ROOT / "data" / "manual"
RAW_DIR = ROOT / "data" / "raw"
PLACEHOLDER = "<在这里粘贴回答，原文照贴，不要删改>"

HEADER = """# 学大教育 · 大模型可见度人工采集模板
# 采集渠道: {label}    渠道标识: {provider}    日期: {date}
#
# 用法：
#   1. 在 {label} 里**逐题**提问（每题开一个新对话，避免上下文串味）
#   2. 把回答原文完整粘贴到对应问题下方，替换掉占位行
#   3. 没问的题保留占位行即可，会自动跳过
#   4. 保存后运行: python import_manual.py {path}
#
# 注意：原文照贴，不要概括、不要删掉推荐顺序，排名指标依赖原始顺序。
"""


def template(provider: str, label: str, types: List[str], limit: int) -> Path:
    date = datetime.now().strftime("%Y-%m-%d")
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    path = MANUAL_DIR / f"{date}_{provider}.md"

    qs = select(types=types, limit=limit)
    body = [HEADER.format(label=label, provider=provider, date=date, path=path)]
    for q in qs:
        body.append(f"\n## {q.id} | {q.text}\n\n{PLACEHOLDER}\n")
    path.write_text("\n".join(body), encoding="utf-8")
    print(f"✅ 模板已生成: {path}（{len(qs)} 题）")
    print(f"   在 {label} 里逐题提问并粘贴回答，然后运行:")
    print(f"   python import_manual.py {path}")
    return path


def parse(path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """解析模板，返回 {question_id: 回答} 和文件头里的元信息。"""
    text = path.read_text(encoding="utf-8")

    meta = {}
    m = re.search(r"^#\s*采集渠道:\s*(\S+)\s+渠道标识:\s*(\S+)\s+日期:\s*(\S+)", text, re.MULTILINE)
    if m:
        meta = {"label": m.group(1), "provider": m.group(2), "date": m.group(3)}

    answers: Dict[str, str] = {}
    current, buf = None, []
    for line in text.splitlines():
        hit = re.match(r"^##\s+(\S+)\s*\|", line)
        if hit:
            if current:
                answers[current] = "\n".join(buf).strip()
            current, buf = hit.group(1), []
        elif current is not None:
            buf.append(line)
    if current:
        answers[current] = "\n".join(buf).strip()

    # 去掉未填写的占位
    return {k: v for k, v in answers.items()
            if v and PLACEHOLDER not in v and len(v) > 10}, meta


async def build(answers: Dict[str, str], provider: str, label: str, no_judge: bool) -> List[Dict]:
    by_id = {q.id: q for q in QUESTIONS}
    unknown = [k for k in answers if k not in by_id]
    if unknown:
        print(f"⚠️  忽略未知问题编号: {unknown}")

    judge_provider, use_judge = None, not no_judge
    if use_judge:
        try:
            judge_provider = config.pick_judge()
        except RuntimeError as e:
            print(f"⚠️  {e}，本次用词典法打分")
            use_judge = False

    records = []
    async with LLMClient(concurrency=3) as client:
        for qid, answer in answers.items():
            if qid not in by_id:
                continue
            rec = await build_record(
                question=by_id[qid], answer=answer,
                provider_key=provider, provider_label=label,
                model="app", repeat=1, channel="manual", mode="web",
                client=client, judge_provider=judge_provider, use_judge=use_judge,
                search_evidence=True,   # App 默认联网
            )
            records.append(rec)
            print(console_line(rec))
    return records


def save(records: List[Dict]):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with out.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n💾 已追加 {len(records)} 条到 {out}")


def main():
    ap = argparse.ArgumentParser(description="人工采集导入")
    ap.add_argument("file", nargs="?", help="填好的模板文件")
    ap.add_argument("--template", action="store_true", help="生成空白模板")
    ap.add_argument("--provider", default="app", help="渠道标识，如 doubao_app")
    ap.add_argument("--label", default="", help="渠道展示名，如 豆包App")
    ap.add_argument("--types", default="category", help="模板包含的问题类型")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    if args.template:
        types = [t.strip() for t in args.types.split(",")] if args.types else None
        template(args.provider, args.label or args.provider, types, args.limit)
        return 0

    if not args.file:
        ap.error("请给出模板文件路径，或用 --template 生成模板")

    path = Path(args.file)
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        return 1

    answers, meta = parse(path)
    if not answers:
        print("❌ 没解析到任何回答，请确认已把回答粘贴到 `## 问题编号` 下方")
        return 1

    provider = args.provider if args.provider != "app" else meta.get("provider", "app")
    label = args.label or meta.get("label", provider)
    print(f"\n📥 导入 {label}（{provider}）的 {len(answers)} 条回答\n")

    records = asyncio.run(build(answers, provider, label, args.no_judge))
    save(records)

    if not args.no_report:
        import report
        report.build(datetime.now().strftime("%Y-%m-%d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
