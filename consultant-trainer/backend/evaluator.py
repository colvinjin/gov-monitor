"""
咨询师评估模块
实时评估对话质量，生成训练报告
"""
import json
from typing import List, Dict, Optional
from config import CLAUDE_API_KEY, CLAUDE_API_URL
import httpx


class ConversationEvaluator:
    """对话评估器"""
    
    # 评估维度
    DIMENSIONS = {
        "rapport": "建立信任关系",
        "needs_analysis": "需求挖掘",
        "product_intro": "产品介绍",
        "objection_handling": "异议处理",
        "closing": "成交引导"
    }
    
    def __init__(self):
        self.api_key = CLAUDE_API_KEY
        self.api_url = CLAUDE_API_URL
        self.evaluations: List[Dict] = []
    
    async def evaluate_turn(self, consultant_text: str, parent_response: str, 
                          turn_number: int, parent_traits: Dict) -> Dict:
        """
        评估单轮对话
        
        Returns:
            {
                "scores": {"rapport": 8, "needs_analysis": 7, ...},
                "feedback": "具体建议",
                "strengths": ["优点1", "优点2"],
                "improvements": ["改进点1", "改进点2"]
            }
        """
        prompt = f"""你是一位资深的学大教育销售培训专家。请评估咨询师在这轮对话中的表现。

家长特征: {json.dumps(parent_traits, ensure_ascii=False)}

第 {turn_number} 轮对话:
咨询师: {consultant_text}
家长回复: {parent_response}

请从以下5个维度评分（1-10分），并给出具体建议：
1. 建立信任关系 (rapport) - 是否快速建立信任
2. 需求挖掘 (needs_analysis) - 是否有效挖掘家长需求
3. 产品介绍 (product_intro) - 产品介绍是否清晰有吸引力
4. 异议处理 (objection_handling) - 是否妥善处理家长疑虑
5. 成交引导 (closing) - 是否有自然的成交引导

请以JSON格式返回:
{{
    "scores": {{
        "rapport": 分数,
        "needs_analysis": 分数,
        "product_intro": 分数,
        "objection_handling": 分数,
        "closing": 分数
    }},
    "feedback": "总体评价和建议",
    "strengths": ["优点1", "优点2"],
    "improvements": ["改进点1", "改进点2"],
    "key_insight": "关键洞察（一句话）"
}}"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": "你是学大教育销售培训专家，擅长评估咨询师表现并给出建设性反馈。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 1000
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # 解析 JSON
                try:
                    # 尝试直接解析
                    evaluation = json.loads(content)
                except json.JSONDecodeError:
                    # 尝试从 markdown 代码块中提取
                    import re
                    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                    if json_match:
                        evaluation = json.loads(json_match.group(1))
                    else:
                        # 简单解析失败，返回默认结构
                        evaluation = {
                            "scores": {k: 7 for k in self.DIMENSIONS.keys()},
                            "feedback": content[:200],
                            "strengths": ["积极参与对话"],
                            "improvements": ["继续练习"],
                            "key_insight": "表现良好"
                        }
                
                # 确保所有维度都有分数
                for dim in self.DIMENSIONS.keys():
                    if dim not in evaluation.get("scores", {}):
                        evaluation.setdefault("scores", {})[dim] = 7
                
                evaluation["turn"] = turn_number
                self.evaluations.append(evaluation)
                
                return evaluation
                
        except Exception as e:
            print(f"评估失败: {e}")
            return {
                "turn": turn_number,
                "scores": {k: 7 for k in self.DIMENSIONS.keys()},
                "feedback": "评估暂时不可用",
                "strengths": ["继续练习"],
                "improvements": ["保持积极态度"],
                "key_insight": "系统评估中"
            }
    
    def generate_final_report(self) -> Dict:
        """生成最终评估报告"""
        if not self.evaluations:
            return {
                "overall_score": 0,
                "dimension_scores": {},
                "summary": "暂无评估数据",
                "recommendations": []
            }
        
        # 计算各维度平均分
        dimension_scores = {}
        for dim in self.DIMENSIONS.keys():
            scores = [e["scores"].get(dim, 7) for e in self.evaluations if "scores" in e]
            dimension_scores[dim] = round(sum(scores) / len(scores), 1) if scores else 7
        
        # 总分
        overall_score = round(sum(dimension_scores.values()) / len(dimension_scores), 1)
        
        # 收集所有优点和改进点
        all_strengths = []
        all_improvements = []
        for e in self.evaluations:
            all_strengths.extend(e.get("strengths", []))
            all_improvements.extend(e.get("improvements", []))
        
        # 去重并取最常见的
        from collections import Counter
        top_strengths = [s for s, _ in Counter(all_strengths).most_common(3)]
        top_improvements = [i for i, _ in Counter(all_improvements).most_common(3)]
        
        # 评级
        if overall_score >= 9:
            level = "优秀"
        elif overall_score >= 7:
            level = "良好"
        elif overall_score >= 5:
            level = "合格"
        else:
            level = "需改进"
        
        return {
            "overall_score": overall_score,
            "level": level,
            "dimension_scores": dimension_scores,
            "dimension_names": self.DIMENSIONS,
            "total_turns": len(self.evaluations),
            "strengths": top_strengths,
            "improvements": top_improvements,
            "summary": f"本次训练综合评分 {overall_score} 分，表现{level}。",
            "recommendations": self._generate_recommendations(dimension_scores)
        }
    
    def _generate_recommendations(self, scores: Dict[str, float]) -> List[str]:
        """生成个性化建议"""
        recommendations = []
        
        # 找出得分最低的维度
        sorted_dims = sorted(scores.items(), key=lambda x: x[1])
        
        for dim, score in sorted_dims[:2]:  # 关注最弱的2个维度
            if score < 6:
                if dim == "rapport":
                    recommendations.append("建议加强开场白练习，更快建立信任关系")
                elif dim == "needs_analysis":
                    recommendations.append("多使用开放式问题，深入挖掘家长真实需求")
                elif dim == "product_intro":
                    recommendations.append("准备更多成功案例，让产品介绍更有说服力")
                elif dim == "objection_handling":
                    recommendations.append("提前准备常见异议的应对话术")
                elif dim == "closing":
                    recommendations.append("练习自然过渡，把握成交时机")
        
        if not recommendations:
            recommendations.append("整体表现不错，继续保持！可以尝试更复杂的场景训练。")
        
        return recommendations


# 单例实例
evaluator = ConversationEvaluator()
