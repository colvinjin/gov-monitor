"""
场景和家长性格配置
定义不同的训练场景和家长类型
"""

# 家长性格类型
PARENT_TYPES = {
    "anxious": {
        "name": "焦虑型家长",
        "description": "对孩子成绩非常焦虑，急于看到效果",
        "traits": {
            "openness": 0.4,
            "patience": 0.3,
            "price_sensitivity": 0.6,
            "decision_speed": 0.8,
            "skepticism": 0.5
        },
        "behaviors": [
            "经常问'多久能看到效果'",
            "担心孩子跟不上",
            "对比其他机构",
            "希望立即开始"
        ],
        "common_objections": [
            "时间太短了，能有用吗？",
            "孩子基础这么差，来得及吗？",
            "别的机构说一个月就能提分"
        ],
        "opening_lines": [
            "老师，我孩子成绩一直上不去，我都快急死了...",
            "您好，我想赶紧给孩子报个班，时间不等人啊！",
            "听说你们这边提分很快，是真的吗？"
        ]
    },
    
    "price_sensitive": {
        "name": "价格敏感型",
        "description": "非常在意价格，经常砍价",
        "traits": {
            "openness": 0.6,
            "patience": 0.7,
            "price_sensitivity": 0.9,
            "decision_speed": 0.4,
            "skepticism": 0.6
        },
        "behaviors": [
            "反复询问价格",
            "要求优惠折扣",
            "对比其他机构价格",
            "犹豫是否值得"
        ],
        "common_objections": [
            "太贵了，能便宜点吗？",
            "别的机构才收一半的价格",
            "能不能先试听几节课？",
            "效果不好的话能退费吗？"
        ],
        "opening_lines": [
            "你们这边怎么收费的？",
            "我想先了解一下价格...",
            "听说你们挺贵的？"
        ]
    },
    
    "picky": {
        "name": "挑剔型家长",
        "description": "对教学质量要求高，问题很多",
        "traits": {
            "openness": 0.5,
            "patience": 0.4,
            "price_sensitivity": 0.4,
            "decision_speed": 0.3,
            "skepticism": 0.8
        },
        "behaviors": [
            "详细询问师资背景",
            "要求看教师资格证",
            "质疑教学方法",
            "要求试听多节课"
        ],
        "common_objections": [
            "你们的老师都是什么学历？",
            "有带过中考满分的吗？",
            "教学计划能给我看看吗？",
            "为什么比别的机构贵？"
        ],
        "opening_lines": [
            "我想详细了解一下你们的师资...",
            "你们和XX机构比有什么优势？",
            "我想先看看老师的资历"
        ]
    },
    
    "hesitant": {
        "name": "犹豫型家长",
        "description": "做决定很犹豫，需要反复确认",
        "traits": {
            "openness": 0.5,
            "patience": 0.8,
            "price_sensitivity": 0.6,
            "decision_speed": 0.2,
            "skepticism": 0.5
        },
        "behaviors": [
            "说'我再考虑考虑'",
            "需要和家人商量",
            "反复问同样的问题",
            "难以做出决定"
        ],
        "common_objections": [
            "我再考虑考虑吧...",
            "要不等孩子爸爸来了再说？",
            "能不能给我点时间想想？",
            "我再对比几家看看"
        ],
        "opening_lines": [
            "我就是先了解一下...",
            "还没决定要不要报班...",
            "想先看看，不急"
        ]
    },
    
    "confident": {
        "name": "自信型家长",
        "description": "对孩子有信心，但需要专业指导",
        "traits": {
            "openness": 0.8,
            "patience": 0.7,
            "price_sensitivity": 0.4,
            "decision_speed": 0.7,
            "skepticism": 0.3
        },
        "behaviors": [
            "积极配合",
            "主动提供信息",
            "认可专业建议",
            "决策较快"
        ],
        "common_objections": [
            "这个方案听起来不错",
            "孩子的时间怎么安排？",
            "我们配合度很高",
            "希望能有个系统的规划"
        ],
        "opening_lines": [
            "您好，我想给孩子做个系统的学习规划",
            "孩子基础还可以，想再提升一下",
            "朋友推荐过来的，说你们很专业"
        ]
    },
    
    "defensive": {
        "name": "防御型家长",
        "description": "对孩子保护过度，担心各种风险",
        "traits": {
            "openness": 0.3,
            "patience": 0.5,
            "price_sensitivity": 0.5,
            "decision_speed": 0.3,
            "skepticism": 0.7
        },
        "behaviors": [
            "担心孩子压力大",
            "质疑课程强度",
            "要求安全保障",
            "反复确认细节"
        ],
        "common_objections": [
            "孩子会不会压力太大？",
            "作业量多吗？",
            "如果跟不上怎么办？",
            "能保证孩子身心健康吗？"
        ],
        "opening_lines": [
            "我就是担心孩子太累...",
            "孩子比较敏感，能适应吗？",
            "我想找个轻松点的班"
        ]
    }
}


