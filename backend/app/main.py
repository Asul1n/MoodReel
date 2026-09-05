"""MoodReel 后端服务中枢入口。

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .db import init_db
from .logging_config import logger, setup_logging
from .routers import crawl, dataset, hotspot, sentiment, viz
from .services import textcnn, textcnn_zh

setup_logging()

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    textcnn.load()      # 英文 TextCNN
    textcnn_zh.load()   # 中文 TextCNN（model_zh.pt，可缺）
    logger.info("后端启动完成 en_model=%s zh_model=%s", textcnn.is_ready(), textcnn_zh.is_ready())
    if not textcnn.is_ready():
        logger.warning("英文 TextCNN 未就绪：%s", textcnn.status()["msg"])
    yield


app = FastAPI(title="MoodReel 后端服务中枢", version=VERSION, lifespan=lifespan)

# 开发期允许任意来源（App 局域网访问）；上线收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=None, tags=["health"])
def health() -> dict:
    return {
        "ok": True,
        "model_ready": textcnn.is_ready(),
        "model": textcnn.status(),
        "version": VERSION,
    }


app.include_router(dataset.router)
app.include_router(crawl.router)
app.include_router(sentiment.router)
app.include_router(hotspot.router)
app.include_router(viz.router)

# 本地静态资源（下载到本地的海报等）
config.STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
