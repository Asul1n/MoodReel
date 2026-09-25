"""适配器契约测试：SourceResult 必须能表达失败原因（规格 §11）。"""
from app.services.adapters.base import SourceResult, ok, failed, degraded


def test_ok_result_has_no_reason() -> None:
    r = ok("bangumi", data=[1, 2])
    assert r.status == "ok"
    assert r.ok is True
    assert r.error is None
    assert r.data == [1, 2]


def test_failed_result_must_carry_reason_and_http_status() -> None:
    """失败必须带原因 —— 禁止用空列表掩盖失败。"""
    r = failed("bangumi", reason="HTTP 429 限流", http_status=429)
    assert r.status == "failed"
    assert r.ok is False
    assert "429" in r.error
    assert r.http_status == 429


def test_failed_requires_non_empty_reason() -> None:
    import pytest
    with pytest.raises(ValueError):
        failed("bangumi", reason="")


def test_degraded_is_still_ok_for_callers() -> None:
    """降级数据可用，但调用方能看到降级标记。"""
    r = degraded("bilibili", reason="网页兜底命中", data=[1])
    assert r.ok is True
    assert r.status == "degraded"
    assert r.error == "网页兜底命中"


def test_empty_ok_is_distinct_from_failure() -> None:
    """『确实没有数据』与『请求失败』必须可区分。"""
    empty = ok("bangumi", data=[])
    fail = failed("bangumi", reason="连接超时", http_status=None)
    assert empty.ok is True and empty.status == "ok"
    assert fail.ok is False
