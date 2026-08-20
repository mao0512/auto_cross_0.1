"""
graph_builder.py
LangGraph 工作流编排 AutoCross AI‑Agent
新版链路：CrawlAgent → product_decision_node【选品决策】 → 条件分支
accept：image_proc→translate→miaoshou_push
reject/human_override：直接END终止
支持环境变量控制模拟/真实模式
"""
import os
import logging
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from src.schemas.agent_state import AgentState
from src.agents.product_decision_agent import product_decision_node, should_continue_workflow

# 加载环境变量
load_dotenv()
logger = logging.getLogger(__name__)

# 模拟开关读取
SIMULATE_CRAWL = os.getenv("SIMULATE_CRAWL", "true").lower() == "true"
SIMULATE_IMAGE = os.getenv("SIMULATE_IMAGE", "true").lower() == "true"
SIMULATE_TRANSLATE = os.getenv("SIMULATE_TRANSLATE", "true").lower() == "true"
SIMULATE_MIAOSHOU = os.getenv("SIMULATE_MIAOSHOU", "true").lower() == "true"
CRAWL_HEADLESS = os.getenv("CRAWL_HEADLESS", "false").lower() == "true"


async def crawl_agent(state: AgentState) -> AgentState:
    """CrawlAgent：1688商品采集节点｜支持模拟/真实Playwright采集"""
    pid = state["product_id"]
    src_url = state["source_url"]
    logger.info(f"[CrawlAgent] 当前state全部字段：{state}")
    logger.info(f"[CrawlAgent] 待访问链接:{src_url}")
    logger.info(f"[CrawlAgent] 正在爬取商品 ID:{pid}")

    import asyncio
    import random
    delay = random.uniform(3.0, 6.0)
    logger.info(f"[CrawlAgent] 防封禁随机等待 {delay:.2f}s")
    await asyncio.sleep(delay)

    if SIMULATE_CRAWL:
        logger.info("[CrawlAgent]【模拟模式】采集整套主副图、SKU规格完成")
        new_state = state.copy()
        new_state["raw_title"] = "跨境热销款 男士纯棉T恤"
        new_state["raw_desc"] = "男士夏季纯棉短袖T恤，多颜色多尺码可选，面料透气亲肤。"
        # 修复：同步写入cn_title、cn_description，数据库、接口不再返回null
        new_state["cn_title"] = new_state["raw_title"]
        new_state["cn_description"] = new_state["raw_desc"]

        new_state["raw_img_list"] = [
            f"data/images_raw/{pid}/main.png",
            f"data/images_raw/{pid}/sub_1.png",
            f"data/images_raw/{pid}/sub_2.png",
            f"data/images_raw/{pid}/sub_3.png",
        ]
        new_state["raw_sku_list"] = [
            {"sku_id": f"{pid}_SKU01", "spec": "颜色:黑色;尺码:M", "price": 29.9, "weight":0.3},
            {"sku_id": f"{pid}_SKU02", "spec": "颜色:白色;尺码:L", "price": 29.9, "weight":0.3},
        ]
        return new_state
    else:
        logger.info("[CrawlAgent]【真实采集模式】启动Playwright访问1688页面")
        from src.agents.crawl_agent import crawl_1688_node
        new_state = await crawl_1688_node(state)
        return new_state


async def image_agent(state: AgentState) -> AgentState:
    """ImageAgent：图片下载、裁剪、增强、加水印"""
    pid = state["product_id"]
    logger.info(f"[ImageAgent] product_id={pid}")
    new_state = state.copy()
    if SIMULATE_IMAGE:
        logger.info("[ImageAgent]模拟模式，跳过真实图片处理")
        new_state["processed_img_list"] = [
            f"data/images_processed/{pid}/main.jpg",
            f"data/images_processed/{pid}/sub_1.jpg",
            f"data/images_processed/{pid}/sub_2.jpg",
            f"data/images_processed/{pid}/sub_3.jpg",
        ]
        return new_state
    else:
        from src.agents.image_agent import image_node
        res_state = await image_node(new_state)
        return res_state


async def translate_agent(state: AgentState) -> AgentState:
    """TranslateAgent 中文转俄语标题、详情"""
    logger.info("[TranslateAgent]进入翻译节点")
    new_state = state.copy()
    cn_title = new_state.get("raw_title", "")
    cn_desc = new_state.get("raw_desc", "")

    if SIMULATE_TRANSLATE:
        logger.info(f"[TranslateAgent]正在翻译商品:{cn_title}")
        logger.info(f"[TranslateAgent]中文标题：{cn_title}")
        new_state["ru_title"] = "Мужская хлопковая футболка, популярная модель"
        new_state["ru_description"] = "Удобная мужская хлопковая футболка, несколько расцветок на выбор."
        return new_state
    else:
        from src.agents.translate_agent import translate_ru_node
        res_state = await translate_ru_node(new_state)
        return res_state


async def miaoshou_agent(state: AgentState) -> AgentState:
    """MiaoshouAgent 推送商品至妙手开放API"""
    logger.info("[MiaoshouAgent]进入妙手ERP推送节点")
    new_state = state.copy()
    if SIMULATE_MIAOSHOU:
        logger.info("[MiaoshouAgent]模拟推送成功")
        new_state["miaoshou_task_id"] = f"SIM‑{state['product_id']}"
        new_state["push_success"] = True
        return new_state
    else:
        from src.agents.miaoshou_openapi_agent import push_product_to_miaoshou
        res_state = await push_product_to_miaoshou(new_state)
        return res_state


def build_agent_graph():
    """构建完整的Agent工作流图
    链路：crawl → product_decision_node →【条件判断】
        accept → image_proc → translate → miaoshou_push
        reject / human_override → END
    """
    graph = StateGraph(AgentState)

    # 注册全部节点
    graph.add_node("crawl", crawl_agent)
    graph.add_node("product_decision", product_decision_node)
    graph.add_node("image_proc", image_agent)
    graph.add_node("translate", translate_agent)
    graph.add_node("miaoshou_push", miaoshou_agent)

    # 固定边
    graph.add_edge("crawl", "product_decision")
    # 条件路由：选品节点输出后判断走向
    graph.add_conditional_edges(
        "product_decision",
        should_continue_workflow,
        {
            "image_proc": "image_proc",
            "__end__": END
        }
    )

    graph.add_edge("image_proc", "translate")
    graph.add_edge("translate", "miaoshou_push")
    graph.add_edge("miaoshou_push", END)

    graph.set_entry_point("crawl")
    app = graph.compile()
    return app