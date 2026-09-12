#!/usr/bin/env python3
"""
学大教育 · 国内主流大模型品牌可见度监测 - 配置层

包含三部分配置：
1. BRAND / COMPETITORS  品牌词表（含中文子串消歧规则）
2. PROVIDERS            被监测的国产大模型（均走 OpenAI 兼容协议）
3. WEIGHTS / 判定阈值    指标口径
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List

try:  # python-dotenv 是可选依赖，缺失时直接读进程环境变量
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


# ============================================================
# 1. 品牌词表
# ============================================================

@dataclass
class Brand:
    """品牌及其在模型回答中的各种写法。

    aliases: 强匹配词，出现即判定命中。
    fuzzy:   易误伤的短写法（如"学大"会命中"教学大纲"），需上下文消歧。
    """
    name: str
    aliases: List[str] = field(default_factory=list)
    fuzzy: List[str] = field(default_factory=list)
    # fuzzy 命中后，若前/后紧邻字符落在黑名单里，判为误匹配
    fuzzy_prev_block: str = ""
    fuzzy_next_block: str = ""
    # fuzzy 命中后，窗口内必须出现任一限定词（为空表示不要求）
    fuzzy_require: List[str] = field(default_factory=list)
    is_self: bool = False


# "学大"作为子串极易误伤：教学大纲 / 数学大赛 / 学大概 / 同学大多 / 上学大约 …
# 前置黑名单收录常见"X学"构词的 X，后置黑名单收录常见"大X"构词的 X。
XUEDA_PREV_BLOCK = "教数化科文理医光电力法哲美史地生物药农工商神心社语汉天算同中小大上放开求好自助留国"
XUEDA_NEXT_BLOCK = "概纲了约赛会师佬专学事业型批片桥"

BRAND = Brand(
    name="学大教育",
    aliases=["学大教育", "紫光学大", "学大1对1", "学大一对一", "学大个性化", "Xueda", "XUEDA", "xueda"],
    fuzzy=["学大"],
    fuzzy_prev_block=XUEDA_PREV_BLOCK,
    fuzzy_next_block=XUEDA_NEXT_BLOCK,
    is_self=True,
)

# 一对一 / 个性化辅导赛道主要竞品
COMPETITORS: List[Brand] = [
    Brand("新东方", aliases=["新东方"]),
    Brand("学而思", aliases=["学而思", "好未来", "学而思培优"]),
    Brand("精锐教育", aliases=["精锐教育", "精锐·个性化"],
          fuzzy=["精锐"], fuzzy_require=["教育", "辅导", "1对1", "一对一", "培训", "机构"]),
    Brand("京翰教育", aliases=["京翰教育", "京翰"]),
    Brand("卓越教育", aliases=["卓越教育"],
          fuzzy=["卓越"], fuzzy_require=["教育", "辅导", "1对1", "一对一", "培训", "机构"]),
    Brand("龙文教育", aliases=["龙文教育"],
          fuzzy=["龙文"], fuzzy_require=["教育", "辅导", "1对1", "一对一", "培训", "机构"]),
    Brand("掌门1对1", aliases=["掌门1对1", "掌门一对一", "掌门教育"],
          fuzzy=["掌门"], fuzzy_require=["教育", "辅导", "1对1", "一对一", "在线"]),
    Brand("猿辅导", aliases=["猿辅导"]),
    Brand("作业帮", aliases=["作业帮"]),
    Brand("高途", aliases=["高途课堂", "高途教育"],
          fuzzy=["高途"], fuzzy_require=["教育", "辅导", "课堂", "培训", "机构"]),
    Brand("大桥教育", aliases=["大桥教育"]),
    Brand("金博教育", aliases=["金博教育"]),
]


def all_brands() -> List[Brand]:
    """自家品牌 + 竞品，供 SOV 计算使用。"""
    return [BRAND] + COMPETITORS


# ============================================================
# 2. 被监测模型（全部走 OpenAI 兼容的 /chat/completions）
# ============================================================

@dataclass
class Provider:
    key: str                                   # 内部标识
    label: str                                 # 展示名
    base_url: str                              # OpenAI 兼容 base_url
    default_model: str
    api_key_env: str
    note: str = ""
    extra_body: Dict = field(default_factory=dict)   # 如联网搜索开关
    timeout: float = 180.0

    @property
    def model(self) -> str:
        """允许用环境变量覆盖模型版本，如 DOUBAO_MODEL=doubao-seed-1-6-250615"""
        return os.getenv(f"{self.key.upper()}_MODEL", self.default_model)

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key)


PROVIDERS: List[Provider] = [
    Provider(
        key="doubao", label="豆包(字节·方舟)",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-pro-32k",
        api_key_env="ARK_API_KEY",
        note="模型名需填方舟上的接入点 ID 或模型名",
    ),
    Provider(
        key="qwen", label="通义千问(阿里)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        api_key_env="DASHSCOPE_API_KEY",
        note="extra_body 里可开 enable_search 模拟联网版",
        extra_body={"enable_search": False},
    ),
    Provider(
        key="deepseek", label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
    ),
    Provider(
        key="glm", label="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-plus",
        api_key_env="ZHIPU_API_KEY",
    ),
    Provider(
        key="kimi", label="Kimi(月之暗面)",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        api_key_env="MOONSHOT_API_KEY",
    ),
    Provider(
        key="ernie", label="文心一言(百度千帆)",
        base_url="https://qianfan.baidubce.com/v2",
        default_model="ernie-4.5-turbo-128k",
        api_key_env="QIANFAN_API_KEY",
    ),
    Provider(
        key="hunyuan", label="腾讯混元",
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        default_model="hunyuan-turbos-latest",
        api_key_env="HUNYUAN_API_KEY",
    ),
    Provider(
        key="spark", label="讯飞星火",
        base_url="https://spark-api-open.xf-yun.com/v1",
        default_model="4.0Ultra",
        api_key_env="SPARK_API_KEY",
        note="APIKey:APISecret 形式的 key 直接整体填入",
    ),
    Provider(
        key="minimax", label="MiniMax",
        base_url="https://api.minimax.chat/v1",
        default_model="abab6.5s-chat",
        api_key_env="MINIMAX_API_KEY",
    ),
    Provider(
        key="baichuan", label="百川",
        base_url="https://api.baichuan-ai.com/v1",
        default_model="Baichuan4-Turbo",
        api_key_env="BAICHUAN_API_KEY",
    ),
]


def get_provider(key: str) -> Provider:
    for p in PROVIDERS:
        if p.key == key:
            return p
    raise KeyError(f"未知模型标识: {key}")


def available_providers() -> List[Provider]:
    return [p for p in PROVIDERS if p.available]


# 情感裁判模型：默认复用已配置的某个模型，按顺序取第一个可用的
JUDGE_PREFERENCE = ["deepseek", "doubao", "qwen", "glm", "kimi"]


def pick_judge() -> Provider:
    for key in JUDGE_PREFERENCE:
        p = get_provider(key)
        if p.available:
            return p
    raise RuntimeError("没有可用的裁判模型，请至少配置一个 API Key，或使用 --no-judge")


# ============================================================
# 3. 采集参数与指标口径
# ============================================================

# 每个问题在每个模型上重复采样次数（抵消生成随机性，建议 >=3）
REPEATS = int(os.getenv("MONITOR_REPEATS", "3"))
TEMPERATURE = float(os.getenv("MONITOR_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MONITOR_MAX_TOKENS", "1600"))
CONCURRENCY = int(os.getenv("MONITOR_CONCURRENCY", "4"))
MAX_RETRIES = 3

# 品牌上下文窗口：取提及点前后各 N 字用于情感分析
CONTEXT_WINDOW = 140

# 排名得分表：回答里排第几，折算多少可见度分
RANK_SCORE = {1: 1.0, 2: 0.75, 3: 0.55, 4: 0.40, 5: 0.30}
RANK_SCORE_TAIL = 0.15      # 第 6 名及以后
MENTION_NO_RANK_SCORE = 0.20  # 提及了但没进推荐清单

# 可见度指数权重（三项之和为 1）
WEIGHTS = {
    "mention": 0.45,    # 提及率
    "rank": 0.30,       # 排名（首位率的连续化版本）
    "sentiment": 0.25,  # 正面反馈程度
}

SYSTEM_PROMPT = "你是一个中文智能助手，请像平时回答普通用户那样自然作答。"
