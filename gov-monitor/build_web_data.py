#!/usr/bin/env python3
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / 'monitor_results.json'
ARCHIVE_DIR = ROOT / 'archive'
OUT = ROOT / 'web_data.json'


def normalize_source(url: str) -> str:
    if 'moe.gov.cn' in url: return '教育部'
    if 'beijing.gov.cn' in url: return '北京市政府'
    if 'cq.gov.cn' in url: return '重庆市政府'
    if 'bjwmb.gov.cn' in url: return '北京市委宣传部'
    if 'zj.gov.cn' in url: return '浙江省相关部门'
    if 'shhk.gov.cn' in url: return '虹口区教育局'
    return '政府网站'


def parse_items(raw_items):
    cleaned, cats, seen = [], {}, set()
    for item in raw_items:
        url = item.get('url') or ''
        title = (item.get('title') or '').strip()
        if not url or not title or url in seen:
            continue
        seen.add(url)
        raw_cat = item.get('category') or '未分类'
        if '/' in raw_cat:
            category, sub_category = raw_cat.split('/', 1)
        else:
            category, sub_category = raw_cat, ''
        cats[category] = cats.get(category, 0) + 1
        cleaned.append({
            'category': category,
            'subCategory': sub_category,
            'keyword': item.get('keyword', ''),
            'title': title,
            'source': normalize_source(url),
            'url': url,
            'date': (item.get('published_date') or '')[:10],
            'summary': (item.get('snippet') or '').replace('\n', ' ')[:120]
        })
    return cleaned, cats


def load_history(days=14):
    """Load last N days of archived daily summaries for trend chart."""
    history = []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime('%Y-%m-%d')
        archive_file = ARCHIVE_DIR / f'{date_str}.json'
        if archive_file.exists():
            data = json.loads(archive_file.read_text(encoding='utf-8'))
            history.append({'date': date_str, 'categories': data.get('categories', {}), 'total': data.get('total', 0)})
        else:
            history.append({'date': date_str, 'categories': {}, 'total': 0})
    return history


def archive_today(cats, total):
    """Save today's summary to archive."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    archive_file = ARCHIVE_DIR / f'{today}.json'
    archive_file.write_text(json.dumps({'date': today, 'total': total, 'categories': cats}, ensure_ascii=False), encoding='utf-8')


def main():
    if not RESULTS.exists():
        print('monitor_results.json not found')
        return 1

    items = json.loads(RESULTS.read_text(encoding='utf-8'))
    cleaned, cats = parse_items(items)

    archive_today(cats, len(cleaned))
    history = load_history(14)

    payload = {
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'summary': {'total': len(cleaned), 'categories': cats},
        'history': history,
        'items': cleaned,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'✅ wrote {OUT} (history: {len(history)} days)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
