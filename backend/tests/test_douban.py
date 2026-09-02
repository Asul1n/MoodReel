"""豆瓣爬虫解析器单测（不访问网络）。"""
import json
import pathlib

import pytest

from app.crawler.douban import parse_interests, parse_subjects

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REAL_JSON = FIXTURES / "douban_interests.json"


def _payload(items: list[dict]) -> str:
    return json.dumps({"start": 0, "count": len(items), "total": 1000, "interests": items})


def test_parse_interests() -> None:
    payload = _payload([
        {"comment": "恐惧让你沦为囚犯，希望让你重获自由。", "rating": {"value": 5}},
        {"comment": "节奏略慢，但值得。", "rating": {"value": 3}},
        {"comment": "这条没打星", "rating": None},
        {"comment": "   ", "rating": {"value": 1}},      # 空正文应被跳过
    ])
    items = parse_interests(payload)
    assert len(items) == 3
    assert items[0].stars == 5
    assert items[1].stars == 3
    assert items[2].stars is None


def test_parse_interests_invalid() -> None:
    assert parse_interests("") == []
    assert parse_interests("<html>验证页</html>") == []
    assert parse_interests('{"code": 999}') == []


def test_parse_subjects_json() -> None:
    payload = ('[{"id":"1292052","title":"肖申克的救赎","year":"1994","subtype":"movie"},'
               '{"id":"1","title":"某书","subtype":"book"}]')
    refs = parse_subjects(payload)
    assert len(refs) == 1
    assert refs[0].movie_id == "douban:1292052"
    assert refs[0].year == 1994
    assert refs[0].source == "douban"


@pytest.mark.skipif(not REAL_JSON.exists(), reason="真实 JSON 未提供：tests/fixtures/douban_interests.json")
def test_parse_real_interests() -> None:
    items = parse_interests(REAL_JSON.read_text(encoding="utf-8"))
    assert len(items) >= 1
    assert all(it.text for it in items)
