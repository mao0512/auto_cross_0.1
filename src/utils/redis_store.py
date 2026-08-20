import redis.asyncio as redis
import json
from typing import Optional, List
from dotenv import load_dotenv
import os

load_dotenv()


class RedisTaskStore:
    def __init__(self):
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD") or None,
            decode_responses=True
        )
        self.EXPIRE_SEC = 7 * 24 * 3600

    async def save_task(self, product_id: str, data: dict):
        """保存任务哈希，list/dict自动转json字符串，兼容redis hset，7天过期"""
        key = f"cross_task:{product_id}"
        safe_mapping = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                safe_mapping[k] = json.dumps(v, ensure_ascii=False)
            elif isinstance(v, bool):
                safe_mapping[k] = str(v).lower()
            elif v is None:
                safe_mapping[k] = ""
            else:
                safe_mapping[k] = str(v)
        await self.client.hset(key, mapping=safe_mapping)
        await self.client.expire(key, self.EXPIRE_SEC)

    async def get_task(self, product_id: str) -> Optional[dict]:
        """读取任务，把json字符串还原回list/dict"""
        key = f"cross_task:{product_id}"
        raw = await self.client.hgetall(key)
        if not raw:
            return None
        result = {}
        for k, v in raw.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result

    async def get_tasks_by_status(self, status: str) -> List[dict]:
        """根据状态获取所有任务【异步版本】"""
        try:
            task_keys = await self.client.keys("cross_task:*")
            tasks = []
            for key in task_keys:
                task_data = await self.client.hgetall(key)
                if task_data and task_data.get("status") == status:
                    parsed = {}
                    for k, v in task_data.items():
                        try:
                            parsed[k] = json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            parsed[k] = v
                    tasks.append(parsed)
            return tasks
        except Exception as e:
            print(f"[RedisStore] 获取任务列表失败: {e}")
            return []

    async def update_task_status(self, product_id: str, status: str):
        """更新任务状态"""
        try:
            key = f"cross_task:{product_id}"
            await self.client.hset(key, "status", status)
        except Exception as e:
            print(f"[RedisStore] 更新任务状态失败: {e}")

    async def exists(self, product_id: str) -> bool:
        key = f"cross_task:{product_id}"
        return await self.client.exists(key) > 0

    async def delete_task(self, product_id: str):
        key = f"cross_task:{product_id}"
        await self.client.delete(key)
