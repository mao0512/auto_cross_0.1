from typing import List, Dict, Any, Optional, Literal
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """LangGraph工作流全局状态
    扩展：选品决策Agent、多平台目标市场、成本利润、风险评估、人工强制拦截
    """
    product_id: str
    source_url: str

    # 1688采集输出
    raw_img_list: List[str]
    raw_title: str
    raw_desc: str
    raw_sku_list: List[Dict[str, Any]]

    # 图片处理输出
    processed_img_list: List[str]

    # AI翻译输出
    ru_title: str
    ru_description: str
    ru_sku_specs: List[Dict[str, Any]]

    # ERP/妙手推送结果
    miaoshou_task_id: Optional[str]
    push_success: bool

    # 任务状态
    task_status: str
    error_msg: Optional[str]

    # ============【新增：选品决策Agent字段】============
    # 成本、利润、物流、退货预估
    product_cost: Optional[Dict[str, Any]]
    # 选品判定状态
    decision: Literal["pending", "accept", "reject"]
    decision_reason: str
    # 目标市场平台列表：["ozon","wildberries"] / 未来 ["saudi","th","kr","us","eu"]
    market_target: List[str]
    # 风险标记：时效风险、退货高风险、合规风险标记
    risk_flag: bool
    # 市场适配打分 0‑10
    score: Optional[float]
    # 人工强制拦截开关：True=即使AI判定accept，依然禁止推送平台
    human_override: bool