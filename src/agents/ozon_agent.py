import requests
import os
import logging
from src.utils.browser import BrowserManager
from typing import List, Dict, Optional
from src.core.state_def import TaskState

logger = logging.getLogger(__name__)


class OzonAgent:
    def __init__(self):
        self.client_id = os.getenv("OZON_CLIENT_ID")
        self.api_key = os.getenv("OZON_API_KEY")
        self.base_url = "https://api-seller.ozon.ru"
        self.simulate_mode = os.getenv("simulate_mode", "True") == "True"
        self.timeout = 20
        self.headers = {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def get_shortage_list(self) -> List[Dict]:
        if self.simulate_mode:
            return [
                {"product_name": "Мужская хлопковая футболка", "category_id": 10021, "stock_deficit": True}
            ]
        url = f"{self.base_url}/v1/analytics/shortage"
        payload = {"category_id": 0, "limit": 100}
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception as e:
            logger.error(f"获取缺货列表失败: {str(e)}")
            return []

    def get_hot_sales(self) -> List[Dict]:
        if self.simulate_mode:
            return [
                {"product_name": "Летняя хлопковая футболка", "sales_count": 1260}
            ]
        url = f"{self.base_url}/v1/analytics/hits"
        payload = {"category_id": 0, "limit": 100}
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception as e:
            logger.error(f"获取热销榜单失败: {str(e)}")
            return []

    def get_product_detail(self, product_id: str) -> Dict:
        if self.simulate_mode:
            return {"product_id": product_id, "name": "Мужская хлопковая футболка"}
        url = f"{self.base_url}/v1/product/info"
        payload = {"product_id": [int(product_id)]}
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("result", [{}])[0]
        except Exception as e:
            logger.error(f"读取商品详情异常:{str(e)}")
            return {}

    async def create_ozon_product(self, task_state: TaskState) -> Dict:
        sku_list = task_state.get("sku_list", task_state.get("ozon_payload", {}).get("sku_list", []))
        product_title = task_state.get("ru_title", "")
        product_desc = task_state.get("ru_description", "")
        weight = task_state.get("package_weight", 500)
        length = task_state.get("package_length", 20)
        width = task_state.get("package_width", 15)
        height = task_state.get("package_height", 5)
        category_id = task_state.get("ozon_payload", {}).get("category_id", 10021)
        image_urls = task_state.get("processed_img_list", [])

        # 组装Ozon规格sku
        sku_items = []
        for item in sku_list:
            sku_items.append({
                "offer_id": item.get("sku_id"),
                "price": "990",
                "old_price": "1290",
                "visibility":"VISIBLE"
            })

        payload = {
            "products": [
                {
                    "offer_id": task_state["product_id"],
                    "product_id": 0,
                    "price": "990",
                    "old_price": "1290",
                    "currency_code": "RUB",
                    "visibility": "VISIBLE",
                    "name": product_title,
                    "description": product_desc,
                    "category_id": category_id,
                    "images": image_urls,
                    "weight": weight,
                    "dimensions": {
                        "length": length,
                        "width": width,
                        "height": height
                    },
                    "skus": sku_items
                }
            ]
        }

        if self.simulate_mode:
            print(f"[OzonAgent‑模拟上架] 商品id:{task_state['product_id']} 俄语标题:{product_title} SKU数量:{len(sku_list)}")
            logger.info(f"Ozon模拟提交载荷 {payload}")
            return {
                "success": True,
                "ozon_product_id": f"OZ‑{task_state['product_id']}",
                "sku_list": sku_list
            }

        url = f"{self.base_url}/v1/product/import"
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            res_data = resp.json()
            logger.info(f"Ozon商品创建成功 返回:{res_data}")
            return res_data
        except Exception as e:
            err_msg = f"Ozon商品上架失败 {str(e)}"
            logger.error(err_msg)
            return {"success": False, "error": err_msg}
