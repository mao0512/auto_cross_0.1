from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SkuItem(BaseModel):
    sku_id: Optional[str] = None
    spec: Optional[str] = None
    price: Optional[float] = None
    weight: Optional[float] = None


class ProductRequest(BaseModel):
    # 必传字段
    product_id: str = Field(..., description="任务唯一商品ID")
    source_url: str = Field(..., description="1688货源链接")
    # 新增：目标平台，支持多平台 ["ozon","wildberries"]
    market_target: List[str] = Field(default_factory=lambda: ["ozon"], description="目标铺货平台")

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


class TaskResponse(BaseModel):
    id: str
    product_id: str
    source_url: str

    cn_title: Optional[str]
    cn_description: Optional[str]
    ru_title: Optional[str]
    ru_description: Optional[str]

    raw_img_path: Optional[str]
    processed_img_path: Optional[str]
    sku_data: List[Dict[str, Any]]

    task_status: str
    error_msg: Optional[str]

    erp_goods_id: Optional[str]
    ozon_goods_id: Optional[str]

    create_time: str
    update_time: str

    # =========新增选品决策返回字段=========
    decision: Optional[str] = Field(None, description="选品判定:pending/accept/reject")
    decision_reason: Optional[str] = Field(None, description="判定原因说明")
    score: Optional[float] = Field(None, description="市场适配打分0‑10")
    risk_flag: Optional[bool] = Field(None, description="是否标记高风险")
    market_target: Optional[List[str]] = Field(default_factory=list, description="目标铺货平台列表")