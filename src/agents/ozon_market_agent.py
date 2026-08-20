import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class OzonMarketAgent:
    """Ozon 市场数据抓取与分析 Agent"""

    def __init__(self):
        self.simulate = os.getenv("SIMULATE_OZON_MARKET", "true").lower() == "true"

    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("🔍 [OzonMarketAgent] 开始执行市场数据抓取...")

        if self.simulate:
            logger.info("🔍 [OzonMarketAgent] 模拟模式：跳过真实网络请求")
            # TODO: 模拟返回热搜词和竞品数据
            mock_keywords = [{"keyword": "电热毯", "category_id": "123", "heat_score": 95.5}]
            mock_competitors = [{"ozon_item_id": "OZ-999", "title": "测试竞品", "price": 1500.0}]
            state["hot_keywords"] = mock_keywords
            state["competitors"] = mock_competitors
        else:
            # TODO: 接入真实妙手 API 或爬虫抓取数据并写入 PostgreSQL ozon_hot_keyword、ozon_competitor
            pass

        return state
