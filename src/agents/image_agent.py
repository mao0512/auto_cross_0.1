import os
import logging
import aiohttp
from pathlib import Path
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter, ImageFont
from src.schemas.agent_state import AgentState

logger = logging.getLogger(__name__)


class ImageUploadAgent:
    """
    商品图片处理Agent
    1.远程URL下载1688原图
    2.居中裁剪正方形 1200*1200 Ozon标准
    3.亮度、对比度、锐化优化
    4.右下角半透明水印
    5.本地缓存；支持模拟开关；输出本地路径列表对接妙手ERP API
    """

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.save_dir = "./data/product_images"
        self.process_root = Path("data/images_processed")
        os.makedirs(self.save_dir, exist_ok=True)
        self.output_format = "JPEG"
        self.target_size = (1200, 1200)

    async def download_image(self, url: str, save_name: str) -> str | None:
        """从1688远程下载图片到本地原始目录"""
        save_path = os.path.join(self.save_dir, save_name)
        if os.path.exists(save_path):
            logger.debug(f"图片已存在，直接复用: {save_path}")
            return save_path

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning(f"图片下载失败 status={resp.status} url={url}")
                        return None
                    content = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(content)
            return save_path
        except Exception as e:
            logger.exception(f"下载图片异常 {url}")
            return None

    async def image_process_local(self, raw_img_list: list[str], product_id: str) -> list[str]:
        """
        复用原来的image_node核心逻辑：
        正方形居中裁剪1200*1200、调色、锐化、右下角半透明水印
        """
        processed_dir = self.process_root / product_id
        processed_dir.mkdir(exist_ok=True, parents=True)
        processed_img_list = []

        for raw_path_str in raw_img_list:
            logger.info(f"[ImageAgent] 开始处理商品图片 {raw_path_str}")
            raw_path = Path(raw_path_str)

            if not raw_path.exists():
                logger.warning("[ImageAgent‑警告] 图片路径不存在，创建备用纯白图片")
                img = Image.new("RGB", self.target_size, (255, 255, 255))
            else:
                try:
                    img = Image.open(raw_path).convert("RGB")
                    w, h = img.size
                    side = min(w, h)
                    left = (w - side) / 2
                    top = (h - side) / 2
                    img = img.crop((left, top, left + side, top + side))
                    img = img.resize(self.target_size, Image.Resampling.LANCZOS)

                    # 亮度对比度优化
                    bright = ImageEnhance.Brightness(img)
                    img = bright.enhance(1.05)
                    contrast = ImageEnhance.Contrast(img)
                    img = contrast.enhance(1.03)
                    img = img.filter(ImageFilter.UnsharpMask(radius=1.2))

                    # 右下角半透明水印
                    draw = ImageDraw.Draw(img)
                    try:
                        water_font = ImageFont.truetype("simhei.ttf", 38)
                    except Exception:
                        water_font = ImageFont.load_default(size=38)
                    water_text = "AutoCross"
                    draw.text((1040, 1120), water_text, font=water_font, fill=(70, 70, 70))

                except Exception as e:
                    logger.exception(f"[ImageAgent‑异常] 无法识别图片文件 {raw_path_str}")
                    img = Image.new("RGB", self.target_size, (255, 255, 255))

            save_name = raw_path.name
            out_path = str(processed_dir / save_name)
            img.save(out_path, format=self.output_format, quality=95)
            processed_img_list.append(out_path)
            logger.info(f"[ImageAgent] 图片标准化完成，输出路径: {out_path}")

        return processed_img_list


async def image_process_node(state: AgentState) -> AgentState:
    """LangGraph标准节点入口 graph_builder调用 image_process_node"""
    sim_flag = os.getenv("SIMULATE_IMAGE", "true").lower() == "true"
    agent = ImageUploadAgent(simulate=sim_flag)
    product_id = state["product_id"]
    raw_img_list = state.get("raw_img_list", [])
    new_state = state.copy()

    if agent.simulate:
        logger.info(f"[ImageUploadAgent]模拟模式，跳过真实图片处理 product_id={product_id}")
        new_state["processed_img_list"] = []
        new_state["task_status"] = "image_done"
        new_state["error_msg"] = None
        return new_state

    processed_img_list = await agent.image_process_local(raw_img_list, product_id)
    new_state["processed_img_list"] = processed_img_list
    new_state["task_status"] = "image_done"
    new_state["error_msg"] = None
    return new_state
