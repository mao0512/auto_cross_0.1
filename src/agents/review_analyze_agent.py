import os
import logging
from typing import Any, Dict
from src.utils.db_conn import insert_risk_log

logger = logging.getLogger(__name__)


class ReviewAnalyzeAgent:
    """竞品评论风险分析 Agent"""

    def __init__(self):
        self.simulate = os.getenv("SIMULATE_REVIEW_ANALYZE", "true").lower() == "true"

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("💬 [ReviewAnalyzeAgent] 开始分析竞品差评...")
        product_id = state.get("product_id")

        if self.simulate:
            logger.info("💬 [ReviewAnalyzeAgent] 模拟模式：跳过真实评论抓取")
            # TODO: 模拟返回差评分析结果
            state["review_risks"] = [{"competitor_id": 1, "risk_tags": ["材质薄", "续航差"]}]
            # 模拟命中坑品可打开下面测试阻断逻辑
            # await insert_risk_log(product_id,"ReviewAnalyzeAgent","block","竞品大量差评：材质薄、续航差",{"risk_tags":["材质薄","续航差"]})
            # state["status"] = "blocked"
        else:
            # TODO: 真实抓取评论，调用 LLM 提取风险标签，写入 competitor_review 表
            # 如果检测高危风险：
            # await insert_risk_log(...)
            # state["status"] = "blocked"
            pass

        return state
