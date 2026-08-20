from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SkuItem(BaseModel):
    sku_id: Optional[str] = None
    spec: Optional[str] = None


class ProductRequest(BaseModel):
    # 必传字段
    product_id: str
    source_url: str

    # 全部改为可选，爬虫自动抓取填充
    cn_title: Optional[str] = None
    cn_description: Optional[str] = None
    spu_title: Optional[str] = None
    spu_serial_number: Optional[str] = None
    category_id: Optional[int] = None
    attr_json: Optional[Dict[str, Any]] = None
    description_rich: Optional[str] = None
    package_weight: Optional[float] = None
    package_length: Optional[float] = None
    package_width: Optional[float] = None
    package_height: Optional[float] = None
    sku_list: Optional[List[SkuItem]] = None
    video_url: Optional[str] = None

    # 流水线开关，设置默认值
    enable_ocr: bool = True
    enable_translate: bool = True
    enable_image_process: bool = True
    push_to_erp: bool = True