import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

# 读取Redis配置
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_DB = int(os.getenv("REDIS_DB"))
EXPIRE_SECONDS = int(os.getenv("REDIS_TASK_EXPIRE"))

# 创建异步Redis客户端
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD if REDIS_PASSWORD else None,
    db=REDIS_DB,
    decode_responses=True
)


async def check_task_cache(product_id: str) -> bool:
    """
    检查Redis缓存判断任务是否正在执行
    返回True=任务缓存存在、正在运行，需要跳过；False=可以执行
    """
    key = f"running_task:{product_id}"
    exist = await redis_client.exists(key)
    return bool(exist)


async def set_task_running(product_id: str):
    """标记任务正在运行，设置过期时间"""
    key = f"running_task:{product_id}"
    await redis_client.setex(key, EXPIRE_SECONDS, "running")


async def clear_task_cache(product_id: str):
    """任务处理完毕之后清除运行标记"""
    key = f"running_task:{product_id}"
    await redis_client.delete(key)


async def set_task_status(product_id: str, status: str):
    """写入任务状态缓存"""
    key = f"task_status:{product_id}"
    await redis_client.setex(key, EXPIRE_SECONDS, status)


async def get_task_status(product_id: str) -> str | None:
    key = f"task_status:{product_id}"
    return await redis_client.get(key)