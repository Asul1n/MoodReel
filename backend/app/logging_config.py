"""日志配置：控制台 + 滚动文件 backend/logs/moodreel.log。

用法：app.main 顶部调用 setup_logging()；各模块用
    import logging; logger = logging.getLogger("moodreel")
记录关键事件（启动/模型加载/抓取任务/补标/新增）与异常，便于排错和作为实践文档素材。
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger("moodreel")


def setup_logging(level: int = logging.INFO) -> None:
    """幂等配置：只加一次 handler；独立 logger（propagate=False 避免与 uvicorn 重复）。"""
    if logger.handlers:
        return
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)
    fmt = logging.Formatter(_FMT)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file = RotatingFileHandler(
        _LOG_DIR / "moodreel.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file.setFormatter(fmt)

    logger.addHandler(console)
    logger.addHandler(file)
    logger.propagate = False
