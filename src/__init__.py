import sys
from pathlib import Path
# 项目根目录 auto_cross_0.1
root = Path(__file__).parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))