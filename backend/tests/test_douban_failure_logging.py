"""回归测试：豆瓣爬虫不得把失败伪装成"搜索无结果"（规格 §11 第 2 条）。

背景：线上曾出现"搜索无结果 query=楚门的世界"，但同片源现测搜索正常。
真因是 _get() 吞掉了 HTTP 403，调用方把 None 当成"确实无结果"，
于是排障时完全看不出是被限流。本测试锁住"失败必须留下状态码"。
"""
import logging
import threading

import pytest

from app.crawler import douban
from app.crawler.douban import DoubanCrawler


class _Resp:
    def __init__(self, code: int) -> None:
        self.status_code = code
        self.text = ""


class _Session:
    def __init__(self, code: int) -> None:
        self.code = code

    def get(self, url, headers=None, **kw):
        return _Resp(self.code)


def _crawler(code: int) -> DoubanCrawler:
    """绕过 __init__ 构造实例——它会 _prime() 真连豆瓣，不适合单测。"""
    c = DoubanCrawler.__new__(DoubanCrawler)
    c._lock = threading.Lock()
    c._spin = 0
    c._idents = [{"session": _Session(code), "cookie": None}]
    c._proxies = []
    return c


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """退避 sleep 与断言无关，且会让测试慢 ~15 秒。"""
    monkeypatch.setattr(douban.time, "sleep", lambda *_: None)


@pytest.fixture(autouse=True)
def _capture_moodreel(caplog, monkeypatch):
    """让 caplog 能收到 moodreel logger 的记录。

    app/logging_config 为避免与 uvicorn 重复输出，把该 logger 设为
    propagate=False；caplog 挂在 root 上就收不到。单独跑本文件时
    logging_config 未被导入，所以只有全量跑才暴露此问题。
    """
    logger = logging.getLogger("moodreel")
    monkeypatch.setattr(logger, "propagate", True)
    caplog.set_level(logging.WARNING, logger="moodreel")


def _messages(caplog) -> str:
    return " | ".join(r.getMessage() for r in caplog.records)


def test_get_logs_http_status_on_ratelimit(caplog) -> None:
    src = _crawler(403)
    out = src._get("https://example.invalid", {})
    assert out is None
    assert "403" in _messages(caplog), \
        "失败必须记录状态码，否则无法区分『被拦』与『无结果』"


def test_get_logs_non_200_status(caplog) -> None:
    src = _crawler(404)
    out = src._get("https://example.invalid", {})
    assert out is None
    assert "404" in _messages(caplog)


def test_get_logs_final_failure_after_retries(caplog) -> None:
    """重试耗尽后要有明确的最终失败日志（ERROR 级）。"""
    src = _crawler(429)
    out = src._get("https://example.invalid", {})
    assert out is None
    assert any(r.levelno >= logging.ERROR for r in caplog.records), \
        "重试耗尽必须报 ERROR，便于与『确实无数据』区分"
    assert "429" in _messages(caplog)


def test_get_logs_exception(caplog) -> None:
    """网络异常也要记录，不能静默返回 None。"""
    import requests

    class _Boom:
        def get(self, url, headers=None, **kw):
            raise requests.RequestException("connection reset")

    src = _crawler(200)
    src._idents = [{"session": _Boom(), "cookie": None}]
    out = src._get("https://example.invalid", {})
    assert out is None
    assert "connection reset" in _messages(caplog)
