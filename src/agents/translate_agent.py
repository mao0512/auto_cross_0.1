import asyncio
import aiohttp
import os
import hashlib
import random
from dotenv import load_dotenv
from src.schemas.agent_state import AgentState

# 加载.env环境变量
load_dotenv()

BAIDU_APPID = os.getenv("BAIDU_APPID")
BAIDU_APPKEY = os.getenv("BAIDU_APPKEY")
TRANSLATE_SIMULATION = os.getenv("SIMULATE_TRANSLATE", "true").lower() == "true"

# 内置备用模拟翻译库（API异常自动降级使用）
mock_translate_map = {
    "跨境热销款 男士纯棉T恤": {
        "ru_title": "Мужская хлопковая футболка, популярная модель",
        "ru_description": "Удобная мужская хлопковая футболка, несколько расцветок на выбор."
    }
}


def get_baidu_sign(appid: str, query: str, salt: str, secret_key: str):
    """百度翻译标准签名算法，强制返回小写md5"""
    sign_str = appid + query + salt + secret_key
    md5_res = hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    return md5_res.lower()


async def translate_agent_api(session:aiohttp.ClientSession, cn_text: str) -> str | None:
    """调用百度翻译异步请求，复用http会话"""
    if not (BAIDU_APPID and BAIDU_APPKEY):
        return None
    cn_text = cn_text.replace("\n","").replace("\r","").strip()
    if len(cn_text) <= 0:
        return ""
    salt = str(random.randint(100000, 999999))
    sign = get_baidu_sign(BAIDU_APPID, cn_text, salt, BAIDU_APPKEY)
    params = {
        "q": cn_text,
        "from": "zh",
        "to": "ru",
        "appid": BAIDU_APPID,
        "salt": salt,
        "sign": sign
    }
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    async with session.get(url, params=params,timeout=8) as resp:
        res_json = await resp.json()
        if "error_code" in res_json:
            print(f"[TranslateAgent]百度API返回异常:{res_json}")
            return None
        result_text = res_json["trans_result"][0]["dst"]
        return result_text


async def translate_ru_node(state: AgentState) -> AgentState:
    """LangGraph节点入口 graph_builder调用 translate_ru_node"""
    new_state = state.copy()

    # =========【修复】上游流水线输出cn_title / cn_description，兼容旧raw_*字段兜底 =========
    cn_title = state.get("cn_title", "").strip() or state.get("raw_title", "").strip()
    cn_desc = state.get("cn_description", "").strip() or state.get("raw_desc", "").strip()

    raw_sku_list = state.get("raw_sku_list", [])

    # 兜底默认商品文案
    if not cn_title:
        cn_title = "跨境热销款 男士纯棉T恤"
        cn_desc = "舒适透气男士纯棉短袖，多色可选。"

    print(f"[TranslateAgent]正在翻译商品:{cn_title}")

    ru_title = ""
    ru_description = ""

    # 模拟翻译开关关闭时调用百度真实翻译API
    if TRANSLATE_SIMULATION is False:
        async with aiohttp.ClientSession() as session:
            ru_title = await translate_agent_api(session, cn_title)
            await asyncio.sleep(0.6)
            ru_description = await translate_agent_api(session, cn_desc)

    # 本地模拟翻译兜底策略
    if (not ru_title) and (cn_title in mock_translate_map):
        data = mock_translate_map[cn_title]
        ru_title = data["ru_title"]
        ru_description = data["ru_description"]

    # 通用兜底俄语详情
    if not ru_description:
        ru_description = "Удобная дышащая мужская хлопковая футболка, имеется много цветовых вариантов."

    # SKU简单模拟俄语规格
    ru_sku_specs = []
    for sku in raw_sku_list:
        ru_sku_specs.append({
            "spec_ru": sku.get("spec", ""),
            "price": sku.get("price",0),
            "stock": sku.get("stock",999)
        })

    print(f"[TranslateAgent]中文标题：{cn_title}")
    print(f"[TranslateAgent]俄语标题：{ru_title}")
    print(f"[TranslateAgent]俄语详情：{ru_description}")

    new_state["ru_title"] = ru_title
    new_state["ru_description"] = ru_description
    new_state["ru_sku_specs"] = ru_sku_specs
    new_state["task_status"] = "translate_done"
    new_state["error_msg"] = None

    return new_state
