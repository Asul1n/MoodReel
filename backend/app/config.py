"""全局配置：从环境变量 / .env 读取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")

# SQLite 数据库路径
DB_PATH = os.getenv("MOODREEL_DB", str(BASE_DIR / "data" / "moodreel.db"))

# 模型目录（vocab.json / textcnn.npz）
MODEL_DIR = Path(os.getenv("MOODREEL_MODEL_DIR", str(BASE_DIR / "models")))

# 腾讯 AI 情感分析 API（备选中文通道；当前默认用百度，见下）
TENCENT_APPID = os.getenv("TENCENT_APPID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
TENCENT_ENABLED = os.getenv("TENCENT_ENABLED", "false").lower() == "true"

# 百度 AI 情感倾向分析 API（中文通道，默认）
# 文档：https://cloud.baidu.com/product/nlp_apply/sentiment_classify
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")       # 百度智能云 API Key
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")  # 百度智能云 Secret Key
BAIDU_ENABLED = os.getenv("BAIDU_ENABLED", "false").lower() == "true"

# 监听
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
