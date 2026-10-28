"""搜索行为记录（search_events）测试：POST /crawl 挂钩 + runner 落库时机。

口径（接口契约「推荐约定」）：不新增上报接口 —— POST /crawl 若带有效 token，
任务处理成功且匹配到影片时由 runner 顺带写一条 search_events；游客/无效 token 不写。
"""
import uuid

from fastapi.testclient import TestClient

from app import models
from app.crawler import runner
from app.db import SessionLocal
from app.main import app
from app.services.auth import hash_password, new_token

client = TestClient(app)


def _new_job(source: str = "imdb", query: str = "Shawshank") -> str:
    db = SessionLocal()
    try:
        job = models.CrawlJob(job_id=uuid.uuid4().hex, source=source,
                              query=query, limit=10, status="pending")
        db.add(job)
        db.commit()
        return job.job_id
    finally:
        db.close()


def _user_with_token(username="挂钩用户"):
    db = SessionLocal()
    try:
        u = models.User(username=username, password_hash=hash_password("pass123"),
                        token=new_token())
        db.add(u)
        db.commit()
        return u.id, u.token
    finally:
        db.close()


def _events():
    db = SessionLocal()
    try:
        return [(e.user_id, e.movie_id, e.keyword)
                for e in db.query(models.SearchEvent).all()]
    finally:
        db.close()


def test_start_crawl_passes_user_id_when_token_valid(monkeypatch) -> None:
    uid, token = _user_with_token()
    seen = {}
    monkeypatch.setattr(runner, "start",
                        lambda job_id, user_id=None: seen.update(job_id=job_id, user_id=user_id))

    r = client.post("/crawl", json={"source": "imdb", "query": "Shawshank"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert seen["job_id"] == r.json()["job_id"]
    assert seen["user_id"] == uid


def test_start_crawl_guest_or_bad_token_passes_none(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(runner, "start",
                        lambda job_id, user_id=None: seen.update(user_id=user_id))

    r = client.post("/crawl", json={"source": "imdb", "query": "Shawshank"})
    assert r.status_code == 201
    assert seen["user_id"] is None                    # 游客不记录

    r = client.post("/crawl", json={"source": "imdb", "query": "Shawshank"},
                    headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 201                       # 无效 token 不报错，按游客处理
    assert seen["user_id"] is None


def test_runner_records_event_on_matched_movie() -> None:
    """离线样本兜底也算匹配到影片（degraded）：应写入事件。"""
    uid, _ = _user_with_token()
    job_id = _new_job()
    runner._run(job_id, user_id=uid)                  # 同步执行，不访问外网

    db = SessionLocal()
    try:
        job = db.get(models.CrawlJob, job_id)
        assert job.status == "degraded"
        assert job.movie_id                            # 任务上留痕匹配到的影片
    finally:
        db.close()
    assert _events() == [(uid, job.movie_id, "Shawshank")]


def test_runner_skips_event_for_guest_or_failed_job() -> None:
    job_id = _new_job()
    runner._run(job_id, user_id=None)
    assert _events() == []                            # 游客不写

    uid, _ = _user_with_token()
    job_id = _new_job(query="绝不存在的片名xyz")
    runner._run(job_id, user_id=uid)
    assert _events() == []                            # 失败任务不写
