"""可视化模块路由：一次返回所选上下文的全部图表聚合数据（App 只负责渲染）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import analytics

router = APIRouter(prefix="/viz", tags=["viz"])


@router.get("/summary")
def summary(
    context: str = Query("whole", description="whole 或 movie:{movie_id}"),
    top_n: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """一次返回：dist(分布) / trend(趋势) / top_words / cloud / polarity，供可视化页。"""
    return analytics.summary(db, context, top_n=top_n)
