import pytesseract
from PIL import Image
import cv2
import numpy as np
import os
from pathlib import Path
import yaml

# ===================== 全局配置区域 =====================
pytesseract.pytesseract.tesseract_cmd = r'G:\Program Files\Tesseract-OCR\tesseract.exe'

def load_keyword_config():
    """加载关键词yaml配置：白名单、标题黑名单、描述黑名单、OCR黑名单，白名单优先级最高"""
    config_path = Path(__file__).parent.parent.parent / "config" / "ban_keywords.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    allow_list = set(cfg.get("title_allow", []))
    ban_list = set(cfg.get("title_ban", []))
    desc_ban = set(cfg.get("desc_ban", []))
    ocr_ban = set(cfg.get("ocr_ban", []))
    return allow_list,ban_list,desc_ban,ocr_ban


async def check_node(state: dict):
    title = state.get("cn_title","")
    desc = state.get("cn_description", "")
    raw_img_list = state.get("raw_img_list", [])
    allow_list,ban_list,desc_ban,ocr_ban = load_keyword_config()

    print(f"[CheckAgent] 正在校验商品标题:{title}")
    new_state = state.copy()

    # 标题黑名单校验，白名单豁免拦截
    hit_ban = any(bad_word in title for bad_word in ban_list)
    hit_allow = any(good_word in title for good_word in allow_list)
    if hit_ban and (not hit_allow):
        print(f"[CheckAgent]校验拦截！命中标题黑名单")
        new_state["status"]="blocked"
        new_state["blacklist_hit"]=True
        new_state["block_reason"] = f"标题命中违禁关键词"
        return new_state

    # 商品详情违禁词筛查（本次新增功能）
    hit_desc_ban = any(bad_word in desc for bad_word in desc_ban)
    if hit_desc_ban and (not hit_allow):
        print(f"[CheckAgent]校验拦截！商品详情命中违禁关键词")
        new_state["status"]="blocked"
        new_state["blacklist_hit"]=True
        new_state["block_reason"] = f"商品详情命中违禁关键词"
        return new_state

    # 仅第一张主图进行OCR识别校验，副图跳过
    if len(raw_img_list) > 0:
        one_img_path = raw_img_list[0]
        print(f"[CheckAgent]仅针对主图执行OCR识别：{one_img_path}")

        if not os.path.exists(one_img_path):
            print("[CheckAgent‑警告] 主图文件不存在，跳过OCR校验")
        else:
            try:
                img_cv = cv2.imread(one_img_path)
                if img_cv is None:
                    print("[CheckAgent‑警告] 主图读取失败，跳过OCR校验")
                    ocr_text = ""
                else:
                    # 灰度、高斯降噪、对比度增强
                    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (3, 3), 0)
                    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                    enhance = clahe.apply(blur)
                    # 截取中心ROI
                    h, w = enhance.shape
                    roi_h1, roi_h2 = int(h * 0.15), int(h * 0.85)
                    roi_w1, roi_w2 = int(w * 0.15), int(w * 0.85)
                    roi_img = enhance[roi_h1:roi_h2, roi_w1:roi_w2]
                    binary = cv2.adaptiveThreshold(roi_img, 255,
                                                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                        cv2.THRESH_BINARY,
                                                        blockSize=11, C=2)

                    img = Image.fromarray(binary)
                    ocr_text = pytesseract.image_to_string(img, lang='chi_sim')
                    ocr_text = ocr_text.strip()
                    print(f"[CheckAgent][OCR原始识别文本]:{ocr_text}")

                    for bad_text in ocr_ban:
                        if bad_text in ocr_text:
                            print(f"[CheckAgent]校验拦截！图片检测到违禁字符：{ocr_text}")
                            new_state["status"]="blocked"
                            new_state["blacklist_hit"]=True
                            new_state["block_reason"] = "主图OCR识别出违禁文字"
                            return new_state
            except Exception as e:
                print(f"[CheckAgent‑异常] OCR处理失败 {str(e)}，直接放行")

    print("[CheckAgent]校验通过，允许推送后续处理流程；副图已经全部跳过OCR检测")
    new_state["status"]="image_check_ok"
    new_state["blacklist_hit"]=False
    new_state["block_reason"] = ""
    if "messages" in new_state:
        new_state["messages"].append(("assistant","标题、详情、主图OCR校验通过，副图跳过OCR"))
    return new_state
