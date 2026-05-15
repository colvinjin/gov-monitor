#!/usr/bin/env python3
"""
政府网站监测脚本 v2 - 使用 Tavily 搜索 API
通过搜索引擎定向抓取政府网站最新动态，避免直接解析网页结构
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# 关键词配置（格式：大类/子类）
KEYWORDS = {
    "教育类/校外培训": ["学科类培训", "校外培训", "培训机构", "双减政策", "课后服务", "民办教育", "教育机构"],
    "教育类/基础教育": ["基础教育", "素质教育", "公益教育", "教育帮扶", "义务教育", "学前教育"],
    "教育类/职业教育": ["职业教育", "职业技能", "职业培训", "技工院校", "产教融合"],
    "教育类/教育AI": ["教育数字化", "AI+教育", "人工智能教育", "智慧教育", "教育大模型"],
    "阅读文化类/实体书店": ["实体书店", "书店", "新华书店", "独立书店"],
    "阅读文化类/书香校园": ["书香校园", "校园阅读", "图书角"],
    "阅读文化类/亲子阅读": ["亲子阅读", "家庭阅读", "亲子共读"],
    "阅读文化类/阅读推广": ["全民阅读", "阅读推广", "青少年阅读", "数字阅读", "世界读书日"],
    "阅读文化类/分级阅读": ["分级阅读", "阶梯阅读", "儿童阅读分级"],
    "医教融合/孤独症": ["孤独症", "自闭症", "ASD", "谱系障碍"],
    "医教融合/ADHD": ["ADHD", "注意缺陷", "多动症", "注意力障碍"],
    "医教融合/心理健康": ["心理健康", "学生心理", "心理援助", "心理教育", "青少年心理"],
    "新兴产业/低空经济": ["低空经济", "eVTOL", "无人机", "低空飞行", "通用航空"],
    "新兴产业/具身智能": ["具身智能", "人形机器人", "机器人", "智能机器人"],
    "新兴产业/人工智能": ["人工智能", "大模型", "生成式AI", "AI治理", "算法"],
    "新兴产业/算力": ["算力", "智算中心", "算力网络", "GPU", "算力基础设施"],
}

# 监测网站域名
DOMAINS = [
    # 中央部委
    "moe.gov.cn",        # 教育部
    "ccppg.com.cn",      # 中央宣传部
    "mct.gov.cn",        # 文旅部
    "most.gov.cn",       # 科技部
    "miit.gov.cn",       # 工信部
    "ndrc.gov.cn",       # 发改委
    "mca.gov.cn",        # 民政部
    "women.org.cn",      # 妇联
    "nhc.gov.cn",        # 国家卫健委
    "cdpf.org.cn",       # 国家残联
    # 省市教育厅
    "jw.beijing.gov.cn", # 北京教委
    "edu.sh.gov.cn",     # 上海教委
    "edu.gd.gov.cn",     # 广东教育厅
    "edu.zj.gov.cn",     # 浙江教育厅
    "jyt.jiangsu.gov.cn",# 江苏教育厅
    "edu.sc.gov.cn",     # 四川教育厅
    "jyt.hubei.gov.cn",  # 湖北教育厅
    "jyt.hunan.gov.cn",  # 湖南教育厅
    # 句象书店城市
    "bjwmb.gov.cn",      # 北京宣传部
    "whlyj.beijing.gov.cn", # 北京文旅
    "shxc.gov.cn",       # 上海宣传部
    "wgj.sh.gov.cn",     # 上海文旅
    "wgj.sz.gov.cn",     # 深圳文旅
    "wlj.wuhan.gov.cn",  # 武汉文旅
    "wlgd.changsha.gov.cn", # 长沙文旅
    "wgj.chengdu.gov.cn",# 成都文旅
    "qdxc.gov.cn",       # 青岛宣传部
    "wgj.qingdao.gov.cn",# 青岛文旅
]


class GovMonitorV2:
    def __init__(self):
        self.results = []
        self.workspace = Path(__file__).parent

    def search_with_tavily(self, query: str, domain: str = None) -> List[Dict]:
        """使用 Tavily 搜索"""
        cmd = ["openclaw", "tavily", "search", query, "--max-results", "5"]
        if domain:
            cmd.extend(["--include-domains", domain])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # 解析 JSON 输出
                data = json.loads(result.stdout)
                return data.get('results', [])
        except Exception as e:
            print(f"⚠️  搜索失败 [{query}]: {e}")
        
        return []

    def monitor_keyword(self, keyword: str, category: str):
        """监测单个关键词"""
        print(f"🔍 搜索关键词: {keyword} ({category})")
        
        # 搜索最近一周的内容
        query = f"{keyword} site:gov.cn"
        results = self.search_with_tavily(query)
        
        for item in results:
            # 检查是否在监测域名列表中
            url = item.get('url', '')
            if any(domain in url for domain in DOMAINS):
                self.results.append({
                    'category': category,
                    'keyword': keyword,
                    'title': item.get('title', ''),
                    'url': url,
                    'snippet': item.get('content', '')[:200],
                    'published_date': item.get('published_date', ''),
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"  ✅ {item.get('title', '')[:50]}...")

    def run(self):
        """执行监测任务"""
        print(f"\n{'='*60}")
        print(f"🚀 开始政府网站监测 (Tavily版) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        for category, keywords in KEYWORDS.items():
            print(f"\n📂 {category}")
            for keyword in keywords:
                self.monitor_keyword(keyword, category)
        
        print(f"\n{'='*60}")
        print(f"✅ 监测完成，共发现 {len(self.results)} 条相关信息")
        print(f"{'='*60}\n")
        
        return self.results

    def save_results(self):
        """保存结果"""
        output_file = self.workspace / 'monitor_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: {output_file}")

    def print_summary(self):
        """打印摘要"""
        if not self.results:
            print("\n📊 今日无匹配动态")
            return
        
        print("\n📊 监测摘要:")
        by_category = {}
        for item in self.results:
            cat = item['category']
            by_category[cat] = by_category.get(cat, 0) + 1
        
        for cat, count in by_category.items():
            print(f"  • {cat}: {count}条")


def main():
    monitor = GovMonitorV2()
    monitor.run()
    monitor.save_results()
    monitor.print_summary()


if __name__ == '__main__':
    main()
