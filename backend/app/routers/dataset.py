"""语料模块（静态 IMDB + 动态采集 + 手动新增）：浏览/筛选/统计/新增。"""
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import analytics, deepseek, textcnn

router = APIRouter(prefix="/dataset", tags=["dataset"])
_CJK = re.compile(r"[一-鿿]")
logger = logging.getLogger("moodreel")


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


class IngestRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=500)
    source: str = Field("manual", pattern="^(manual|imdb_static)$")
    movie_id: str | None = None
    analyze: bool = False   # True 时按语言自动补标（en→TextCNN / zh→DeepSeek）


def _detect_lang(text: str) -> str:
    return "zh" if _CJK.search(text) else "en"


def _label_if_possible(review: models.Review) -> None:
    """best-effort：给单条评论补情感标签；缺模型/接口则静默保留未标注。"""
    try:
        if review.lang == "en" and textcnn.is_ready():
            (item,) = textcnn.analyze_batch([review.text])[0][:1]
            review.pred_label, review.pred_prob, review.model = \
                item["label"], item["prob"], "textcnn"
        elif review.lang == "zh" and deepseek.enabled():
            lab = deepseek.classify([review.text])[0]
            review.pred_label, review.pred_prob, review.model = \
                lab["label"], lab["prob"], "deepseek"
    except Exception:
        pass  # 不因补标失败影响新增入库


@router.post("/ingest", status_code=201)
def ingest(payload: IngestRequest, db: Session = Depends(get_db)) -> dict:
    """手动新增/导入评论并落库；analyze=true 时自动按语言补情感标签。"""
    ids: list[int] = []
    for text in payload.texts:
        text = (text or "").strip()
        if not text:
            continue
        review = models.Review(
            movie_id=payload.movie_id,
            source=payload.source,
            lang=_detect_lang(text),
            text=text,
            created_at=datetime.utcnow(),
        )
        db.add(review)
        db.flush()          # 取 id
        if payload.analyze:
            _label_if_possible(review)
        ids.append(review.id)
    db.commit()
    logger.info("ingest count=%s analyze=%s ids=%s", len(ids), payload.analyze, ids[:20])
    return {"ids": ids, "count": len(ids), "analyze": payload.analyze}
