"""分歧分析与分歧榜路由（规格 §7）。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models
from ..db import get_db
from ..services.analytics import source_terms_from_db
from ..services.divergence import SourceStat, compute_divergence

router = APIRouter(tags=["divergence"])

# 站点 → 该站评论在 Review 表中的 source 标记
_SOURCE_TO_REVIEW = {"bangumi": "bangumi_live", "bilibili": "bilibili_live",
                     "anilist": "anilist_live", "mal": "mal_live"}


def _stats_of(rows: list[models.AnimeSource]) -> list[SourceStat]:
    """DB 行 → 引擎入参，顺带把各站分制归一到 10 分制。"""
    out: list[SourceStat] = []
    for s in rows:
        norm = None
        if s.rating_raw is not None and s.rating_scale:
            norm = s.rating_raw * (10.0 / s.rating_scale)
        out.append(SourceStat(
            source=s.source, rating_norm=norm, rating_count=s.rating_count,
            pos=s.sentiment_pos, neg=s.sentiment_neg, review_count=s.review_count))
    return out


def _compute(db: Session, anime_id: str):
    anime = db.get(models.Anime, anime_id)
    if anime is None:
        raise HTTPException(404, "番剧不存在")
    rows = db.query(models.AnimeSource).filter_by(anime_id=anime_id).all()
    result = compute_divergence(
        _stats_of(rows),
        thr_r=config.ANIME_THR_R, thr_s=config.ANIME_THR_S, m=config.ANIME_BAYES_M,
        min_rating_count=config.ANIME_MIN_RATING_COUNT,
        min_reviews=config.ANIME_MIN_REVIEWS,
        low_conf_weight=config.ANIME_LOW_CONF_WEIGHT)
    return anime, rows, result


def _attribution(db: Session, anime_id: str) -> dict:
    """各站已入库评论 → 分站独有褒贬词（规格 §6.5）。"""
    present = {s.source: _SOURCE_TO_REVIEW[s.source]
               for s in db.query(models.AnimeSource).filter_by(anime_id=anime_id).all()
               if s.source in _SOURCE_TO_REVIEW}
    if len(present) < 2:
        return {}
    return source_terms_from_db(db, anime_id, present, top_n=15)


def _payload(anime, rows, result, db: Session, anime_id: str) -> dict:
    participated = set(result.sources_rating) | set(result.sources_sentiment)
    return {
        "anime_id": anime_id,
        "title_cn": anime.title_cn,
        "status": result.status,
        "reason": result.reason,
        "d_rating": result.d_rating,
        "d_sentiment": result.d_sentiment,
        "quadrant": result.quadrant,
        "sources_used": {"rating": result.sources_rating,
                         "sentiment": result.sources_sentiment},
        # 有已入库站点一个指标都没参与 → 结果打了折扣，如实标注
        "degraded": len(participated) < len(rows),
        "ratings": result.ratings,
        "sentiment": result.sentiment,
        "attribution": {"per_source": _attribution(db, anime_id)},
        "computed_at": datetime.utcnow().isoformat(),
    }


@router.get("/divergence/{anime_id}")
def divergence(anime_id: str, refresh: bool = False,
               db: Session = Depends(get_db)) -> dict:
    """单番分歧结果；命中缓存直接返回（规格 §11 第 5 条）。"""
    cached = db.get(models.Divergence, anime_id)
    if cached is not None and not refresh:
        payload = json.loads(cached.payload or "{}")
        payload["cached"] = True
        return payload

    anime, rows, result = _compute(db, anime_id)
    payload = _payload(anime, rows, result, db, anime_id)
    payload["cached"] = False

    if result.status == "ok":
        row = cached or models.Divergence(anime_id=anime_id)
        row.d_rating = result.d_rating
        row.d_sentiment = result.d_sentiment
        row.quadrant = result.quadrant
        row.sources_rating = ",".join(result.sources_rating)
        row.sources_sentiment = ",".join(result.sources_sentiment)
        row.degraded = payload["degraded"]
        row.payload = json.dumps(payload, ensure_ascii=False)
        row.computed_at = datetime.utcnow()
        db.add(row)
        db.commit()
    return payload


@router.get("/ranking/divergence")
def ranking(quadrant: str | None = None, sort: str = "d_sentiment",
            limit: int = 20, offset: int = 0,
            db: Session = Depends(get_db)) -> dict:
    """分歧榜。未缓存的番剧按需实时计算并落缓存（规格 §7）。"""
    anime_rows = db.execute(select(models.Anime).limit(200)).scalars().all()

    items: list[dict] = []
    for a in anime_rows:
        cached = db.get(models.Divergence, a.anime_id)
        if cached is None:
            try:
                _, _, res = _compute(db, a.anime_id)
            except HTTPException:
                continue
            if res.status != "ok" or res.quadrant is None:
                continue
            cached = models.Divergence(
                anime_id=a.anime_id, d_rating=res.d_rating,
                d_sentiment=res.d_sentiment, quadrant=res.quadrant,
                sources_rating=",".join(res.sources_rating),
                sources_sentiment=",".join(res.sources_sentiment))
            db.add(cached)
            db.commit()
        if cached.quadrant is None:
            continue
        if quadrant and cached.quadrant != quadrant:
            continue
        items.append({
            "anime_id": a.anime_id, "title_cn": a.title_cn, "year": a.year,
            "d_rating": cached.d_rating, "d_sentiment": cached.d_sentiment,
            "quadrant": cached.quadrant,
        })

    key = sort if sort in ("d_rating", "d_sentiment") else "d_sentiment"
    items.sort(key=lambda x: (x[key] is None, -(x[key] or 0)))
    return {"total": len(items), "items": items[offset:offset + limit]}
