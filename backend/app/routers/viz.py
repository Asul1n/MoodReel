"""可视化模块路由：图表聚合数据 + 词云图片。"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import analytics, wordcloud_img

router = APIRouter(prefix="/viz", tags=["viz"])
logger = logging.getLogger("moodreel")


@router.get("/wordcloud")
def wordcloud(
    context: str = Query("whole", description="whole 或 movie:{movie_id}"),
    top_n: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Response:
    """返回词云 PNG 图片（前端 Image 直接加载该 URL）。"""
    cloud = analytics.hotspot(db, context, top_n=top_n)["cloud"]
    t0 = time.perf_counter()
    try:
        png = wordcloud_img.build(cloud)
    except Exception as exc:
        logger.error("词云渲染失败 context=%s: %s", context, exc)
        raise HTTPException(status_code=500, detail=f"词云渲染失败：{exc}")
    ms = (time.perf_counter() - t0) * 1000
    logger.info("生成词云 context=%s 输入%d词 实际画%d词 大小=%.0fKB 耗时=%.0fms",
                context, len(cloud), wordcloud_img._last_placed,
                len(png) / 1024, ms)
    return Response(content=png, media_type="image/png")


@router.get("/summary")
def summary(
    context: str = Query("whole", description="whole 或 movie:{movie_id}"),
    top_n: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """一次返回：dist(分布) / trend(趋势) / top_words / cloud / polarity，供可视化页。"""
    return analytics.summary(db, context, top_n=top_n)
