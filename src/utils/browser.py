from playwright.async_api import async_playwright, Page, BrowserContext
from typing import Optional, Dict
import asyncio


class BrowserManager:
    """
    Playwright 异步浏览器管理器
    适配LangGraph异步节点，全部async/await，杜绝同步阻塞报错
    支持无头模式、反爬虫检测、页面操作、截图
    """
    def __init__(self, headless: bool = True, viewport: Dict = None):
        self.headless = headless
        # 默认窗口尺寸，允许外部配置覆盖
        self.viewport = viewport or {"width": 1920, "height": 1080}
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None

    async def start(self) -> Page:
        """【异步】启动浏览器，返回Page对象"""
        # 启动异步playwright实例
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        # 创建浏览器上下文
        self.context = await self.browser.new_context(
            viewport=self.viewport,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai'
        )
        # 注入反webdriver检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)
        # 创建新页面
        self.page = await self.context.new_page()
        return self.page

    async def goto(self, url: str, wait_until: str = 'networkidle', timeout: int = 15000):
        """【异步】页面跳转"""
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)
        await asyncio.sleep(1)

    async def fill(self, selector: str, value: str):
        """【异步】输入框填充内容"""
        await self.page.fill(selector, value)
        await asyncio.sleep(0.5)

    async def click(self, selector: str):
        """【异步】点击页面元素"""
        await self.page.click(selector)
        await asyncio.sleep(1)

    async def screenshot(self, path: str, full_page: bool = True):
        """【异步】页面截图保存"""
        await self.page.screenshot(path=path, full_page=full_page)

    async def get_text(self, selector: str) -> str:
        """【异步】获取元素文本内容"""
        content = await self.page.text_content(selector)
        return content or ""

    async def is_visible(self, selector: str, timeout: int = 3000) -> bool:
        """【异步】判断元素是否可见"""
        try:
            return await self.page.is_visible(selector, timeout=timeout)
        except Exception:
            return False

    async def close(self):
        """【异步】顺序释放资源，关闭浏览器，捕获异常避免残留进程"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            print(f"[BrowserManager]关闭浏览器资源异常: {e}")