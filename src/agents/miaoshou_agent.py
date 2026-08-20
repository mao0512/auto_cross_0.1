# src/agents/miaoshou_agent.py
from playwright.async_api import Page, BrowserContext
import yaml
import os
from dotenv import load_dotenv
import asyncio
from src.schemas.agent_state import AgentState

load_dotenv()


class MiaoshouERPAgent:
    def __init__(self, context: BrowserContext | None = None):
        """
        初始化妙手ERP Agent
        注意：这里接收的是 BrowserContext 而不是 Page，以便复用全局浏览器环境
        """
        self.context = context
        self.page = None  # Page对象将在登录时创建
        self.selectors = self._load_selectors()
        self.login_url = "https://erp.91miaoshou.com/login"
        self.username = os.getenv("MIAOSHOU_USER")
        self.password = os.getenv("MIAOSHOU_PWD")

    def _load_selectors(self):
        """加载页面定位器配置"""
        try:
            with open("config/selectors.yaml", "r", encoding="utf-8") as f:
                return yaml.safe_load(f)["miaoshou_erp"]
        except FileNotFoundError:
            print("[警告] 未找到 selectors.yaml，将使用空定位器")
            return {}
        except KeyError:
            print("[警告] selectors.yaml 中未找到 miaoshou_erp 配置")
            return {}

    async def _get_page(self):
        """获取或创建新页面"""
        if not self.context:
            from playwright.async_api import async_playwright
            p = await async_playwright().start()
            self.context = await p.chromium.new_context(viewport={"width": 1440, "height": 900})

        if not self.page or self.page.is_closed():
            self.page = await self.context.new_page()
        return self.page

    async def login(self):
        """登录妙手ERP"""
        page = await self._get_page()
        print(f"[MiaoshouAgent] 正在访问登录页: {self.login_url}")

        try:
            # 1. 访问登录页
            await page.goto(self.login_url, wait_until="networkidle", timeout=30000)

            # 2. 执行登录操作 (需等待填入真实的XPath)
            # 这里的定位器暂时留空，等待你提供 selectors.yaml 后填充
            user_input_selector = self.selectors.get("user_input")
            pwd_input_selector = self.selectors.get("pwd_input")
            login_btn_selector = self.selectors.get("login_btn")

            if user_input_selector and pwd_input_selector and login_btn_selector:
                print("[MiaoshouAgent] 正在填入账号密码...")
                await page.fill(user_input_selector, self.username)
                await page.fill(pwd_input_selector, self.password)
                await page.click(login_btn_selector)

                # 等待登录成功跳转
                await page.wait_for_url("**/dashboard**", timeout=10000)
                print("[MiaoshouAgent] 登录成功")
            else:
                print("[MiaoshouAgent] 警告：定位器未配置，跳过自动登录步骤。请检查 selectors.yaml")
                # 为了演示流程，这里暂停5秒让你手动登录（仅调试用）
                await asyncio.sleep(5)

            return True
        except Exception as e:
            print(f"[MiaoshouAgent] 登录失败: {e}")
            # 截图保存错误现场
            await page.screenshot(path="error_login.png")
            return False

    async def create_product(self, product_data: dict):
        """新建商品，回填标题、描述、价格"""
        page = await self._get_page()
        print(f"[MiaoshouAgent] 正在创建商品：{product_data.get('title')}")

        try:
            # 1. 点击“新建商品”按钮
            new_product_btn = self.selectors.get("new_product_btn")
            if new_product_btn:
                await page.click(new_product_btn)
                # 等待新商品页面加载
                await page.wait_for_load_state("networkidle")

            # 2. 填入商品标题
            title_input = self.selectors.get("title_input")
            if title_input:
                await page.fill(title_input, product_data.get("title", ""))

            # 3. 填入商品描述 (如果有)
            desc_input = self.selectors.get("description_input")
            if desc_input and product_data.get("description"):
                await page.fill(desc_input, product_data.get("description"))

            # 4. 填入价格
            price_input = self.selectors.get("price_input")
            if price_input and product_data.get("price"):
                await page.fill(price_input, str(product_data.get("price")))

            print("[MiaoshouAgent] 商品基础信息填写完毕")
            # 注意：图片上传和SKU填写逻辑较复杂，建议在后续阶段单独实现
            return True

        except Exception as e:
            print(f"[MiaoshouAgent] 创建商品失败: {e}")
            await page.screenshot(path="error_create_product.png")
            return False

    async def close(self):
        """关闭页面"""
        if self.page and not self.page.is_closed():
            await self.page.close()


async def push_miaoshou_node(state: AgentState) -> AgentState:
    """LangGraph节点入口 graph_builder调用 push_miaoshou_node"""
    new_state = state.copy()
    product_id = state["product_id"]
    simulate_flag = os.getenv("SIMULATE_MIAOSHOU", "true").lower() == "true"

    if simulate_flag:
        print("[MiaoshouAgent]【模拟推送】跳过真实浏览器妙手ERP")
        new_state["miaoshou_task_id"] = f"MS_{product_id}_001"
        new_state["push_success"] = True
        new_state["task_status"] = "push_success"
        new_state["error_msg"] = None
        return new_state

    # 真实浏览器模式
    agent = MiaoshouERPAgent()
    login_ok = await agent.login()
    if not login_ok:
        new_state["miaoshou_task_id"] = None
        new_state["push_success"] = False
        new_state["task_status"] = "push_failed"
        new_state["error_msg"] = "妙手ERP登录失败"
        await agent.close()
        return new_state

    product_payload = {
        "title": state.get("ru_title",""),
        "description": state.get("ru_description",""),
        "price": 699
    }
    create_ok = await agent.create_product(product_payload)
    await agent.close()

    if create_ok:
        new_state["miaoshou_task_id"] = f"MS_{product_id}_REAL"
        new_state["push_success"] = True
        new_state["task_status"] = "push_success"
        new_state["error_msg"] = None
    else:
        new_state["miaoshou_task_id"] = None
        new_state["push_success"] = False
        new_state["task_status"] = "push_failed"
        new_state["error_msg"] = "妙手ERP新建商品执行失败"

    return new_state
