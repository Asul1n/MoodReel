"""数据分析/可视化聚合测试：用豆瓣离线样本造数（不访问网络）。"""
import uuid

from fastapi.testclient import TestClient

from app import models
from app.crawler import runner
from app.db import SessionLocal
from app.main import app
from app.services import analytics

client = TestClient(app)
MOVIE_CTX = "movie:douban:1292052"


class _NoOnline:
    """把在线爬虫挡掉，强制走离线样本（测试不碰外网、结果确定）。"""
    name = "douban"

    def search(self, query):  # noqa: D102
        raise NotImplementedError

    def fetch(self, movie, limit=60):  # noqa: D102
        raise NotImplementedError


def _seed_douban_sample() -> str:
    """离线采集《肖申克的救赎》样本(8条, 星级 4正/1中性/3负)入库。"""
    orig = runner.CRAWLERS["douban"]
    runner.CRAWLERS["douban"] = _NoOnline()
    job_id = uuid.uuid4().hex
    try:
        with SessionLocal() as db:
            db.add(models.CrawlJob(job_id=job_id, source="douban", query="肖申克的救赎",
                                   limit=10, status="pending"))
            db.commit()
        runner._run(job_id)  # 在线被挡 -> 走离线样本，status=degraded
    finally:
        runner.CRAWLERS["douban"] = orig
    return job_id


def test_stats_distribution_movie():
    _seed_douban_sample()
    with SessionLocal() as db:
        st = analytics.stats(db, MOVIE_CTX)
    assert st["dist"]["positive"] == 4   # 星级 5,5,4,4
    assert st["dist"]["negative"] == 3   # 星级 2,1,2
    assert st["dist"]["neutral"] == 1    # 星级 3
    assert st["total"] == 8


def test_hotspot_polarity_and_cloud():
    _seed_douban_sample()
    with SessionLocal() as db:
        hs = analytics.hotspot(db, MOVIE_CTX, top_n=10)
    assert hs["total_reviews"] == 8
    assert len(hs["keywords"]) > 0
    assert hs["cloud"] == hs["keywords"]
    assert "pos" in hs["polarity"] and "neg" in hs["polarity"]


def test_summary_shape():
    _seed_douban_sample()
    with SessionLocal() as db:
        s = analytics.summary(db, MOVIE_CTX, top_n=10)
    assert s["movie"]["movie_id"] == "douban:1292052"
    assert set(s["dist"]) == {"positive", "negative", "neutral"}
    assert s["total"] == 8
    assert isinstance(s["trend"], list)
    assert isinstance(s["top_words"], list)


def test_router_stats_and_viz():
    _seed_douban_sample()
    r = client.get("/dataset/stats", params={"context": MOVIE_CTX})
    assert r.status_code == 200
    assert r.json()["dist"]["positive"] == 4

    v = client.get("/viz/summary", params={"context": MOVIE_CTX, "top_n": 10})
    assert v.status_code == 200
    body = v.json()
    assert body["total"] == 8
    assert body["movie"]["title"] == "肖申克的救赎"

    h = client.get("/hotspot", params={"context": MOVIE_CTX, "top_n": 10})
    assert h.status_code == 200
    assert h.json()["total_reviews"] == 8
