"""语料模块（静态 IMDB + 手动新增）：浏览/筛选/统计。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count(models.Review.id))) or 0
    pos = db.scalar(
        select(func.count(models.Review.id)).where(models.Review.pred_label == "positive")
    ) or 0
    neg = db.scalar(
        select(func.count(models.Review.id)).where(models.Review.pred_label == "negative")
    ) or 0
    sources = dict(
        db.execute(
            select(models.Review.source, func.count()).group_by(models.Review.source)
        ).all()
    )
    return {
        "total": total,
        "pred_positive": pos,
        "pred_negative": neg,
        "pred_none": total - pos - neg,
        "by_source": sources,
    }


@router.get("/reviews", response_model=schemas.ReviewListOut)
def reviews(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sentiment: str | None = Query(None, pattern="^(positive|negative)$"),
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
    """手动新增/导入评论并落库（可选立即分析，接入后补充）。"""
    raise HTTPException(status_code=501, detail="成员A/B实现：落库 + 语言路由自动分析后返回 id 列表")
