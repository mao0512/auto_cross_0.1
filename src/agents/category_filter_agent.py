import os
import logging
from typing import Any, Dict, List
from src.utils.db_conn import insert_risk_log

logger = logging.getLogger(__name__)


class CategoryFilterAgent:
    """受控多类目测款过滤 Agent"""

    def __init__(self):
        self.simulate = os.getenv("SIMULATE_CATEGORY_FILTER", "true").lower() == "true"
        self.max_allowed_categories = int(os.getenv("MAX_CATEGORIES_PER_BATCH", 4))

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("🚦 [CategoryFilterAgent] 开始执行类目过滤与管控...")

        # 获取待上架商品的类目列表
        pending_products: List[Dict] = state.get("pending_products", [])
        category_ids = set(p.get("category_id") for p in pending_products if p.get("category_id"))

        if len(category_ids) > self.max_allowed_categories:
            warn_msg = (
                f"🚦 [CategoryFilterAgent] 拦截：检测到 {len(category_ids)} 个一级大类，"
                f"超出限制 {self.max_allowed_categories}。将仅保留前 {self.max_allowed_categories} 个类目。"
            )
            logger.warning(warn_msg)
            product_id = state.get("product_id","batch_task")
            await insert_risk_log(str(product_id),"CategoryFilterAgent","warn",warn_msg,{
                "actual_count":len(category_ids),
                "max_allow":self.max_allowed_categories
            })
            allowed_categories = list(category_ids)[:self.max_allowed_categories]
            state["filtered_products"] = [
                p for p in pending_products if p.get("category_id") in allowed_categories
            ]
        else:
            logger.info(f"🚦 [CategoryFilterAgent] 放行：当前 {len(category_ids)} 个类目，符合受控测款标准。")
            state["filtered_products"] = pending_products

        return state
