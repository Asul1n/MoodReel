"""豆瓣爬虫解析器单测（不访问网络）。"""
import pathlib

import pytest

from app.crawler.douban import looks_blocked, parse_comments, parse_subjects

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "douban_comments_sample.html"
REAL = FIXTURES / "douban_comments.html"


def test_parse_comments_sample() -> None:
    items = parse_comments(SAMPLE.read_text(encoding="utf-8"))
    assert len(items) == 3
    assert items[0].stars == 4
    assert items[1].stars == 1
    assert items[2].stars is None
    assert all(it.text for it in items)


def test_parse_subjects_json() -> None:
    payload = '[{"id":"1292052","title":"肖申克的救赎","year":"1994","subtype":"movie"},' \
              '{"id":"1","title":"某本书","subtype":"book"}]'
    refs = parse_subjects(payload)
    assert len(refs) == 1
    assert refs[0].movie_id == "douban:1292052"
    assert refs[0].year == 1994
    assert refs[0].source == "douban"


def test_looks_blocked() -> None:
    assert looks_blocked("")                          # 空
    assert looks_blocked("检测到有异常请求，请稍后再试")   # 反爬验证页
    assert not looks_blocked("<html><body>" + "a" * 2000 + "</body></html>")


@pytest.mark.skipif(not REAL.exists(), reason="真实豆瓣页面未提供：tests/fixtures/douban_comments.html")
def test_parse_real_douban_page() -> None:
    """拿到真实页面后此用例自动启用（豆瓣改版时用它校准选择器）。"""
    items = parse_comments(REAL.read_text(encoding="utf-8"))
    assert len(items) >= 1
