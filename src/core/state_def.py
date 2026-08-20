from typing import TypedDict,List,Dict,Any

class TaskState(TypedDict):
    product_id: str
    source_url: str
    title: str
    description: str
    raw_image_path: str
    processed_image_path: str
    raw_img_list: List[str]
    processed_img_list: List[str]
    cn_title: str
    cn_description: str
    ru_title: str
    ru_description: str
    status: str
    messages: list
    blacklist_hit: bool
    sku_list: List[Any]
    package_weight: float | None
    package_length: float | None
    package_width: float | None
    package_height: float | None
    ozon_payload: Dict[str,Any]