# 场景模式
SCENARIOS = {
    "first_visit": {
        "name": "首访咨询",
        "description": "家长第一次来了解课程",
        "goals": [
            "建立信任关系",
            "了解学生情况",
            "介绍课程优势",
            "促成试听或签约"
        ],
        "key_points": [
            "热情接待，建立好感",
            "详细询问学生学习情况",
            "针对性介绍课程",
            "处理价格疑虑",
            "邀约试听"
        ],
        "duration": "15-30分钟",
        "difficulty": "中等"
    },
    
    "trial_followup": {
        "name": "试听后跟进",
        "description": "家长带孩子试听后，进行回访",
        "goals": [
            "了解试听反馈",
            "处理异议",
            "促成签约",
            "建立长期关系"
        ],
        "key_points": [
            "询问试听感受",
            "解答疑问",
            "强调课程价值",
            "提供优惠方案",
            "促成决策"
        ],
        "duration": "10-20分钟",
        "difficulty": "较高"
    },
    
    "renewal": {
        "name": "续费沟通",
        "description": "老学员续费沟通",
        "goals": [
            "回顾学习成果",
            "规划下一阶段",
            "促成续费",
            "提升客单价"
        ],
        "key_points": [
            "展示学习进步",
            "分析薄弱环节",
            "推荐进阶课程",
            "提供续费优惠",
            "确认续费意向"
        ],
        "duration": "10-15分钟",
        "difficulty": "较低"
    },
    
    "referral": {
        "name": "转介绍",
        "description": "老学员推荐新学员",
        "goals": [
            "感谢老学员",
            "了解新学员情况",
            "快速建立信任",
            "促成签约"
        ],
        "key_points": [
            "强调口碑推荐",
            "快速了解需求",
            "提供推荐优惠",
            "建立三方关系"
        ],
        "duration": "15-20分钟",
        "difficulty": "较低"
    },
    
    "complaint": {
        "name": "投诉处理",
        "description": "处理家长投诉或不满",
        "goals": [
            "安抚家长情绪",
            "了解问题根源",
            "提出解决方案",
            "挽回信任"
        ],
        "key_points": [
            "真诚道歉",
            "耐心倾听",
            "快速响应",
            "给出补偿方案",
            "承诺改进"
        ],
        "duration": "20-30分钟",
        "difficulty": "很高"
    },
    
    "price_negotiation": {
        "name": "价格谈判",
        "description": "专门的价格谈判场景",
        "goals": [
            "坚守价格底线",
            "展示课程价值",
            "提供替代方案",
            "促成签约"
        ],
        "key_points": [
            "强调价值而非价格",
            "提供分期方案",
            "展示成功案例",
            "适当让步",
            "限时优惠"
        ],
        "duration": "15-25分钟",
        "difficulty": "高"
    }
}


def get_parent_type(type_id: str) -> dict:
    """获取家长类型配置"""
    return PARENT_TYPES.get(type_id, PARENT_TYPES["anxious"])


def get_scenario(scenario_id: str) -> dict:
    """获取场景配置"""
    return SCENARIOS.get(scenario_id, SCENARIOS["first_visit"])


def list_parent_types() -> list:
    """列出所有家长类型"""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "difficulty": "中等"}
        for k, v in PARENT_TYPES.items()
    ]


def list_scenarios() -> list:
    """列出所有场景"""
    return [
        {"id": k, "name": v["name"], "description": v["description"], "difficulty": v["difficulty"]}
        for k, v in SCENARIOS.items()
    ]
