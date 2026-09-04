"""全局配置：从环境变量 / .env 读取。"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
load_dotenv(BASE_DIR / ".env")


def _abs(p: str) -> str:
    """把相对路径统一解析到 backend/ 下，避免依赖运行目录。"""
    path = Path(p).expanduser()
    return str(path if path.is_absolute() else BASE_DIR / path)


# SQLite 数据库路径
DB_PATH = _abs(os.getenv("MOODREEL_DB", str(BASE_DIR / "data" / "moodreel.db")))

# 模型目录（model.pt 等）
MODEL_DIR = Path(_abs(os.getenv("MOODREEL_MODEL_DIR", str(BASE_DIR / "models"))))

# 腾讯 AI 情感分析 API（备选中文通道；当前默认用百度，见下）
TENCENT_APPID = os.getenv("TENCENT_APPID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
TENCENT_ENABLED = os.getenv("TENCENT_ENABLED", "false").lower() == "true"

# 百度 AI 情感倾向分析 API（中文通道，默认）
# 文档：https://cloud.baidu.com/product/nlp_apply/sentiment_classify
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")       # 百度智能云 API Key
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")  # 百度智能云 Secret Key
BAIDU_ENABLED = os.getenv("BAIDU_ENABLED", "false").lower() == "true"

# DeepSeek 大模型情感分析（OpenAI 兼容；中文/英文皆可，用于评论批量补标）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_ENABLED = os.getenv("DEEPSEEK_ENABLED", "false").lower() == "true"

# 监听
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
