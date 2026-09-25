"""动漫域路由：跨站检索 / 采集 / 单番各站数据（规格 §7）。"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.adapters import get_adapter
from ..services.identity import match_candidates

router = APIRouter(prefix="/anime", tags=["anime"])

# 归并阈值：低于此分不认为是同一部番（宁可漏合并，不可误合并）
MATCH_THRESHOLD = 0.7

# 锚点优先级：决定 anime_id 形如 "<source>:<source_id>"，影响可读性与稳定性
ANCHOR_PRIORITY = ["bangumi", "bilibili", "anilist", "mal"]


@router.get("/search")
def search(q: str, sources: str = "bangumi,bilibili",
           db: Session = Depends(get_db)) -> dict:
    """跨站检索并按归并结果聚合候选番剧。

    单站失败不阻断整体检索：其结果记入 errors，其余站点照常返回。
    """
    query = (q or "").strip()
    wanted = [s.strip() for s in (sources or "").split(",") if s.strip()]
    errors: list[dict] = []
    if not query:
        return {"items": [], "errors": errors}

    per_source: dict[str, list] = {}
    for src in wanted:
        adapter = get_adapter(src)
        if adapter is None:
            errors.append({"source": src, "reason": "v1 未实现该站点"})
            continue
        res = adapter.search(query)
        if not res.ok:
            errors.append({"source": src, "reason": res.error})
            continue
        per_source[src] = list(res.data or [])

    # 以首个有结果的站点为锚点，其余站点按归并匹配并入同一条
    items: list[dict] = []
    anchor_src = next((s for s in wanted if per_source.get(s)), None)
    if anchor_src:
        for anchor in per_source[anchor_src]:
            group = [{"source": anchor.source, "source_id": anchor.source_id,
                      "title": anchor.title_cn, "year": anchor.year,
                      "url": anchor.url}]
            for other in wanted:
                if other == anchor_src:
                    continue
                match = match_candidates(anchor, per_source.get(other, []),
                                         threshold=MATCH_THRESHOLD)
                if match:
                    group.append({"source": match.source, "source_id": match.source_id,
                                  "title": match.title_cn, "year": match.year,
                                  "url": match.url})
                    # 已被归并的候选不再单独成条
                    per_source[other] = [c for c in per_source[other]
                                         if c.source_id != match.source_id]
            items.append({
                "anime_id": None,          # 尚未入库；ingest 后分配
                "title_cn": anchor.title_cn,
                "title_jp": anchor.title_jp,
                "title_en": anchor.title_en,
                "year": anchor.year,
                "episodes": anchor.episodes,
                "sources": group,
            })

    return {"items": items, "errors": errors}


class IngestIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    year: int | None = None
    sources: list[str] = Field(default_factory=lambda: ["bangumi", "bilibili"])
    limit: int = Field(200, ge=1, le=1000)
    refresh: bool = False


@router.post("/ingest", status_code=201)
def ingest(body: IngestIn, db: Session = Depends(get_db)) -> dict:
    """跨站采集一部番：建 Anime/AnimeSource，落 CrawlJob 供前端轮询。

    v1 范围：同步完成**元数据与评分**入库（快、稳定，够算评分分歧）。
    评论正文的批量采集是独立步骤，未完成时 /divergence 会如实返回
    insufficient_data，而不是给出没有依据的结论。
    """
    found: list[tuple[str, object]] = []
    for src in body.sources:
        adapter = get_adapter(src)
        if adapter is None:
            raise HTTPException(400, f"v1 未实现站点：{src}")
        res = adapter.search(body.title)
        if not res.ok:
            raise HTTPException(502, f"{src} 检索失败：{res.error}")
        for cand in (res.data or []):
            # 年份相差 1 年以上视为不同作品（放送跨年常见，故容差 1 年）
            if body.year and cand.year and abs(cand.year - body.year) > 1:
                continue
            found.append((src, cand))
            break

    if not found:
        raise HTTPException(404, "各站均未检索到该番剧")

    found.sort(key=lambda x: ANCHOR_PRIORITY.index(x[0])
               if x[0] in ANCHOR_PRIORITY else len(ANCHOR_PRIORITY))
    anchor_src, anchor = found[0]
    anime_id = f"{anchor_src}:{anchor.source_id}"

    anime = db.get(models.Anime, anime_id)
    if anime is None:
        anime = models.Anime(anime_id=anime_id)
        db.add(anime)

    for src, cand in found:
        adapter = get_adapter(src)
        meta_res = adapter.fetch_meta(cand.source_id)
        if meta_res.ok and meta_res.data:
            m = meta_res.data
            anime.title_cn = anime.title_cn or m.title_cn or cand.title_cn
            anime.title_jp = anime.title_jp or m.title_jp
            anime.title_en = anime.title_en or m.title_en
            anime.year = anime.year or m.year
            anime.episodes = anime.episodes or m.episodes
            anime.studio = anime.studio or m.studio
            anime.synopsis = anime.synopsis or m.synopsis
            anime.poster_url = anime.poster_url or m.poster_url

        row = db.query(models.AnimeSource).filter_by(
            anime_id=anime_id, source=src).first()
        if row is None:
            row = models.AnimeSource(anime_id=anime_id, source=src,
                                     source_id=cand.source_id)
            db.add(row)
        row.url = cand.url
        rating_res = adapter.fetch_rating(cand.source_id)
        if rating_res.ok and rating_res.data:
            row.rating_raw = rating_res.data.score_raw
            row.rating_scale = rating_res.data.scale
            row.rating_count = rating_res.data.count
        row.fetched_at = datetime.utcnow()

    job = models.CrawlJob(job_id=uuid.uuid4().hex, source=anchor_src,
                          query=body.title, limit=body.limit,
                          refresh=body.refresh, status="done", fetched=0)
    db.add(job)
    db.commit()

    return {"job_id": job.job_id, "anime_id": anime_id,
            "sources": [s for s, _ in found]}


@router.get("/{anime_id}/sources")
def anime_sources(anime_id: str, db: Session = Depends(get_db)) -> dict:
    """单番各站原始数据（规格 §7）。

    与 /divergence 的分工：这里给**原始**分站数据（含未进入分歧计算的站），
    /divergence 给**计算结果**。前端两者都用。
    """
    anime = db.get(models.Anime, anime_id)
    if anime is None:
        raise HTTPException(404, "番剧不存在")
    rows = db.query(models.AnimeSource).filter_by(anime_id=anime_id).all()
    return {
        "anime": {
            "anime_id": anime.anime_id,
            "title_cn": anime.title_cn, "title_jp": anime.title_jp,
            "title_en": anime.title_en, "year": anime.year,
            "episodes": anime.episodes, "studio": anime.studio,
            "synopsis": anime.synopsis, "poster_url": anime.poster_url,
        },
        "sources": [{
            "source": s.source, "source_id": s.source_id, "url": s.url,
            "rating_raw": s.rating_raw, "rating_scale": s.rating_scale,
            "rating_count": s.rating_count, "rating_weighted": s.rating_weighted,
            "review_count": s.review_count,
            "sentiment": {"pos": s.sentiment_pos, "neg": s.sentiment_neg,
                          "mean": s.sentiment_mean},
            "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
        } for s in rows],
    }
