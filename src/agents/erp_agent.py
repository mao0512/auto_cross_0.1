import os
import time
import hashlib
import requests
import logging
from dotenv import load_dotenv
from typing import Dict, List, Any

load_dotenv()
logger = logging.getLogger(__name__)


class ErpAgent:
    """
    妙手ERP【开放HTTP API版本】
    移除Playwright浏览器自动化，使用妙手openapi接口
    能力：商品新增、SKU录入、图片上传、中俄标题、规格录入
    """
    def __init__(self):
        self.app_id = os.getenv("MIAOSHOU_APP_ID")
        self.app_secret = os.getenv("MIAOSHOU_APP_SECRET")
        self.api_base = os.getenv("MIAOSHOU_API_BASE", "https://openapi.91miaoshou.com/api")
        self.simulation = os.getenv("ERP_SIMULATION", "True") == "True"
        self.session = requests.Session()

    def _gen_sign(self, params: Dict[str, Any]) -> str:
        """妙手开放平台签名算法"""
        sorted_items = sorted(params.items())
        raw = "".join([f"{k}{v}" for k, v in sorted_items]) + self.app_secret
        sign = hashlib.md5(raw.encode("utf-8")).hexdigest().upper()
        return sign

    def _request(self, path: str, body: Dict) -> Dict:
        """统一请求封装，自动加app_id、timestamp、sign签名"""
        timestamp = int(time.time())
        params = {
            "app_id": self.app_id,
            "timestamp": timestamp
        }
        payload = {**params, "data": body}
        payload["sign"] = self._gen_sign(payload)

        if self.simulation:
            logger.info(f"[ErpAgent‑模拟模式] 妙手API {path} 载荷：{payload}")
            return {"code":0, "msg":"simulate success", "data":{"goods_id":"SIM_"+str(timestamp)}}

        try:
            resp = self.session.post(f"{self.api_base}{path}", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.exception("[ErpAgent]调用妙手API异常")
            raise e

    async def push_product(self, state: Dict) -> Dict:
        """
        接收LangGraph state，向妙手ERP推送处理完成商品
        state字段：product_id、cn_title、ru_title、cn_description、ru_description
                   sku_list、processed_img_list、package_weight、package_length...
        """
        product_id = state["product_id"]
        sku_list:List[Dict] = state.get("sku_list",[])
        img_list:List[str] = state.get("processed_img_list",[])

        payload_data = {
            "outer_goods_id": product_id,
            "goods_name_cn": state.get("cn_title",""),
            "goods_name_ru": state.get("ru_title",""),
            "desc_cn": state.get("cn_description",""),
            "desc_ru": state.get("ru_description",""),
            "images": img_list,
            "sku": [
                {
                    "outer_sku_id": sku.get("sku_id"),
                    "spec": sku.get("spec"),
                    "price": 99.0
                } for sku in sku_list
            ],
            "package_weight": state.get("package_weight"),
            "package_length": state.get("package_length"),
            "package_width": state.get("package_width"),
            "package_height": state.get("package_height")
        }

        resp = self._request("/goods/create", payload_data)
        state["erp_goods_id"] = resp.get("data",{}).get("goods_id")
        logger.info(f"[ErpAgent] product_id={product_id} 推送妙手完成 erp_goods_id={state['erp_goods_id']}")
        return state


async def erp_node(state: dict):
    """
    LangGraph 异步节点入口：推送商品至妙手ERP（API版本）
    对外函数名保持 erp_node，workflow_demo.py 完全不用修改调用代码
    """
    print(f"[ErpAgent]正在推送商品到妙手开放API:{state['product_id']}")
    new_state = state.copy()

    erp = ErpAgent()
    try:
        new_state = await erp.push_product(new_state)
        new_state["status"] = "completed"
        new_state["messages"] = [("assistant", "ERP(OpenAPI)推送成功")]
    except Exception as err:
        logger.exception("[ErpAgent]妙手API推送失败")
        new_state["status"] = "erp_fail"
        new_state["messages"] = [("assistant", f"ERP推送失败:{str(err)}")]

    return new_state
