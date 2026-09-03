"""MoodReel 后端服务中枢入口。

启动：uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .db import init_db
from .routers import crawl, dataset, hotspot, sentiment, viz
from .services import textcnn

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    textcnn.load()  # 惰性：缺 torch/模型时不报错，仅 model_ready=False
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
