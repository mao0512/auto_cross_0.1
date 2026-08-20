import asyncio
import uuid
import logging
from typing import Optional, List, Dict
from pathlib import Path
import os
import sys

# 【必须放在最前面，先修正项目根路径】
ROOT_PATH = Path(__file__).parent
sys.path.insert(0, str(ROOT_PATH))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from src.schemas.product_schema import ProductRequest, SkuItem
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from src.graph_builder import build_agent_graph
from src.utils.redis_store import RedisTaskStore
from src.utils.db_conn import task_is_exist, get_one_task, init_db, save_or_update_task, del_one_task, get_product_risk_logs

# 日志配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


task_store = RedisTaskStore()
background_task_map: Dict[str, bool] = {}
workflow_instance = None


# 返回模型、Ozon完整载荷模型，保留
class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class OzonGoodsPayload(BaseModel):
    product_id: str
    source_url: str
    spu_title: Optional[str] = None
    spu_serial_number: Optional[str] = None
    category_id: Optional[str] = None
    attr_json: Optional[dict] = None
    description_rich: Optional[str] = None
    vat_rate: float = 0.20
    package_weight: Optional[float] = None
    package_length: Optional[float] = None
    package_width: Optional[float] = None
    package_height: Optional[float] = None
    sku_list: Optional[List[SkuItem]] = None
    video_url: Optional[str] = None
    pay_ad_switch: bool = False


# 简易测试入参：只需要product_id + source_url
class SimpleTaskCreate(BaseModel):
    product_id: str
    source_url: str


# 请求体模型（新增简易批量任务模型）
class ProductTask(BaseModel):
    product_id: str
    source_url: Optional[str] = None


class BatchProductRequest(BaseModel):
    product_list: List[ProductTask] = Field(description="待处理商品列表")


# 调试专用‑清除缓存请求模型
class DelTaskRequest(BaseModel):
    product_id: str


# 生命周期钩子，替代废弃的 startup‑event
@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow_instance
    # 初始化数据库
    await init_db()
    # 初始化LangGraph 工作流，只执行一次
    workflow_instance = build_agent_graph()
    logger.info("PostgreSQL数据表初始化完成、全局工作流实例加载成功")
    yield


# 后台流水线任务【修复：流水线结束手动赋值status=completed】
async def run_cross_workflow(payload: OzonGoodsPayload):
    global workflow_instance
    try:
        init_state = {
            "product_id": payload.product_id,
            "url": payload.source_url,
            "source_url": payload.source_url,
            "ozon_payload": payload.model_dump(),
            "cn_title": "",
            "cn_description": "",
            "ru_title": "",
            "ru_description": "",
            "raw_img_list": [],
            "processed_img_list": [],
            "status": "pending",
            "blacklist_hit": False,
            "messages": [],
            "sku_list": payload.sku_list if payload.sku_list else [],
            "package_weight": payload.package_weight,
            "package_length": payload.package_length,
            "package_width": payload.package_width,
            "package_height": payload.package_height
        }
        logger.info(f"[流水线启动] product_id = {payload.product_id}")
        result = await workflow_instance.ainvoke(init_state)
        # 流水线正常走完，强制赋值完成状态
        result["status"] = "completed"

        # 保存全部流水线结果至PostgreSQL（包含sku_list数组）
        await save_or_update_task(result)

        await task_store.save_task(payload.product_id, {
            "status": result.get("status", "unknown"),
            "ru_title": result.get("ru_title", ""),
            "ru_description": result.get("ru_description", ""),
            "raw_img_list": result.get("raw_img_list", []),
            "processed_img_list": result.get("processed_img_list", [])
        })

        logger.info(f"[流水线完成] product_id = {payload.product_id}, 状态:{result.get('status')}")
    except Exception as e:
        logger.error(f"[流水线异常]{payload.product_id}, 错误:{str(e)}", exc_info=True)
        await task_store.save_task(payload.product_id, {
            "status": "failed",
            "error_msg": str(e),
            "product_id": payload.product_id
        })
    finally:
        background_task_map.pop(payload.product_id, None)


app = FastAPI(
    title="AutoCross AI Agent API",
    description="自动跨境商品处理 AI 智能体接口，兼容Ozon多‑SKU铺货、主副图批量处理",
    version="0.1.0",
    lifespan=lifespan
)

