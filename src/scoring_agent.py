from typing import Dict, List



class ScoringAgent:
    def __init__(self):
        # 严景森模型权重配置
        self.weights = {
            "shortage_score": 0.3,  # 缺货蓝海权重（最高）
            "margin_score": 0.3,  # 毛利率权重
            "competition_score": 0.2,  # 竞争度权重
            "pain_point_score": 0.2  # 差评痛点规避权重
        }

    def calculate_margin(self, ozon_price: float, cost_1688: float,
                         logistics: float = 20.0, commission_rate: float = 0.15) -> float:
        """计算毛利率"""
        revenue = ozon_price * (1 - commission_rate) - logistics
        margin = (revenue - cost_1688) / ozon_price
        return margin

    def score_product(self, product_data: Dict, cost_1688: float) -> Dict:
        """
        严景森4步标准化评分
        返回: {"score": 0-100, "pass": bool, "reason": str}
        """
        ozon_price = product_data.get("price", 0)
        shortage_rank = product_data.get("shortage_rank", 100)  # 1-100, 1为最缺货

        # 1. 毛利率一票否决
        margin = self.calculate_margin(ozon_price, cost_1688)
        if margin < 0.35:
            return {"score": 0, "pass": False, "reason": f"毛利率{margin:.2%} < 35%"}

        # 2. 缺货蓝海评分 (越缺货分越高)
        shortage_score = max(0, (100 - shortage_rank) / 100) * 100

        # 3. 竞争度评分 (简化逻辑：在售卖家数越少分越高)
        seller_count = product_data.get("seller_count", 50)
        competition_score = max(0, (100 - seller_count) / 100) * 100

        # 4. 差评痛点评分 (简化：有"尺寸偏小"等关键词扣分)
        pain_points = product_data.get("negative_keywords", [])
        pain_score = max(0, 100 - len(pain_points) * 20)

        # 加权总分
        total_score = (
                shortage_score * self.weights["shortage_score"] +
                (margin * 100) * self.weights["margin_score"] +
                competition_score * self.weights["competition_score"] +
                pain_score * self.weights["pain_point_score"]
        )

        return {
            "score": round(total_score, 2),
            "pass": total_score >= 60,  # 60分以上进入1688匹配环节
            "reason": f"毛利{margin:.2%}, 缺货{shortage_rank}, 竞争{seller_count}"
        }