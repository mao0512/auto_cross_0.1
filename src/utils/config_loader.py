import yaml
import os
from pathlib import Path
import time

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent
YAML_PATH = BASE_DIR / "config" / "ban_keywords.yaml"
# 记录文件上次修改时间，实现热加载
_last_modify_time = 0
_cached_config = None


def load_ban_keywords():
    """
    加载违规黑名单配置【热加载版本】
    修改yaml文件自动生效，无需重启程序
    返回：title_ban：全部转为小写字符串列表
    """
    global _last_modify_time, _cached_config
    if not os.path.exists(YAML_PATH):
        # 文件缺失兜底默认黑名单
        default = {
            "title_ban": ["刺刀", "bamoher"],
            "ocr_ban": []
        }
        return default

    current_mtime = os.path.getmtime(YAML_PATH)
    # 文件未变更，直接返回缓存
    if current_mtime == _last_modify_time and _cached_config is not None:
        return _cached_config

    # 文件改动，重新读取
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    # 统一全部转为小写，规避大小写问题（BaMoHer / bamoher 等效拦截）
    raw_data["title_ban"] = [kw.lower() for kw in raw_data.get("title_ban", [])]
    raw_data["ocr_ban"] = [kw.lower() for kw in raw_data.get("ocr_ban", [])]

    _last_modify_time = current_mtime
    _cached_config = raw_data
    return _cached_config
def load_crawl_config():
    """加载采集浏览器、延时配置"""
    from pathlib import Path
    import yaml
    BASE_DIR = Path(__file__).parent.parent.parent
    cfg_path = BASE_DIR / "config" / "request.yaml"
    if not cfg_path.exists():
        # 默认兜底参数
        return {
            "crawl": {"min_sleep":1.5, "max_sleep":4.0, "page_timeout":30000},
            "browser": {"headless":False,"viewport_width":1280,"viewport_height":720}
        }
    with open(cfg_path,"r",encoding="utf-8") as f:
        return yaml.safe_load(f)