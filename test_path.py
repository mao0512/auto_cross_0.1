from pathlib import Path

# 和项目路径保持一致
img_path = Path(r"data/images_raw/TEST_001.png")

print("文件绝对完整路径：", img_path.absolute())
print("文件是否存在：", img_path.exists())

# 如果打印False，代表系统找不到图片，两种常见坑：
# 1. 文件名有空格："TEST_001 .png"
# 2. Windows后缀隐藏，真实名称 TEST_001.png.png