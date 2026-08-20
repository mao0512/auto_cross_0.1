from src.schemas.agent_state import AgentState
import asyncio
import random
from pathlib import Path
from playwright.async_api import async_playwright, Page
import aiohttp

# ============配置区============
ROOT = Path(__file__).parent.parent.parent
RAW_IMG_ROOT = ROOT / "data" / "images_raw"
SIMULATE_CRAWL = True
PAGE_TIMEOUT = 60000
HEADLESS = False

# UA池
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]


async def safe_download_img(session: aiohttp.ClientSession, img_url: str, save_path: Path):
    try:
        resp = await session.get(img_url, timeout=15)
        if resp.status == 200:
            data = await resp.read()
            if len(data) > 3000:
                with open(save_path, "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"[CrawlAgent]图片下载失败 {img_url},err:{str(e)}")
    return False


async def fetch_goods_info(page: Page):
    title = ""
    title_selectors = [
        "h1.title-text",
        ".offer-title h1",
        "div.title h1",
        ".offer-name",
        "h1.od-detail-title",
        ".detail-header h1",
        "div.offer-info h1"
    ]
    for sel in title_selectors:
        try:
            ele = await page.wait_for_selector(sel, timeout=3000)
            raw_text = await ele.inner_text()
            raw_text = raw_text.strip()
            if "有限公司" not in raw_text and "商行" not in raw_text and raw_text:
                title = raw_text
                break
        except Exception:
            continue

    desc = ""
    desc_selector = [".detail-desc-text", "div.desc-content", ".offer-desc", ".desc-text"]
    for sel in desc_selector:
        try:
            ele = await page.query_selector(sel)
            if ele:
                desc = (await ele.inner_text()).strip()
                break
        except Exception:
            continue
    title = " ".join(title.split())
    return {"cn_title": title, "cn_description": desc}


async def fetch_image_list(page: Page):
    img_url_set = set()
    main_img_selector = [
        ".mainPic img",
        ".slider-img img",
        "div.gallery-list img",
        ".img-box img",
        ".de-gallery img",
        ".offer-gallery img",
        ".pic-box img",
        ".swiper-slide img"
    ]
    for sel in main_img_selector:
        imgs = await page.query_selector_all(sel)
        for img in imgs:
            src = await img.get_attribute("src")
            if not src:
                src = await img.get_attribute("data-src")
            if not src:
                src = await img.get_attribute("data-lazy")
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            lower_src = src.lower()
            skip_suffix = [".svg", ".gif", "png_icon", "logo", "icon"]
            if any(word in lower_src for word in skip_suffix):
                continue
            if "_.jpg" in lower_src:
                src = src.split("_.jpg")[0] + ".jpg"
            if "_.jpeg" in lower_src:
                src = src.split("_.jpeg")[0] + ".jpeg"
            img_url_set.add(src)
    img_list = list(img_url_set)
    print(f"[CrawlAgent] 抓取到 {len(img_list)} 张商品素材图")
    return img_list


async def fetch_package_param(page: Page):
    sku_list = []
    weight = 0.25
    length = 22
    width = 18
    height = 4
    return {
        "sku_list": sku_list,
        "package_weight": weight,
        "package_length": length,
        "package_width": width,
        "package_height": height
    }


async def crawl_1688_node(state: AgentState) -> AgentState:
    """LangGraph节点入口，graph_builder调用名称 crawl_1688_node"""
    product_id = state.get("product_id")
    print(f"[CrawlAgent] 当前state全部字段：{dict(state)}")
    source_url = state.get("source_url")

    new_state = state.copy()

    if not source_url:
        print("[CrawlAgent‑ERROR] source_url 获取为空！爬虫终止")
        new_state["raw_img_list"] = []
        new_state["raw_title"] = ""
        new_state["raw_desc"] = ""
        new_state["raw_sku_list"] = []
        new_state["task_status"] = "crawl_failed"
        new_state["error_msg"] = "source_url为空"
        return new_state

    print(f"[CrawlAgent] 待访问链接:{source_url}")
    print(f"[CrawlAgent] 正在爬取商品 ID:{product_id}")

    sleep_sec = round(random.uniform(3.0, 6.0), 2)
    print(f"[CrawlAgent] 防封禁随机等待 {sleep_sec}s")
    await asyncio.sleep(sleep_sec)

    save_dir = RAW_IMG_ROOT / product_id
    save_dir.mkdir(exist_ok=True, parents=True)
    raw_img_list = []
    goods_info = {"cn_title": "", "cn_description": ""}
    package_info = {"sku_list": [], "package_weight": None, "package_length": None,
                     "package_width": None, "package_height": None}

    if SIMULATE_CRAWL is True:
        print("[CrawlAgent]【模拟模式】采集整套主副图、SKU规格完成")
        from PIL import Image
        for index in range(4):
            file_name = "main.png" if index == 0 else f"sub_{index}.png"
            out_path = save_dir / file_name
            test_img = Image.new("RGB", (1200, 1200), color=(255, 255, 255))
            test_img.save(out_path)
            raw_img_list.append(str(out_path))

        goods_info["cn_title"] = "跨境热销款 男士纯棉T恤"
        goods_info["cn_description"] = "舒适透气男士纯棉短袖，多色可选。"

        # 模拟SKU尺码‑颜色数组
        package_info["sku_list"] = [
            {"spec": "黑色‑M", "sku_id": f"{product_id}_SKU01"},
            {"spec": "白色‑L", "sku_id": f"{product_id}_SKU02"},
            {"spec": "灰色‑XL", "sku_id": f"{product_id}_SKU03"},
        ]
        package_info["package_weight"] = 0.25
        package_info["package_length"] = 22
        package_info["package_width"] = 18
        package_info["package_height"] = 4

    else:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=HEADLESS,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-popup-blocking'
                ]
            )
            retry_times = 4
            for attempt in range(retry_times):
                try:
                    context = await browser.new_context(
                        user_agent=random.choice(USER_AGENT_LIST),
                        viewport={"width": 1366, "height": 768}
                    )
                    page = await context.new_page()
                    #原生JS去除浏览器自动化标记，替代stealth插件
                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.navigator.chrome = { runtime: {} };
                        window.navigator.webdriver=undefined;
                    """)
                    #真人浏览流程：先进入首页
                    await page.goto("https://www.1688.com", timeout=PAGE_TIMEOUT)
                    await asyncio.sleep(random.uniform(2, 3))
                    #打开商品详情
                    await page.goto(source_url, timeout=PAGE_TIMEOUT, wait_until="load")
                    await asyncio.sleep(random.uniform(3,5))
                    #下滑加载相册懒加载图片
                    await page.evaluate("window.scrollTo(0, 300)")
                    await asyncio.sleep(random.uniform(3,4))

                    goods_info = await fetch_goods_info(page)
                    print(f"[CrawlAgent] 获取商品标题：{goods_info['cn_title']}")
                    img_urls = await fetch_image_list(page)
                    package_info = await fetch_package_param(page)

                    if goods_info["cn_title"] != "":
                        async with aiohttp.ClientSession() as session:
                            for idx, img_link in enumerate(img_urls[:4]):
                                save_path = save_dir / (f"img_{idx}.png")
                                ok = await safe_download_img(session, img_link, save_path)
                                if ok:
                                    raw_img_list.append(str(save_path))
                        await context.close()
                        break

                    await context.close()
                    print(f"[CrawlAgent]第{attempt+1}次加载页面没有拿到商品标题，即将重试")
                    await asyncio.sleep(random.uniform(4, 6))

                except Exception as err:
                    print(f"[CrawlAgent]第{attempt+1}次页面访问异常:{str(err)}")
                    await asyncio.sleep(3)
            await browser.close()

    # 字段映射到AgentState
    new_state["raw_img_list"] = raw_img_list
    new_state["raw_title"] = goods_info["cn_title"]
    new_state["raw_desc"] = goods_info["cn_description"]
    new_state["raw_sku_list"] = package_info["sku_list"]
    new_state["task_status"] = "crawl_success"
    new_state["error_msg"] = None

    if not goods_info["cn_title"]:
        print("[CrawlAgent]警告：网页抓取标题为空，请手动在弹出浏览器完成滑块验证")
        new_state["task_status"] = "crawl_warn"
        new_state["error_msg"] = "抓取标题为空，需要过验证码"

    return new_state
