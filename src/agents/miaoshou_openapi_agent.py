"""
miaoshou_openapi_agent.py
妙手ERP 开放API推送Agent，替代旧Playwright浏览器erp_agent
不再启动浏览器，直接HTTP调用openapi.91miaoshou.com
环境变量读取：MIAOSHOU_APP_ID / MIAOSHOU_APP_SECRET / MIAOSHOU_API_BASE
SIMULATE_MIAOSHOU=true：仅打印请求，不调用真实接口
"""
import os
import time
import hashlib
import logging
import aiohttp
from dotenv import load_dotenv
from typing import Dict, Any

load_dotenv()
logger = logging.getLogger(__name__)

MIAOSHOU_APP_ID = os.getenv("MIAOSHOU_APP_ID", "")
MIAOSHOU_APP_SECRET = os.getenv("MIAOSHOU_APP_SECRET", "")
MIAOSHOU_API_BASE = os.getenv("MIAOSHOU_API_BASE", "https://openapi.91miaoshou.com/api")
SIMULATE_MIAOSHOU = os.getenv("SIMULATE_MIAOSHOU", "true").lower() == "true"


def gen_miaoshou_sign(app_secret: str, params: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
    """妙手开放平台签名算法"""
    timestamp = int(time.time())
    params["timestamp"] = timestamp
    sorted_items = sorted(params.items())
    raw_str = "".join([f"{k}{v}" for k, v in sorted_items]) + app_secret
    sign = hashlib.md5(raw_str.encode("utf-8")).hexdigest().upper()
    params["sign"] = sign
    return params, timestamp


async def push_product_to_miaoshou(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    将state商品数据推送妙手开放API
    :param state: LangGraph state，包含cn_title、ru_title、ru_description、sku_list、processed_img_list
    :return: 更新后的state
    """
    pid = state["product_id"]
    new_state = state.copy()

    payload = {
        "app_id": MIAOSHOU_APP_ID,
        "outer_product_id": pid,
        "cn_title": state.get("cn_title", ""),
        "ru_title": state.get("ru_title", ""),
        "ru_desc": state.get("ru_description", ""),
        "sku_list": state.get("sku_list", []),
        "image_list": state.get("processed_img_list", []),
    }

    logger.info(f"[MiaoshouOpenApiAgent] product_id={pid} 待推送payload: {payload}")

    if SIMULATE_MIAOSHOU:
        logger.info("[MiaoshouOpenApiAgent]【模拟模式】跳过妙手开放API真实请求")
        new_state["messages"].append("妙手API模拟推送完成")
        return new_state

    if not MIAOSHOU_APP_ID or not MIAOSHOU_APP_SECRET or MIAOSHOU_APP_ID == "你的app_id":
        logger.error("[MiaoshouOpenApiAgent] MIAOSHOU_APP_ID / APP_SECRET未配置真实密钥")
        new_state["status"] = "failed"
        new_state["messages"].append("妙手API密钥未配置")
        return new_state

    req_params, _ = gen_miaoshou_sign(MIAOSHOU_APP_SECRET, payload)
    url = f"{MIAOSHOU_API_BASE}/product/create"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=req_params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                resp_json = await resp.json()
                logger.info(f"[MiaoshouOpenApiAgent] API返回: {resp_json}")
                if resp_json.get("code") == 0:
                    new_state["messages"].append(f"妙手API创建商品成功，resp:{resp_json}")
                else:
                    new_state["status"] = "failed"
                    new_state["messages"].append(f"妙手API返回错误 {resp_json}")
    except Exception as e:
        logger.error(f"[MiaoshouOpenApiAgent]调用异常 {str(e)}", exc_info=True)
        new_state["status"] = "failed"
        new_state["messages"].append(f"妙手API网络异常:{str(e)}")

    return new_state
