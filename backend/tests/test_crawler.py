"""离线样本 + runner 最小闭环测试（不访问外网）。"""
import time
import uuid

from fastapi.testclient import TestClient

from app import models
from app.crawler import runner, samples
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def _new_job(source: str = "imdb", query: str = "Shawshank", limit: int = 10) -> str:
    with SessionLocal() as db:
        job = models.CrawlJob(job_id=uuid.uuid4().hex, source=source,
                              query=query, limit=limit, status="pending")
        db.add(job)
        db.commit()
        return job.job_id


def test_sample_manifest_and_load():
    movies = samples.list_sample_movies()
    assert len(movies) >= 2  # imdb + douban 各一部
    im = samples.find_movie("imdb", "shawshank") or samples.find_movie("imdb", "tt0111161")
    assert im is not None
    items = samples.load_sample(im)
    assert len(items) > 0
    assert all(it.text for it in items)


def test_runner_offline_loop_degraded_and_ingest():
    job_id = _new_job()
    runner._run(job_id)  # 同步跑，验证逻辑

    with SessionLocal() as db:
        job = db.get(models.CrawlJob, job_id)
        assert job.status == "degraded"
        assert job.fetched > 0
        n_sample = db.query(models.Review).filter(
            models.Review.source == "imdb_sample").count()
        movie = db.query(models.Movie).get("imdb:tt0111161")
    assert n_sample == job.fetched
    assert movie is not None
    assert movie.source == "imdb"


def test_runner_unknown_title_fails_cleanly():
    job_id = _new_job(query="A Movie Not In Sample Pack 99999")
    runner._run(job_id)
    with SessionLocal() as db:
        job = db.get(models.CrawlJob, job_id)
    assert job.status == "failed"
    assert "未收录" in (job.error or "")


def test_crawl_endpoint_returns_degraded_after_poll():
    r = client.post("/crawl", json={"source": "imdb",
                                    "query": "The Shawshank Redemption", "limit": 10})
    assert r.status_code == 201
    job_id = r.json()["job_id"]

    status = None
    for _ in range(100):
        body = client.get(f"/crawl/{job_id}").json()
        if body["status"] not in ("pending", "running"):
            status = body["status"]
            break
        time.sleep(0.05)
    assert status == "degraded"


def test_movies_lists_offline_candidates():
    body = client.get("/crawl/movies").json()
    kinds = {m.get("available") for m in body}
    assert "offline" in kinds
    assert any(m["movie_id"] == "imdb:tt0111161" for m in body)
