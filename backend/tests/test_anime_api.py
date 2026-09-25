"""动漫接口测试（规格 §7）。

用假适配器注入，不依赖外网——适配器契约已在 test_adapters_* 覆盖。
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.adapters.base import Candidate, failed, ok

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
