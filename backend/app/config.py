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

# 腾讯 AI 情感分析 API
TENCENT_APPID = os.getenv("TENCENT_APPID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
TENCENT_ENABLED = os.getenv("TENCENT_ENABLED", "false").lower() == "true"

# 监听
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
