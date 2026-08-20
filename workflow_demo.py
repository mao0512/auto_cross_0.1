import asyncio
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import os
import sys

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_PATH)

load_dotenv()

from src.core.state_def import TaskState
from src.utils.db_conn import init_db, save_or_update_task, task_is_exist
from src.agents.crawl_agent import crawl_node
from src.agents.check_agent import check_node
from src.agents.image_agent import image_node
from src.agents.translate_agent import translate_node
from src.agents.erp_agent import erp_node
from src.agents.ozon_agent import OzonAgent


ozon_agent = OzonAgent()

# 异步包装层，强制await异步函数，杜绝协程对象报错
async def wrap_crawl(state: TaskState):
    return await crawl_node(state)

async def wrap_check(state: TaskState):
    return await check_node(state)

async def wrap_image(state: TaskState):
    return await image_node(state)

async def wrap_translate(state: TaskState):
    return await translate_node(state)

async def wrap_erp(state: TaskState):
    return await erp_node(state)

# 新增Ozon上架节点
async def wrap_ozon_upload(state: TaskState):
    await ozon_agent.create_ozon_product(state)
    return state


# 黑名单条件路由：命中违禁词直接结束流程，否则继续图片处理
def check_blacklist_route(state: TaskState):
    if state.get("blacklist_hit", False):
        return END
    return "image"


async def build_workflow():
    graph = StateGraph(TaskState)
    graph.add_node("crawl", wrap_crawl)
    graph.add_node("check", wrap_check)
    graph.add_node("image", wrap_image)
    graph.add_node("translate", wrap_translate)
    graph.add_node("erp", wrap_erp)
    graph.add_node("ozon_upload", wrap_ozon_upload)

    graph.set_entry_point("crawl")
    graph.add_edge("crawl", "check")
    # 校验节点之后条件判断：违禁直接结束，否则到image
    graph.add_conditional_edges(
        "check",
        check_blacklist_route,
        {
            "image": "image",
            END: END
        }
    )
    graph.add_edge("image", "translate")
    graph.add_edge("translate", "erp")
    graph.add_edge("erp", "ozon_upload")
    graph.add_edge("ozon_upload", END)

    return graph.compile()


async def main():
    await init_db()
    workflow = await build_workflow()
    init_state = {
        "product_id": "TEST_001",
        "source_url": "",
        "raw_img_list": [],
        "processed_img_list": [],
        "status": "pending",
        "blacklist_hit": False,
        "ozon_payload":{}
    }
    result = await workflow.ainvoke(init_state)
    await save_or_update_task(**result)


if __name__ == "__main__":
    asyncio.run(main())
