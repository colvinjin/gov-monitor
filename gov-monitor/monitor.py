#!/usr/bin/env python3
"""
政府网站监测脚本
每天自动抓取重点政府网站的最新动态，匹配关键词后更新到飞书文档
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
import time
from typing import List, Dict, Optional

# 关键词配置
KEYWORDS = {
    # 教育类 - 子分类
    "教育类/校外培训": [
        "学科类培训", "校外培训", "培训机构", "双减政策", "课后服务", "民办教育", "教育机构"
    ],
    "教育类/基础教育": [
        "基础教育", "素质教育", "公益教育", "教育帮扶", "义务教育", "学前教育"
    ],
    "教育类/职业教育": [
        "职业教育", "职业技能", "职业培训", "技工院校", "产教融合"
    ],
    "教育类/教育AI": [
        "教育数字化", "AI+教育", "人工智能教育", "智慧教育", "教育大模型"
    ],
    # 阅读文化类 - 子分类
    "阅读文化类/实体书店": [
        "实体书店", "书店", "新华书店", "独立书店"
    ],
    "阅读文化类/书香校园": [
        "书香校园", "校园阅读", "图书角"
    ],
    "阅读文化类/亲子阅读": [
        "亲子阅读", "家庭阅读", "亲子共读"
    ],
    "阅读文化类/阅读推广": [
        "全民阅读", "阅读推广", "青少年阅读", "数字阅读", "世界读书日"
    ],
    "阅读文化类/分级阅读": [
        "分级阅读", "阶梯阅读", "儿童阅读分级"
    ],
    # 医教融合
    "医教融合/孤独症": [
        "孤独症", "自闭症", "ASD", "谱系障碍"
    ],
    "医教融合/ADHD": [
        "ADHD", "注意缺陷", "多动症", "注意力障碍"
    ],
    "医教融合/心理健康": [
        "心理健康", "学生心理", "心理援助", "心理教育", "青少年心理"
    ],
    # 新兴产业
    "新兴产业/低空经济": [
        "低空经济", "eVTOL", "无人机", "低空飞行", "通用航空"
    ],
    "新兴产业/具身智能": [
        "具身智能", "人形机器人", "机器人", "智能机器人"
    ],
    "新兴产业/人工智能": [
        "人工智能", "大模型", "生成式AI", "AI治理", "算法"
    ],
    "新兴产业/算力": [
        "算力", "智算中心", "算力网络", "GPU", "算力基础设施"
    ],
}

# 监测网站配置
WEBSITES = {
    "中央部委": [
        {"name": "教育部", "url": "http://www.moe.gov.cn/", "list_selector": ".news_list li"},
        {"name": "中央宣传部", "url": "http://www.ccppg.com.cn/", "list_selector": ".news_list li"},
        {"name": "文化和旅游部", "url": "https://www.mct.gov.cn/", "list_selector": ".news_list li"},
        {"name": "科技部", "url": "https://www.most.gov.cn/", "list_selector": ".news_list li"},
        {"name": "工信部", "url": "https://www.miit.gov.cn/", "list_selector": ".news_list li"},
        {"name": "发改委", "url": "https://www.ndrc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "民政部", "url": "https://www.mca.gov.cn/", "list_selector": ".news_list li"},
        {"name": "全国妇联", "url": "http://www.women.org.cn/", "list_selector": ".news_list li"},
        {"name": "国家卫健委", "url": "http://www.nhc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "国家残联", "url": "http://www.cdpf.org.cn/", "list_selector": ".news_list li"},
    ],
    "省市教育厅": [
        {"name": "北京市教委", "url": "http://jw.beijing.gov.cn/", "list_selector": ".news_list li"},
        {"name": "上海市教委", "url": "http://edu.sh.gov.cn/", "list_selector": ".news_list li"},
        {"name": "广东省教育厅", "url": "http://edu.gd.gov.cn/", "list_selector": ".news_list li"},
        {"name": "浙江省教育厅", "url": "http://edu.zj.gov.cn/", "list_selector": ".news_list li"},
        {"name": "江苏省教育厅", "url": "http://jyt.jiangsu.gov.cn/", "list_selector": ".news_list li"},
        {"name": "四川省教育厅", "url": "http://edu.sc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "湖北省教育厅", "url": "http://jyt.hubei.gov.cn/", "list_selector": ".news_list li"},
        {"name": "湖南省教育厅", "url": "http://jyt.hunan.gov.cn/", "list_selector": ".news_list li"},
    ],
    "句象书店城市": [
        {"name": "北京市委宣传部", "url": "https://www.bjwmb.gov.cn/", "list_selector": ".news_list li"},
        {"name": "北京文旅局", "url": "https://whlyj.beijing.gov.cn/", "list_selector": ".news_list li"},
        {"name": "上海市委宣传部", "url": "https://www.shxc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "上海文旅局", "url": "https://wgj.sh.gov.cn/", "list_selector": ".news_list li"},
        {"name": "深圳市委宣传部", "url": "http://www.sznews.com/", "list_selector": ".news_list li"},
        {"name": "深圳文旅局", "url": "http://wgj.sz.gov.cn/", "list_selector": ".news_list li"},
        {"name": "武汉市委宣传部", "url": "http://www.whxc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "武汉文旅局", "url": "http://wlj.wuhan.gov.cn/", "list_selector": ".news_list li"},
        {"name": "长沙市委宣传部", "url": "http://www.csxc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "长沙文旅局", "url": "http://wlgd.changsha.gov.cn/", "list_selector": ".news_list li"},
        {"name": "成都市委宣传部", "url": "http://www.cdxc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "成都文旅局", "url": "http://wgj.chengdu.gov.cn/", "list_selector": ".news_list li"},
        {"name": "青岛市委宣传部", "url": "http://www.qdxc.gov.cn/", "list_selector": ".news_list li"},
        {"name": "青岛文旅局", "url": "http://wgj.qingdao.gov.cn/", "list_selector": ".news_list li"},
    ]
}


class GovMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.results = []

    def fetch_page(self, url: str, timeout: int = 10) -> Optional[str]:
        """抓取网页内容"""
        try:
            response = self.session.get(url, timeout=timeout)
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            print(f"❌ 抓取失败 {url}: {e}")
            return None

    def extract_news(self, html: str, selector: str) -> List[Dict]:
        """从HTML中提取新闻列表"""
        soup = BeautifulSoup(html, 'html.parser')
        news_items = []
        
        try:
            items = soup.select(selector)
            for item in items[:10]:  # 只取最新10条
                title_elem = item.find('a')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    date_elem = item.find(class_=re.compile('date|time'))
                    date = date_elem.get_text(strip=True) if date_elem else ''
                    
                    news_items.append({
                        'title': title,
                        'link': link,
                        'date': date
                    })
        except Exception as e:
            print(f"⚠️  解析新闻列表失败: {e}")
        
        return news_items

    def match_keywords(self, text: str) -> List[str]:
        """匹配关键词"""
        matched = []
        for category, keywords in KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    matched.append(f"{category}:{keyword}")
        return matched

    def monitor_website(self, site: Dict) -> List[Dict]:
        """监测单个网站"""
        print(f"🔍 正在监测: {site['name']}")
        
        html = self.fetch_page(site['url'])
        if not html:
            return []
        
        news_list = self.extract_news(html, site['list_selector'])
        matched_news = []
        
        for news in news_list:
            keywords = self.match_keywords(news['title'])
            if keywords:
                matched_news.append({
                    'source': site['name'],
                    'title': news['title'],
                    'link': news['link'],
                    'date': news['date'],
                    'keywords': keywords,
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"  ✅ 匹配: {news['title'][:50]}... [{', '.join(keywords)}]")
        
        return matched_news

    def run(self):
        """执行监测任务"""
        print(f"\n{'='*60}")
        print(f"🚀 开始政府网站监测 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        for category, sites in WEBSITES.items():
            print(f"\n📂 {category}")
            for site in sites:
                matched = self.monitor_website(site)
                self.results.extend(matched)
                time.sleep(1)  # 避免请求过快
        
        print(f"\n{'='*60}")
        print(f"✅ 监测完成，共发现 {len(self.results)} 条相关信息")
        print(f"{'='*60}\n")
        
        return self.results

    def save_results(self, filename: str = 'monitor_results.json'):
        """保存结果到JSON文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到: {filename}")


def main():
    monitor = GovMonitor()
    results = monitor.run()
    
    if results:
        monitor.save_results()
        
        # 打印摘要
        print("\n📊 监测摘要:")
        by_source = {}
        for item in results:
            source = item['source']
            by_source[source] = by_source.get(source, 0) + 1
        
        for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {source}: {count}条")


if __name__ == '__main__':
    main()
