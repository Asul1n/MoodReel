"""采集模块路由：发起双源抓取 job + 轮询进度。"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/crawl", tags=["crawl"])


class CrawlStart(BaseModel):
    source: str = Field(pattern="^(imdb|douban)$")
    query: str = Field(min_length=1, max_length=200, description="片名或 movie_id")
    limit: int = Field(60, ge=1, le=100)


# 注意：静态路由 /movies 必须声明在动态路由 /{job_id} 之前，避免被抢占匹配。


@router.get("/movies", response_model=list[dict])
def movies(db: Session = Depends(get_db)) -> list[dict]:
    """预置 + 已采集影片列表（App 选片用）。成员A：并入 sample_pack 预置影片。"""
    rows = db.query(models.Movie).order_by(models.Movie.created_at.desc()).limit(200).all()
    return [
        {"movie_id": m.movie_id, "title": m.title, "year": m.year,
         "source": m.source, "source_url": m.source_url}
        for m in rows
    ]


@router.post("", status_code=201)
def start_crawl(payload: CrawlStart, db: Session = Depends(get_db)) -> dict:
    """登记抓取任务。成员A：在此把 job 交给后台线程执行（crawler.imdb/douban）。"""
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
    # TODO(成员A): start background execution of `job` and update status/fetched
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
