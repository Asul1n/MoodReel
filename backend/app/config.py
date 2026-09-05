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

# 本地静态资源（下载到本地的海报等，经 /static 伺服）
STATIC_DIR = BASE_DIR / "static"

# 腾讯 AI 情感分析 API（备选中文通道；当前默认用百度，见下）
TENCENT_APPID = os.getenv("TENCENT_APPID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
TENCENT_ENABLED = os.getenv("TENCENT_ENABLED", "false").lower() == "true"

# DeepSeek 大模型情感分析（OpenAI 兼容；唯一中文通道，正/负二类 + 置信度）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_ENABLED = os.getenv("DEEPSEEK_ENABLED", "false").lower() == "true"

# 豆瓣反爬池（可选，默认匿名单会话）
def _list_env(name: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, "").splitlines() if s.strip()]


def _douban_cookies() -> list[str]:
    """多账号 cookie：DOUBAN_COOKIES 及其 _2/_3/_4/_5，各存一条完整 Cookie。"""
    out: list[str] = []
    for idx in (None, 2, 3, 4, 5):
        v = os.getenv("DOUBAN_COOKIES" if idx is None else f"DOUBAN_COOKIES_{idx}", "")
        if v.strip():
            out.append(v.strip())
    return out


DOUBAN_COOKIES = _douban_cookies()
DOUBAN_PROXIES = _list_env("DOUBAN_PROXIES")     # 代理，每行一个，如 http://user:pass@ip:port
DOUBAN_WORKERS = int(os.getenv("DOUBAN_WORKERS", "1"))  # 并发数（默认低调=1）

# 监听
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