# 在实例创建之后加载跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/process-product", response_model=TaskResponse)
async def process_product(request: ProductRequest):
    try:
        task_id = str(uuid.uuid4())
        initial_state = {
            "product_id": request.product_id,
            "url": request.source_url,
            "source_url": request.source_url,
            "cn_title": request.cn_title or "",
            "cn_description": request.cn_description or "",
            "ru_title": "",
            "ru_description": "",
            "status": "pending",
            "blacklist_hit": False,
            "messages": [],
            "raw_img_list": [],
            "processed_img_list": [],
            "sku_list": [],
            "package_weight": None,
            "package_length": None,
            "package_width": None,
            "package_height": None
        }
        await task_store.save_task(task_id, {
            "status": "pending",
            "product_id": request.product_id,
            "url": request.source_url
        })
        result = await workflow_instance.ainvoke(initial_state)
        result["status"] = "completed"
        await save_or_update_task(result)
        await task_store.save_task(task_id, {
            "status": result["status"],
            "blacklist_hit": str(result.get("blacklist_hit", False)).lower(),
            "product_id": request.product_id,
            "raw_img_list": result.get("raw_img_list", []),
            "processed_img_list": result.get("processed_img_list", [])
        })
        return TaskResponse(
            task_id=task_id,
            status=result["status"],
            message="任务处理完成" if result["status"] == "completed" else f"任务状态: {result['status']}"
        )
    except Exception as e:
        logger.error(f"process‑product 异常: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


# ----------------简易调试接口：只传product_id、source_url，推荐Swagger优先调用这个----------------
@app.post("/api/task/create_simple", summary="【调试简易入口】新建单个铺货任务，仅传product_id+source_url")
async def create_simple_task(req: SimpleTaskCreate, background_tasks: BackgroundTasks):
    pid = req.product_id.strip()
    src_url = req.source_url.strip()
    exist_flag = await task_is_exist(pid)
    if exist_flag:
        raise HTTPException(status_code=400, detail=f"任务 {pid} 已经存在，请先调用清除缓存接口")
    if pid in background_task_map:
        raise HTTPException(status_code=400, detail=f"任务 {pid} 当前正在运行")

    payload = OzonGoodsPayload(
        product_id=pid,
        source_url=src_url
    )
    background_task_map[pid] = True
    await task_store.save_task(pid, {"status": "pending", "product_id": pid})
    background_tasks.add_task(run_cross_workflow, payload)
    return {
        "code":0,
        "msg":"简易任务提交成功，后台执行",
        "data":{
            "product_id": pid,
            "status_url": f"/api/task/status/{pid}"
        }
    }


@app.post("/api/task/create", summary="新建单个商品铺货任务，妙手ERP调用，完整载荷")
async def create_task(payload: OzonGoodsPayload, background_tasks: BackgroundTasks):
    exist_flag = await task_is_exist(payload.product_id)
    if exist_flag:
        raise HTTPException(status_code=400, detail=f"任务 {payload.product_id} 已经存在，请更换编号")
    # 并发重复提交拦截
    if payload.product_id in background_task_map:
        raise HTTPException(status_code=400, detail=f"任务 {payload.product_id} 当前正在运行")

    background_task_map[payload.product_id] = True
    await task_store.save_task(payload.product_id, {"status": "pending", "product_id": payload.product_id})
    # 将完整payload传入后台任务，流水线能够读取SKU、包装参数
    background_tasks.add_task(run_cross_workflow, payload)
    return {"code": 200, "msg": "任务创建成功‑后台开始处理", "product_id": payload.product_id}


@app.post("/api/task/batch", summary="批量新建SKU/SPU铺货任务")
async def batch_task(goods_list: List[OzonGoodsPayload], background_tasks: BackgroundTasks):
    success_list = []
    fail_exist_list = []
    fail_running_list = []
    for item in goods_list:
        exist_flag = await task_is_exist(item.product_id)
        if exist_flag:
            fail_exist_list.append(item.product_id)
            continue
        if item.product_id in background_task_map:
            fail_running_list.append(item.product_id)
            continue

        background_task_map[item.product_id] = True
        await task_store.save_task(item.product_id, {"status": "pending", "product_id": item.product_id})
        background_tasks.add_task(run_cross_workflow, item)
        success_list.append(item.product_id)
    return {
        "code": 200,
        "success_task": success_list,
        "fail_exist_task": fail_exist_list,
        "fail_running_task": fail_running_list
    }


# 简易批量商品处理接口，改为后台异步执行
@app.post("/api/v1/batch-process", summary="批量处理商品，自带任务去重，适配主副图采集")
async def batch_process(req: BatchProductRequest, background_tasks: BackgroundTasks):
    success_list = []
    skip_list = []
    for item in req.product_list:
        pid = item.product_id
        exist = await task_is_exist(pid)
        if exist:
            skip_list.append(pid)
            continue
        payload = OzonGoodsPayload(
            product_id=pid,
            source_url=item.source_url
        )
        background_task_map[pid] = True
        await task_store.save_task(pid, {"status": "pending", "product_id": pid})
        background_tasks.add_task(run_cross_workflow, payload)
        success_list.append(pid)

    return {
        "code": 200,
        "success": success_list,
        "skipped(已存在任务)": skip_list
    }


# ========== 修正后的调试清理缓存接口 ==========
@app.post("/api/v1/task/clear-cache", summary="调试‑清除指定product_id任务缓存，解除任务跳过拦截")
async def clear_single_cache(req: DelTaskRequest):
    pid = req.product_id
    # 清空内存运行标记
    background_task_map.pop(pid, None)
    # 删除PostgreSQL任务记录
    await del_one_task(pid)
    # 删除Redis缓存
    await task_store.delete_task(pid)
    logger.info(f"调试缓存清理成功 product_id:{pid}")
    return {"code": 200, "msg": "指定商品任务缓存已经清空", "product_id": pid}


@app.post("/api/v1/task/clear-all-test", summary="调试‑清空全部测试任务缓存")
async def clear_all_cache():
    # 清空内存运行标记
    background_task_map.clear()
    logger.info("全部调试内存任务标记清空完毕")
    return {"code": 200, "msg": "内存运行标记已清空，请在DBeaver清空auto_cross_task数据表"}


@app.get("/api/task/status/{pid}", summary="从PostgreSQL数据库查询商品任务处理状态、SKU、翻译文案、图片路径")
async def get_status(pid: str):
    task_info = await get_one_task(pid)
    if not task_info:
        raise HTTPException(status_code=404, detail="找不到该任务")
    return task_info


@app.get("/api/risk-log/{pid}", summary="获取商品风控拦截日志")
async def get_risk_log(pid: str):
    logs = await get_product_risk_logs(pid)
    return {
        "product_id": pid,
        "total": len(logs),
        "logs": [
            {
                "id": item.id,
                "agent_name": item.agent_name,
                "risk_level": item.risk_level,
                "risk_reason": item.risk_reason,
                "risk_detail": item.risk_detail,
                "create_time": item.create_time
            }
            for item in logs
        ]
    }


@app.get("/api/health")
async def health_check():
    return {"service": "auto‑cross api‑server", "running": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
