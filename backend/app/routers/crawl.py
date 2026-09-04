"""采集模块路由：发起双源抓取 job + 轮询进度 + 影片列表/详情。"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..crawler import runner, samples
from ..db import get_db

router = APIRouter(prefix="/crawl", tags=["crawl"])

_META_KEYS = ("intro", "poster", "rating", "genres")


class CrawlStart(BaseModel):
    source: str = Field(pattern="^(imdb|douban)$")
    query: str = Field(min_length=1, max_length=200, description="片名或 movie_id")
    limit: int = Field(200, ge=1, le=500)


# 注意：静态路由 /movies、/movie/{id} 必须声明在动态路由 /{job_id} 之前，避免被抢占匹配。


@router.get("/movies", response_model=list[dict])
def movies(db: Session = Depends(get_db)) -> list[dict]:
    """候选影片：已入库（crawl，含简介/海报/评分）+ 离线样本包（offline）。"""
    out: list[dict] = []
    seen: set[str] = set()
    for m in db.query(models.Movie).order_by(models.Movie.created_at.desc()).limit(200).all():
        seen.add(m.movie_id)
        item = {
            "movie_id": m.movie_id, "title": m.title, "year": m.year,
            "source": m.source, "source_url": m.source_url, "available": "crawl",
        }
        for k in _META_KEYS:
            item[k] = getattr(m, k, None)
        out.append(item)
    for sm in samples.list_sample_movies():
        if sm.movie_id in seen:
            continue
        item = {
            "movie_id": sm.movie_id, "title": sm.title, "year": sm.year,
            "source": sm.source, "source_url": None, "available": "offline",
            "note": sm.note,
        }
        for k in _META_KEYS:
            item[k] = None
        out.append(item)
    return out


@router.get("/movie/{movie_id}")
def movie_detail(movie_id: str, db: Session = Depends(get_db)) -> dict:
    """单部影片详情（简介/海报/评分/类型 + 已抓评论数），供前端简介页。"""
    m = db.get(models.Movie, movie_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"影片不存在：{movie_id}")
    review_count = db.scalar(
        select(func.count(models.Review.id)).where(models.Review.movie_id == movie_id)
    ) or 0
    item = {
        "movie_id": m.movie_id, "title": m.title, "year": m.year,
        "source": m.source, "source_url": m.source_url, "review_count": review_count,
    }
    for k in _META_KEYS:
        item[k] = getattr(m, k, None)
    return item


@router.post("", status_code=201)
def start_crawl(payload: CrawlStart, db: Session = Depends(get_db)) -> dict:
    """登记任务并交给后台线程执行（runner）。"""
    job = models.CrawlJob(
        job_id=uuid.uuid4().hex,
        source=payload.source,
        query=payload.query,
        limit=payload.limit,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    runner.start(job.job_id)
    return {"job_id": job.job_id}


@router.get("/{job_id}")
def job_status(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = db.get(models.CrawlJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "fetched": job.fetched,
        "limit": job.limit,
        "error": job.error,
        "degraded": job.status == "degraded",
    }
