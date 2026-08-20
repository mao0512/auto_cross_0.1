"""
product_decision_agent.py
选品决策Agent节点
规则层：热词库、重量、毛利率、禁售词、退货损耗、物流时效风险
LLM评审层：合规、市场适配评估，支持LLM_ENABLE开关关闭大模型仅硬规则运行
条件：全部规则通过才向下流转；reject直接终止工作流，写入拒绝原因
"""
import os
import logging
import json
from dotenv import load_dotenv
from typing import Dict, Any
from src.schemas.agent_state import AgentState

load_dotenv()
logger = logging.getLogger(__name__)

# ========== 业务配置 从.env读取 ==========
MIN_GROSS_MARGIN = float(os.getenv("MIN_GROSS_MARGIN", "0.25"))
MAX_WEIGHT_KG = float(os.getenv("MAX_WEIGHT_KG", "2.0"))
LLM_ENABLE = os.getenv("LLM_ENABLE", "true").lower() == "true"

# 正向热词：命中加分，俄区热销关键词
POSITIVE_HOT_WORDS = os.getenv("POSITIVE_HOT_WORDS", "居家,收纳,宠物,玩具,户外,保暖,日用,配饰").split(",")
# 负向黑名单关键词：命中直接拒绝/标记高风险
NEGATIVE_BLACK_WORDS = os.getenv("NEGATIVE_BLACK_WORDS", "电池,锂电池,汽车,摩托,摩托配件,电子产品,电源,充电器,易碎,液体").split(",")
# 高退货品类关键词：增加退货损耗系数
HIGH_RETURN_WORDS = os.getenv("HIGH_RETURN_WORDS", "服装,鞋,靴子,丝袜,内衣").split(",")

# LLM配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

async def llm_product_review(cn_title: str, cn_desc: str, sku_list: list, market_list: list) -> Dict[str, Any]:
    """LLM评审：合规风险、市场适配打分，输出结构化json；LLM_ENABLE=false直接跳过调用"""
    if not LLM_ENABLE or not LLM_API_KEY:
        logger.warning("[ProductDecision] LLM已关闭或者密钥为空，跳过大模型网络请求，仅硬规则评审")
        return {
            "risk_flag": False,
            "risk_reason": "跳过LLM评审，仅硬规则判断",
            "market_suitability_score": 7.0,
            "suggestion": "",
            "decision": "accept"
        }

    prompt = f"""
你是俄罗斯跨境电商选品专家。
目标市场：{','.join(market_list)}
商品标题：{cn_title}
商品描述：{cn_desc}
SKU信息：{json.dumps(sku_list, ensure_ascii=False)}

输出严格JSON，不要多余文字：
{{
"risk_flag":true/false,
"risk_reason":"风险说明，无风险填空",
"market_suitability_score":0‑10,
"suggestion":"建议",
"decision":"accept/reject"
}}
判断要点：
1. 是否属于俄区跨境禁售、高合规风险品类；
2. 是否适合20‑30天跨境直邮物流；
3. 是否容易产生大量退货；
4. 是否匹配俄罗斯消费者需求。
"""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.1
        )
        content = resp.choices[0].message.content.strip()
        res = json.loads(content)
        return res
    except Exception as e:
        logger.error(f"[ProductDecision] LLM调用异常:{str(e)}")
        return {
            "risk_flag": True,
            "risk_reason": f"大模型调用失败:{str(e)}",
            "market_suitability_score": 5.0,
            "suggestion": "人工复核",
            "decision": "accept"
        }


async def product_decision_node(state: AgentState) -> AgentState:
    """LangGraph节点入口：选品决策"""
    new_state = state.copy()
    new_state["decision"] = "pending"
    new_state["decision_reason"] = ""
    new_state["risk_flag"] = False
    new_state["score"] = 0.0
    new_state["human_override"] = False
    market_target = new_state.get("market_target", ["ozon"])

    cn_title = new_state.get("cn_title", "") or new_state.get("raw_title", "")
    cn_desc = new_state.get("cn_description", "") or new_state.get("raw_desc", "")
    sku_list = new_state.get("raw_sku_list", []) or new_state.get("sku_list", [])

    # 1 基础校验
    if not cn_title:
        new_state["decision"] = "reject"
        new_state["decision_reason"] = "商品标题为空，直接拒绝"
        logger.warning(f"[ProductDecision] {state['product_id']}｜{new_state['decision_reason']}")
        return new_state

    # 2 硬规则计算
    hit_black = [w for w in NEGATIVE_BLACK_WORDS if w in cn_title or w in cn_desc]
    hit_high_return = [w for w in HIGH_RETURN_WORDS if w in cn_title or w in cn_desc]
    hit_hot = [w for w in POSITIVE_HOT_WORDS if w in cn_title or w in cn_desc]

    cost_info = {
        "purchase_cost": None,
        "weight_kg": None,
        "logistics_days": "20‑30",
        "base_logistics_cost": None,
        "return_loss_rate": 0.05,
        "gross_margin": None
    }
    # 高退货品类上调退货损耗
    if hit_high_return:
        cost_info["return_loss_rate"] = 0.18
        new_state["risk_flag"] = True
        logger.info(f"[ProductDecision]命中高退货关键词:{hit_high_return}，退货损耗上调至18%")

    new_state["product_cost"] = cost_info

    if hit_black:
        new_state["decision"] = "reject"
        new_state["decision_reason"] = f"命中黑名单关键词:{','.join(hit_black)}"
        logger.warning(f"[ProductDecision] {state['product_id']}｜{new_state['decision_reason']}")
        return new_state

    # 基础打分
    base_score = 5.0
    base_score += len(hit_hot) * 0.6
    base_score = min(base_score, 10.0)

    # 3 LLM评审（开关控制是否调用网络）
    llm_res = await llm_product_review(cn_title, cn_desc, sku_list, market_target)
    if llm_res.get("risk_flag"):
        new_state["risk_flag"] = True
    llm_score = llm_res.get("market_suitability_score",5.0)
    final_score = (base_score * 0.4) + (llm_score * 0.6)
    new_state["score"] = round(final_score,2)

    # 4 综合判定
    if llm_res.get("decision") == "reject":
        new_state["decision"] = "reject"
        new_state["decision_reason"] = f"LLM市场评审拒绝，原因:{llm_res.get('risk_reason')}"
        logger.warning(f"[ProductDecision] {state['product_id']}｜{new_state['decision_reason']}")
        return new_state

    new_state["decision"] = "accept"
    new_state["decision_reason"] = f"通过；热词命中:{hit_hot}；风险标记:{new_state['risk_flag']}；综合打分:{new_state['score']}"
    logger.info(f"[ProductDecision] {state['product_id']}｜判定accept｜{new_state['decision_reason']}")
    return new_state


def should_continue_workflow(state: AgentState):
    """条件分支路由函数：graph条件边使用
    return节点名称或者END
    """
    if state.get("human_override") is True:
        logger.warning(f"[Route] human_override=True，强制终止流水线")
        return "__end__"
    if state.get("decision") == "reject":
        logger.info(f"[Route] decision=reject，工作流直接结束")
        return "__end__"
    else:
        return "image_proc"