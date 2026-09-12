#!/usr/bin/env python3
"""
监测问题集（Prompt Set）

三类问题对应三类指标，不要混用口径：

- category  品类推荐类：问题里**不出现任何品牌词**，用来算「提及率 / 首位率 / 平均排名」。
            这是最核心的一类，衡量"用户不知道学大时，模型会不会主动推荐学大"。
- brand     品牌问询类：问题里点名学大，用来算「正面反馈程度 / 风险舆情」。
            提及率在这类问题上恒等于 1，因此**不计入提及率**。
- compare   竞品对比类：用来算「声量份额 SOV」和对比语境下的优劣势归因。

新增问题时请标好 type，报表会按 type 分开统计。
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Question:
    id: str
    text: str
    type: str        # category | brand | compare
    scene: str       # 场景标签，便于下钻


QUESTIONS: List[Question] = [
    # ---------- 一、品类推荐类（算提及率 / 首位率） ----------
    Question("cat_01", "国内比较靠谱的中小学一对一辅导机构有哪些？请推荐几家。", "category", "全国·一对一"),
    Question("cat_02", "高中数学成绩差，想找个性化辅导，有哪些正规的教育机构推荐？", "category", "学科·高中数学"),
    Question("cat_03", "孩子高三了想冲刺提分，一对一补课机构选哪家比较好？", "category", "学段·高考冲刺"),
    Question("cat_04", "北京有哪些知名的中小学课外辅导机构？", "category", "城市·北京"),
    Question("cat_05", "上海比较好的高中一对一补习机构有哪些？", "category", "城市·上海"),
    Question("cat_06", "广州、深圳一带口碑不错的中学生辅导机构推荐一下。", "category", "城市·广深"),
    Question("cat_07", "成都的高考文化课培训机构哪几家比较正规？", "category", "城市·成都"),
    Question("cat_08", "武汉初中生补课，有哪些有办学资质的培训机构？", "category", "城市·武汉"),
    Question("cat_09", "西安有哪些做个性化一对一辅导的教育品牌？", "category", "城市·西安"),
    Question("cat_10", "全国性的K12教育培训上市公司有哪些？", "category", "行业·上市公司"),
    Question("cat_11", "艺考生文化课冲刺，哪些机构做得比较专业？", "category", "细分·艺考文化课"),
    Question("cat_12", "初三中考冲刺一对一，家长一般会选哪些机构？", "category", "学段·中考"),
    Question("cat_13", "孩子偏科严重，有没有做个性化教学方案的辅导机构推荐？", "category", "需求·个性化"),
    Question("cat_14", "双减之后还在合规经营的高中学科培训机构有哪些？", "category", "政策·合规"),
    Question("cat_15", "有没有专门做高中全日制补习的正规学校或机构？", "category", "细分·全日制"),
    Question("cat_16", "想给孩子找一对一家教，机构类和个人老师相比怎么选？有推荐的机构吗？", "category", "需求·选择建议"),
    Question("cat_17", "国内做学习能力测评和学情诊断比较专业的教育机构有哪些？", "category", "细分·学情诊断"),
    Question("cat_18", "有哪些教育机构在做AI个性化学习或智慧教育产品？", "category", "细分·教育AI"),
    Question("cat_19", "面向孤独症、ADHD等特殊需求孩子的教育支持机构有哪些？", "category", "细分·医教融合"),
    Question("cat_20", "职业教育和升学规划做得比较好的教育集团有哪些？", "category", "细分·职教升学"),

    # ---------- 二、品牌问询类（算正面反馈程度 / 风险舆情） ----------
    Question("brd_01", "学大教育怎么样？值得选吗？", "brand", "口碑·总体"),
    Question("brd_02", "学大教育的一对一辅导效果好不好？", "brand", "口碑·效果"),
    Question("brd_03", "学大教育的师资力量如何？老师是全职的吗？", "brand", "口碑·师资"),
    Question("brd_04", "学大教育收费贵吗？大概什么价位？", "brand", "口碑·价格"),
    Question("brd_05", "学大教育是正规机构吗？有没有办学资质？", "brand", "口碑·合规"),
    Question("brd_06", "学大教育有哪些优势和不足？", "brand", "口碑·优劣势"),
    Question("brd_07", "在学大教育报名后可以退费吗？家长反馈如何？", "brand", "风险·退费"),
    Question("brd_08", "介绍一下学大教育这家公司的发展历程和业务布局。", "brand", "认知·公司"),
    Question("brd_09", "学大教育（紫光学大）目前的经营状况怎么样？", "brand", "认知·经营"),
    Question("brd_10", "学大教育在个性化教育领域有什么特色做法？", "brand", "认知·特色"),

    # ---------- 三、竞品对比类（算 SOV / 归因） ----------
    Question("cmp_01", "学大教育和新东方相比，哪个更适合高中一对一辅导？", "compare", "对比·新东方"),
    Question("cmp_02", "学大教育和学而思（好未来）有什么区别？", "compare", "对比·学而思"),
    Question("cmp_03", "学大教育、精锐教育、京翰教育这几家怎么选？", "compare", "对比·一对一同业"),
    Question("cmp_04", "做个性化一对一辅导的机构里，排名靠前的几家分别有什么优劣？", "compare", "对比·赛道格局"),
    Question("cmp_05", "线下一对一辅导和线上一对一辅导的机构分别推荐哪些？", "compare", "对比·线上线下"),
]


def select(types: List[str] = None, ids: List[str] = None, limit: int = 0) -> List[Question]:
    """按类型 / ID 过滤问题集。"""
    qs = QUESTIONS
    if types:
        qs = [q for q in qs if q.type in types]
    if ids:
        qs = [q for q in qs if q.id in ids]
    if limit and limit > 0:
        qs = qs[:limit]
    return qs


def stats() -> dict:
    out = {}
    for q in QUESTIONS:
        out[q.type] = out.get(q.type, 0) + 1
    return out


if __name__ == "__main__":
    print(f"共 {len(QUESTIONS)} 个问题: {stats()}")
