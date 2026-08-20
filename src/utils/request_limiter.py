"""
请求随机限速工具，模拟真人浏览，降低1688爬虫识别概率
配合Playwright采集使用
"""
import random
import asyncio
from src.utils.config_loader import load_crawl_config

class RequestLimiter:
    @staticmethod
    async def human_sleep():
        """读取配置文件进行随机等待"""
        cfg = load_crawl_config()
        min_sleep = cfg["crawl"]["min_sleep"]
        max_sleep = cfg["crawl"]["max_sleep"]
        delay = round(random.uniform(min_sleep, max_sleep), 2)
        print(f"[限速工具]模拟人工浏览，休眠 {delay}s")
        await asyncio.sleep(delay)

    @staticmethod
    async def short_wait():
        """页面元素等待短时延时，用于点击后等待渲染"""
        await asyncio.sleep(random.uniform(0.3, 0.8))