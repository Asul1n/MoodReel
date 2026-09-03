"""语料模块（静态 IMDB + 动态采集 + 手动新增）：浏览/筛选/统计。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import analytics

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("/stats")
def stats(context: str = Query("whole", description="whole 或 movie:{movie_id}"),
          db: Session = Depends(get_db)) -> dict:
    """情感分布统计（按统一口径 label，见 services/analytics.py）。"""
    return analytics.stats(db, context)


@router.get("/reviews", response_model=schemas.ReviewListOut)
def reviews(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sentiment: str | None = Query(None, pattern="^(positive|negative|neutral)$"),
    source: str | None = None,
    lang: str | None = Query(None, pattern="^(en|zh)$"),
    movie_id: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> schemas.ReviewListOut:
    stmt = select(models.Review)
    if sentiment:
        stmt = stmt.where(models.Review.pred_label == sentiment)
    if source:
        stmt = stmt.where(models.Review.source == source)
    if lang:
        stmt = stmt.where(models.Review.lang == lang)
    if movie_id:
        stmt = stmt.where(models.Review.movie_id == movie_id)
    if q:
        stmt = stmt.where(models.Review.text.contains(q))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(models.Review.id.desc()).offset(offset).limit(limit)).all()
    return schemas.ReviewListOut(
        total=total,
        items=[
            schemas.ReviewOut(
                id=r.id, text=r.text, lang=r.lang, source=r.source,
                movie_id=r.movie_id, ground_truth=r.ground_truth,
                pred_label=r.pred_label, pred_prob=r.pred_prob,
            )
            for r in rows
        ],
    )


@router.post("/ingest", status_code=201)
def ingest(payload: schemas.AnalyzeRequest, db: Session = Depends(get_db)) -> dict:
    """手动新增/导入评论并落库。TODO：落库后调情感接口补标，返回 id 列表。"""
    raise HTTPException(status_code=501, detail="待实现：落库 + 语言路由自动分析")
