"""
AI 家长 - 对话逻辑与大模型调用
支持多种性格类型和场景模式
"""
import httpx
from typing import List, Dict, Optional
from config import CLAUDE_API_KEY, CLAUDE_API_URL
from scenarios import get_parent_type, get_scenario, PARENT_TYPES


class AIParent:
    """AI 家长角色"""
    
    def __init__(self, parent_type: str = "anxious", scenario: str = "first_visit"):
        """
        初始化 AI 家长
        
        Args:
            parent_type: 家长类型 (anxious, price_sensitive, picky, hesitant, confident, defensive)
            scenario: 场景 (first_visit, trial_followup, renewal, referral, complaint, price_negotiation)
        """
        self.parent_type = parent_type
        self.scenario = scenario
        self.parent_config = get_parent_type(parent_type)
        self.scenario_config = get_scenario(scenario)
        
        self.conversation_history: List[Dict[str, str]] = []
        self.turn_count = 0
        # 动态态度：0=非常抵触 … 1=非常配合，初始由性格决定
        self.attitude: float = 1.0 - self.parent_config["traits"].get("skepticism", 0.5)
        
    def get_system_prompt(self) -> str:
        """生成系统提示词"""
        traits = self.parent_config["traits"]
        behaviors = self.parent_config["behaviors"]
        objections = self.parent_config["common_objections"]
        
        # 性格描述
        traits_desc = []
        if traits["price_sensitivity"] > 0.7:
            traits_desc.append("对价格非常敏感，会反复砍价、对比其他机构")
        elif traits["price_sensitivity"] > 0.5:
            traits_desc.append("在意价格，希望有优惠")
            
        if traits["decision_speed"] > 0.7:
            traits_desc.append("做决定很快，急于看到效果")
        elif traits["decision_speed"] < 0.4:
            traits_desc.append("做决定很慢，总说'再考虑考虑'")
            
        if traits["skepticism"] > 0.7:
            traits_desc.append("非常挑剔，会质疑师资、教学方法")
        elif traits["skepticism"] > 0.5:
            traits_desc.append("有一定戒备心，需要证明")
            
        if traits["openness"] > 0.7:
            traits_desc.append("比较开放，愿意尝试新事物")
        elif traits["openness"] < 0.4:
            traits_desc.append("比较保守，不容易接受新方案")
        
        traits_text = "\n".join([f"- {t}" for t in traits_desc]) if traits_desc else "- 性格比较平和"
        
        # 场景描述
        scenario_goals = "\n".join([f"- {g}" for g in self.scenario_config["goals"]])
        
        # 开场白
        opening = self.parent_config["opening_lines"][0]
        
        return f"""你是学大教育的潜在客户家长，正在{self.scenario_config["name"]}。

【你的类型】{self.parent_config["name"]}
{self.parent_config["description"]}

【你的性格特点】
{traits_text}

【典型行为】
{chr(10).join([f"- {b}" for b in behaviors[:3]])}

【常用异议】
{chr(10).join([f"- {o}" for o in objections[:3]])}

【场景目标（对咨询师而言）】
{scenario_goals}

【对话规则】
1. 用口语化的中文回复，像真实打电话一样自然
2. 不要一次说太多，2-3句话为宜
3. 保持"{self.parent_config["name"]}"的特点，但不要过于极端
4. 如果咨询师专业、真诚，你会逐渐软化态度
5. 如果咨询师急于推销、不专业，你会更坚持己见
6. 每次回复控制在50字以内
7. 可以偶尔使用："嗯..."、"这个..."、"让我想想"等犹豫语气词

【开场白参考】
{opening}

【当前状态】
- 这是第 {self.turn_count} 轮对话
- 场景：{self.scenario_config["name"]}
- 难度：{self.scenario_config["difficulty"]}
- 当前态度：{self._attitude_desc()}

请直接回复家长该说的话，不要加任何解释。"""

    async def generate_response(self, consultant_message: str) -> str:
        """生成家长回复"""
        self.turn_count += 1
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": self.get_system_prompt()}
        ]
        
        # 添加历史对话
        for turn in self.conversation_history:
            messages.append({"role": "user", "content": turn["consultant"]})
            messages.append({"role": "assistant", "content": turn["parent"]})
        
        # 添加当前消息
        messages.append({"role": "user", "content": consultant_message})
        
        try:
            async with httpx.AsyncClient() as client:
                # OpenAI API
                openai_messages = [{"role": "system", "content": self.get_system_prompt()}]
                for turn in self.conversation_history:
                    openai_messages.append({"role": "user", "content": turn["consultant"]})
                    openai_messages.append({"role": "assistant", "content": turn["parent"]})
                openai_messages.append({"role": "user", "content": consultant_message})
                
                response = await client.post(
                    CLAUDE_API_URL,
                    headers={
                        "Authorization": f"Bearer {CLAUDE_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o",
                        "max_tokens": 150,
                        "messages": openai_messages,
                        "temperature": 0.8
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                parent_response = result["choices"][0]["message"]["content"].strip()
                
                # 记录对话
                self.conversation_history.append({
                    "consultant": consultant_message,
                    "parent": parent_response
                })
                
                return parent_response
                
        except Exception as e:
            print(f"AI Parent error: {e}")
            # 降级回复
            fallback = self.parent_config["common_objections"]
            return fallback[self.turn_count % len(fallback)]
    
    def _attitude_desc(self) -> str:
        if self.attitude >= 0.75:
            return "态度友好，比较配合"
        elif self.attitude >= 0.5:
            return "态度中立，有些犹豫"
        elif self.attitude >= 0.25:
            return "态度冷淡，有明显抵触"
        else:
            return "态度强硬，非常抵触，随时可能挂电话"

    def update_attitude(self, avg_score: float) -> None:
        """根据咨询师本轮平均分调整态度（±0.1 步长，限制在 0~1）"""
        delta = 0.1 if avg_score >= 7 else -0.1
        self.attitude = max(0.0, min(1.0, self.attitude + delta))

    def get_traits_summary(self) -> str:
        """获取当前性格摘要"""
        return f"{self.parent_config['name']} | {self.scenario_config['name']}"
    
    def get_traits(self) -> Dict:
        """获取性格特征（用于评估）"""
        return {
            "type": self.parent_type,
            "type_name": self.parent_config["name"],
            "scenario": self.scenario,
            "scenario_name": self.scenario_config["name"],
            **self.parent_config["traits"]
        }
