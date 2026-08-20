import os
import logging
from typing import Any, Dict
from src.utils.db_conn import insert_risk_log

logger = logging.getLogger(__name__)


class CostCalcAgent:
    """商品成本与利润计算 Agent"""

    def __init__(self):
        self.simulate = os.getenv("SIMULATE_COST_CALC", "true").lower() == "true"
        self.min_gross_margin = float(os.getenv("MIN_GROSS_MARGIN", 0.15))

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("💰 [CostCalcAgent] 开始计算商品成本与利润...")
        product_id = state.get("product_id")

        if self.simulate:
            logger.info("💰 [CostCalcAgent] 模拟模式：跳过真实成本计算")
            # TODO: 模拟计算结果
            state["cost_results"] = [{"product_id": "P-001", "profit_margin": 0.45, "is_profitable": True}]
            # 模拟不达标测试阻断
            # margin = 0.10
            # if margin < self.min_gross_margin:
            #     await insert_risk_log(product_id,"CostCalcAgent","block",f"毛利率 {margin:.2%} 低于阈值 {self.min_gross_margin:.2%}",{"margin":margin})
            #     state["status"] = "blocked"
        else:
            # TODO: 结合采购价、物流费、平台佣金(5%-18%)等计算利润
            # 小于min_gross_margin → blocked
            pass

        return state
