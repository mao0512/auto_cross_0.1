import os
import logging
from typing import Any, Dict, List
from src.utils.db_conn import insert_risk_log

logger = logging.getLogger(__name__)


class ComplianceCheckAgent:
    """商品合规与风控检查 Agent"""

    def __init__(self):
        self.simulate = os.getenv("SIMULATE_COMPLIANCE_CHECK", "true").lower() == "true"
        black_str = os.getenv("BLACKLIST_KEYWORDS", "")
        self.blacklist_keywords: List[str] = [x.strip() for x in black_str.split(",") if x.strip()]

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("🛡️ [ComplianceCheckAgent] 开始合规与风控检查...")
        product_id = state.get("product_id")

        if self.simulate:
            logger.info("🛡️ [ComplianceCheckAgent] 模拟模式：跳过真实合规校验")
            # TODO: 模拟合规检查结果
            state["compliance_results"] = [{"product_id": "P-001", "is_compliant": True, "risk_reason": None}]
            # 模拟拦截测试
            # await insert_risk_log(product_id,"ComplianceCheckAgent","block","该类目需要EAC认证，禁止自动铺货",{})
            # state["status"] = "blocked"
        else:
            # TODO: 检查 EAC 认证、商标侵权、黑名单关键词，不通过则写入 product_risk_log，设置status=blocked
            pass

        return state
