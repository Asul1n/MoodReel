"""评论热点挖掘模块路由：Top 热点词 / 词云 / 褒贬倾向词。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import analytics

router = APIRouter(prefix="/hotspot", tags=["hotspot"])


@router.get("")
def hotspot(
    context: str = Query("whole", description="whole 或 movie:{movie_id}"),
    top_n: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """返回 keywords / cloud / polarity.{pos,neg}，供热点页与词云渲染。"""
    return analytics.hotspot(db, context, top_n=top_n)
