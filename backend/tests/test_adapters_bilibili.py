"""B站适配器离线测试。

fixture 说明：
- bilibili_season.json 为真实响应的**字段子集**（只保留适配器读取的字段，
  值原样未改），录制自 api.bilibili.com/pgc/view/web/season?season_id=33378
- bilibili_search_blocked.html 为真实的风控响应：HTTP 200 但返回 HTML，
  正是"200 也不能信"的场景，用来说明适配器必须识别被拦而非返回空列表
"""
import pathlib

import pytest

from app.services.adapters.bilibili import BilibiliAdapter

FIX = pathlib.Path(__file__).parent / "fixtures"


def _adapter_returning(payload: str, code: int = 200) -> BilibiliAdapter:
    a = BilibiliAdapter()
    a._http_get = lambda url, params=None: (code, payload)   # type: ignore[method-assign]
    return a


def test_season_rating_parsed() -> None:
    raw = (FIX / "bilibili_season.json").read_text(encoding="utf-8")
    a = _adapter_returning(raw)

    r = a.fetch_rating("33378")
    assert r.status == "ok"
    assert r.data.scale == 10.0          # B站是 10 分制
    assert r.data.score_raw == pytest.approx(9.4)
    assert r.data.count == 103826


def test_season_meta_parsed() -> None:
    raw = (FIX / "bilibili_season.json").read_text(encoding="utf-8")
    a = _adapter_returning(raw)

    r = a.fetch_meta("33378")
    assert r.status == "ok"
    assert r.data.title_cn == "名侦探柯南"
    assert r.data.poster_url.startswith("http")


def test_total_minus_one_means_unknown_episodes() -> None:
    """B站用 total=-1 表示"连载中/集数未知"，不能把 -1 当集数。

    这是从真实响应里发现的边界：名侦探柯南的 total 就是 -1。
    """
    raw = (FIX / "bilibili_season.json").read_text(encoding="utf-8")
    a = _adapter_returning(raw)

    r = a.fetch_meta("33378")
    assert r.data.episodes is None


def test_blocked_search_reported_as_failure_not_empty() -> None:
    """被风控时返回 HTML（HTTP 仍为 200）——必须报失败，不能返回空列表。

    这是本项目最在意的一类 bug：把"请求被拦"伪装成"搜索无结果"。
    """
    raw = (FIX / "bilibili_search_blocked.html").read_text(encoding="utf-8")
    a = _adapter_returning(raw, code=200)

    r = a.search("名侦探柯南")
    assert r.status == "failed"
    assert r.ok is False
    assert r.data is None, "失败时不得返回空列表冒充『无结果』"
    assert "拦截" in r.error or "JSON" in r.error


def test_http_error_reports_status_code() -> None:
    a = _adapter_returning("", code=412)
    r = a.search("任意")
    assert r.status == "failed"
    assert r.http_status == 412
    assert "412" in r.error


def test_network_exception_reported(monkeypatch) -> None:
    """网络异常由 _http_get 捕获并转成 failed。

    注意要在 requests.get 这层打桩，而不是替换 _http_get 本身——
    否则把"捕获异常"这段被测代码也一起替换掉了。
    """
    import requests

    from app.services.adapters import bilibili as mod

    def _boom(*args, **kwargs):
        raise requests.RequestException("connection reset")

    monkeypatch.setattr(mod.requests, "get", _boom)
    a = BilibiliAdapter()

    r = a.search("任意")
    assert r.status == "failed"
    assert "connection reset" in r.error


def test_reviews_degrade_without_cookie() -> None:
    """短评需登录 cookie；未配置时降级（可继续用评分），而非判死。"""
    a = BilibiliAdapter(cookie="")
    r = a.fetch_reviews("33378", limit=10)
    assert r.status == "degraded"
    assert r.ok is True          # 降级数据仍可用，调用方能继续
    assert r.error


def test_empty_query_returns_ok_empty() -> None:
    """空查询是"确实没查"，与"请求失败"必须区分。"""
    a = _adapter_returning("{}")
    r = a.search("   ")
    assert r.status == "ok"
    assert r.data == []


def test_cookie_read_from_config(monkeypatch) -> None:
    """未显式传 cookie 时从配置读——get_adapter() 是无参构造。"""
    from app.services.adapters import bilibili as mod

    monkeypatch.setattr(mod.config, "BILIBILI_COOKIE", "SESSDATA=abc; bili_jct=def")
    assert BilibiliAdapter().cookie == "SESSDATA=abc; bili_jct=def"


def test_explicit_cookie_overrides_config(monkeypatch) -> None:
    from app.services.adapters import bilibili as mod

    monkeypatch.setattr(mod.config, "BILIBILI_COOKIE", "SESSDATA=from_config")
    assert BilibiliAdapter(cookie="SESSDATA=explicit").cookie == "SESSDATA=explicit"


def test_reviews_use_cookie_when_present(monkeypatch) -> None:
    """配了 cookie 后短评通道应尝试真实抓取，而非直接降级。"""
    from app.services.adapters import bilibili as mod

    monkeypatch.setattr(mod.config, "BILIBILI_COOKIE", "SESSDATA=abc")
    a = BilibiliAdapter()
    assert a.cookie == "SESSDATA=abc"
    r = a.fetch_reviews("33378", limit=10)
    # v1 短评解析未接入，仍为 degraded，但原因不再是"未配置 cookie"
    assert "cookie" not in r.error
