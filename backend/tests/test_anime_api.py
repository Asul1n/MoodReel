"""动漫接口测试（规格 §7）。

用假适配器注入，不依赖外网——适配器契约已在 test_adapters_* 覆盖。
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.adapters.base import (Candidate, Meta, Rating, failed, ok)

client = TestClient(app)


class _FakeAdapter:
    """按站点名返回可控结果。"""

    def __init__(self, source: str) -> None:
        self.source = source

    def search(self, query: str):
        if self.source == "bangumi":
            return ok("bangumi", [Candidate(source="bangumi", source_id="253",
                                            title_cn="进击的巨人", year=2013)])
        return ok("bilibili", [Candidate(source="bilibili", source_id="4450",
                                         title_cn="进击的巨人", year=2013)])


def test_search_merges_sources(monkeypatch) -> None:
    """跨站检索应把同一部番归并成一条，各站信息并列。"""
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _FakeAdapter(s))

    r = client.get("/anime/search",
                   params={"q": "进击的巨人", "sources": "bangumi,bilibili"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert items[0]["title_cn"] == "进击的巨人"
    assert {s["source"] for s in items[0]["sources"]} == {"bangumi", "bilibili"}


def test_search_reports_source_failure(monkeypatch) -> None:
    """单站失败不应让整个检索 500，而是如实报告原因。"""
    from app.routers import anime as anime_router

    class _FailAdapter:
        source = "bangumi"

        def search(self, query):
            return failed("bangumi", "HTTP 429", http_status=429)

    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _FailAdapter())

    r = client.get("/anime/search", params={"q": "任意", "sources": "bangumi"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["errors"]
    assert "429" in body["errors"][0]["reason"]


def test_search_rejects_unknown_source(monkeypatch) -> None:
    """v1 未实现的站点（如 mal）应如实说明，而非静默跳过。"""
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: None)

    r = client.get("/anime/search", params={"q": "任意", "sources": "mal"})
    assert r.status_code == 200
    assert r.json()["errors"][0]["source"] == "mal"


def test_search_empty_query_ok() -> None:
    r = client.get("/anime/search", params={"q": "   ", "sources": "bangumi"})
    assert r.status_code == 200


# --------------------------------------------------------------------------- #
# POST /anime/ingest
# --------------------------------------------------------------------------- #

class _FullFakeAdapter:
    """带元数据与评分的假适配器（ingest 需要完整契约）。"""

    def __init__(self, source: str) -> None:
        self.source = source

    def search(self, query: str):
        return ok(self.source, [Candidate(source=self.source,
                                          source_id=f"{self.source}-1",
                                          title_cn="进击的巨人", year=2013)])

    def fetch_meta(self, sid: str):
        return ok(self.source, Meta(title_cn="进击的巨人", title_jp="進撃の巨人", year=2013))

    def fetch_rating(self, sid: str):
        return ok(self.source, Rating(score_raw=8.6, scale=10.0, count=1000))

    def fetch_reviews(self, sid: str, limit: int = 200):
        return ok(self.source, [])


def test_ingest_creates_anime_and_source_rows(monkeypatch) -> None:
    """发起采集应建 Anime/AnimeSource 记录并返回 job_id。"""
    from app import models
    from app.db import SessionLocal
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _FullFakeAdapter(s))

    r = client.post("/anime/ingest", json={"title": "进击的巨人",
                                           "sources": ["bangumi", "bilibili"],
                                           "limit": 50})
    assert r.status_code == 201
    body = r.json()
    assert body["job_id"]
    assert body["anime_id"]

    db = SessionLocal()
    try:
        anime = db.get(models.Anime, body["anime_id"])
        assert anime is not None
        assert anime.title_jp == "進撃の巨人"
        srcs = db.query(models.AnimeSource).filter_by(anime_id=body["anime_id"]).all()
        assert {s.source for s in srcs} == {"bangumi", "bilibili"}
        assert all(s.rating_raw == 8.6 for s in srcs)
    finally:
        db.close()


def test_ingest_anchor_decides_anime_id(monkeypatch) -> None:
    """anime_id 由锚点站决定（bangumi 优先）。"""
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _FullFakeAdapter(s))

    r = client.post("/anime/ingest", json={"title": "进击的巨人",
                                           "sources": ["bilibili", "bangumi"]})
    assert r.status_code == 201
    assert r.json()["anime_id"] == "bangumi:bangumi-1"


def test_ingest_idempotent(monkeypatch) -> None:
    """重复 ingest 同一部番不应产生重复的 AnimeSource 行。"""
    from app import models
    from app.db import SessionLocal
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _FullFakeAdapter(s))

    first = client.post("/anime/ingest", json={"title": "进击的巨人",
                                               "sources": ["bangumi"]}).json()
    client.post("/anime/ingest", json={"title": "进击的巨人", "sources": ["bangumi"]})

    db = SessionLocal()
    try:
        rows = db.query(models.AnimeSource).filter_by(anime_id=first["anime_id"]).all()
        assert len(rows) == 1
    finally:
        db.close()


def test_ingest_rejects_unimplemented_source(monkeypatch) -> None:
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: None)
    r = client.post("/anime/ingest", json={"title": "任意", "sources": ["mal"]})
    assert r.status_code == 400


def test_ingest_404_when_no_site_finds_it(monkeypatch) -> None:
    """各站都搜不到应返回 404，而不是建一条空记录。"""
    from app.routers import anime as anime_router

    class _EmptyAdapter:
        source = "bangumi"

        def search(self, query):
            return ok("bangumi", [])

    monkeypatch.setattr(anime_router, "get_adapter", lambda s: _EmptyAdapter())
    r = client.post("/anime/ingest", json={"title": "不存在的番", "sources": ["bangumi"]})
    assert r.status_code == 404
