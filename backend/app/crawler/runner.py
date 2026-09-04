"""采集任务执行器（成员A）。

流程：后台线程执行 crawl job —— 先尝试在线抓取（IMDB/豆瓣），失败/未实现再走
sample_pack 离线样本兜底（status=degraded）。在线抓取成功后，会顺带抓取影片
元数据（简介/海报/评分/类型）写入 movies 表，供前端展示简介。

入库命名：
    在线抓取   -> reviews.source = imdb_live / douban_live
    离线样本   -> reviews.source = imdb_sample / douban_sample
"""
import logging
import threading

import requests

from .. import config, models
from ..db import SessionLocal
from . import samples
from .base import MovieRef
from .douban import DoubanCrawler
from .imdb import ImdbCrawler

CRAWLERS = {"imdb": ImdbCrawler(), "douban": DoubanCrawler()}
# 离线样本来源 => reviews.source
SAMPLE_SOURCE = {"imdb": "imdb_sample", "douban": "douban_sample"}

logger = logging.getLogger("moodreel")
_META_FIELDS = ("title", "year", "intro", "poster", "rating", "genres")


def start(job_id: str) -> None:
    """在后台线程执行任务（不阻塞 HTTP 请求）。"""
    threading.Thread(target=_run, args=(job_id,), daemon=True).start()


def _run(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(models.CrawlJob, job_id)
        if job is None or job.status != "pending":
            return
        _set(db, job, status="running")
        try:
            if not _try_online(db, job):
                _fallback_offline(db, job)
        except Exception as exc:  # 无论什么异常，任务都不卡死
            db.rollback()
            _set(db, job, status="failed", error=f"采集异常：{exc}")
        logger.info("crawl job=%s source=%s query=%s status=%s fetched=%s",
                    job.job_id, job.source, job.query, job.status, job.fetched)


def _try_online(db, job) -> bool:
    """真实抓取：成功入库返回 True；未实现/无结果/异常返回 False（走离线兜底）。"""
    crawler = CRAWLERS.get(job.source)
    if crawler is None:
        return False
    try:
        refs = crawler.search(job.query)
        if not refs:
            logger.info("搜索无结果 query=%s source=%s（转离线样本）", job.query, job.source)
            return False
        movie = refs[0]
        logger.info("解析到影片 %s《%s》%s",
                    movie.movie_id, movie.title, f"({movie.year})" if movie.year else "")
        # 幂等/缓存：refresh=false 且该片已有在线评论 -> 复用跳过重抓
        if not getattr(job, "refresh", False):
            live_src = f"{movie.source}_live"
            existing = db.query(models.Review).filter(
                models.Review.movie_id == movie.movie_id,
                models.Review.source == live_src).count()
            if existing:
                _set(db, job, status="done", fetched=existing,
                     error=f"该片已有 {existing} 条评论，已复用跳过抓取（refresh=true 可强制重抓）")
                logger.info("影片 %s 已有 %s 条评论，跳过抓取（refresh=true 可强制重抓）",
                            movie.movie_id, existing)
                return True
        logger.info("开始在线抓取影片 %s，limit=%s", movie.movie_id, job.limit)
        items = crawler.fetch(movie, job.limit)
        if not items:
            logger.warning("影片 %s 抓到 0 条（转离线样本）", movie.movie_id)
            return False
    except NotImplementedError:
        return False  # 在线爬虫尚未实现
    except Exception:
        return False  # 网络/解析失败 → 兜底
    _store(db, job, movie, f"{movie.source}_live", items)
    _apply_meta(db, crawler, movie)   # 顺带抓影片简介等（best-effort）
    _set(db, job, status="done", fetched=len(items))
    return True


def _localize_poster(movie: MovieRef, url: str) -> str | None:
    """把豆瓣海报下载到本地 static/posters/，返回本地路径；失败返回 None。

    目的：绕开豆瓣图床防盗/Referer 校验，让前端始终只连我们后端。
    """
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": "https://movie.douban.com/",
        }, timeout=20)
        if r.status_code != 200 or not r.content:
            return None
        d = config.STATIC_DIR / "posters"
        d.mkdir(parents=True, exist_ok=True)
        fn = movie.movie_id.replace(":", "_") + ".jpg"
        (d / fn).write_bytes(r.content)
        return f"/static/posters/{fn}"
    except Exception:
        return None


def _apply_meta(db, crawler, movie: MovieRef) -> None:
    """把豆瓣详情接口的影片元数据写进 movies（失败静默，不强依赖）。"""
    fetch_meta = getattr(crawler, "movie_meta", None)
    if fetch_meta is None:
        return
    try:
        meta = fetch_meta(movie) or {}
    except Exception:
        return
    if not meta:
        return
    m = db.get(models.Movie, movie.movie_id)
    if m is None:
        return
    for field in _META_FIELDS:
        if meta.get(field) is not None:
            setattr(m, field, meta[field])
    intro = meta.get("intro") or ""
    logger.info("抓取到影片元数据 %s《%s》: 类型=%s 评分=%s",
                movie.movie_id, meta.get("title") or movie.title,
                meta.get("genres"), meta.get("rating"))
    if intro:
        logger.info("影片简介 %s: %s", movie.movie_id,
                    intro[:80] + "…" if len(intro) > 80 else intro)
    # 海报：优先下载到本地伺服，规避豆瓣防盗；失败则保留原外链
    poster = meta.get("poster")
    if poster and str(poster).startswith("http"):
        logger.info("开始下载海报 %s <- %s", movie.movie_id, str(poster)[:80])
        local = _localize_poster(movie, str(poster))
        if local:
            m.poster = local
            logger.info("海报已保存到本地 %s", local)
        else:
            logger.warning("海报本地下载失败，保留豆瓣外链 %s", movie.movie_id)
    db.commit()


def _fallback_offline(db, job) -> None:
    movie = samples.find_movie(job.source, job.query)
    if movie is None:
        _set(db, job, status="failed",
             error=f"在线抓取不可用，且离线样本未收录：{job.query}")
        return
    items = samples.load_sample(movie)
    if not items:
        _set(db, job, status="failed", error=f"离线样本为空：{movie.movie_id}")
        return
    source_label = SAMPLE_SOURCE.get(job.source, f"{job.source}_sample")
    _store(db, job, movie.to_movie_ref(), source_label, items)
    _set(db, job, status="degraded", fetched=len(items),
         error=f"在线抓取未就绪，已用离线样本兜底：{movie.title}")


def _store(db, job, movie: MovieRef, source_label: str, items: list) -> None:
    """把影片 + 影评落库。movie upsert；重复抓取同一 source 先清旧评（幂等）。"""
    m = db.get(models.Movie, movie.movie_id)
    if m is None:
        m = models.Movie(
            movie_id=movie.movie_id, title=movie.title, year=movie.year,
            source=movie.source, source_url=movie.source_url,
        )
        db.add(m)
    else:
        m.title = movie.title
        m.year = movie.year

    db.query(models.Review).filter(
        models.Review.movie_id == movie.movie_id,
        models.Review.source == source_label,
    ).delete(synchronize_session=False)

    lang = "zh" if movie.source == "douban" else "en"
    db.add_all([
        models.Review(movie_id=movie.movie_id, source=source_label, lang=lang,
                      text=item.text.strip(), stars=item.stars,
                      review_time=getattr(item, "time", None))
        for item in items if item.text.strip()
    ])
    db.commit()


def _set(db, job, status: str | None = None, error: str | None = None,
         fetched: int | None = None) -> None:
    if status is not None:
        job.status = status
    if error is not None:
        job.error = error
    if fetched is not None:
        job.fetched = fetched
    db.commit()
