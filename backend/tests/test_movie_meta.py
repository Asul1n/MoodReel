"""影片元数据（简介/海报/评分）解析与接口测试。"""
import json

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app import models
from app.crawler.douban import parse_movie_detail
from app.db import SessionLocal, engine
from app.main import app

client = TestClient(app)

SAMPLE = {
    "title": "肖申克的救赎", "year": "1994",
    "intro": "一场谋杀案使银行家安迪蒙冤入狱……",
    "pic": {"large": "https://img.doubanio.com/large.jpg", "normal": "https://img.doubanio.com/n.jpg"},
    "rating": {"value": 9.7, "count": 3333712},
    "genres": ["剧情", "犯罪"],
    "directors": [{"name": "弗兰克·德拉邦特"}],
}


def test_parse_movie_detail() -> None:
    meta = parse_movie_detail(json.dumps(SAMPLE))
    assert meta["title"] == "肖申克的救赎"
    assert meta["year"] == 1994
    assert meta["rating"] == 9.7
    assert meta["genres"] == "剧情 / 犯罪"
    assert meta["poster"].startswith("https://img.doubanio.com/large")
    assert meta["intro"]


def test_movies_table_has_meta_columns() -> None:
    cols = {c["name"] for c in inspect(engine).get_columns("movies")}
    assert {"intro", "poster", "rating", "genres"} <= cols


def test_movie_detail_endpoint() -> None:
    with SessionLocal() as db:
        db.add(models.Movie(movie_id="douban:1", title="测试片", source="douban",
                            intro="一段简介", poster="http://p/l.jpg",
                            rating=8.5, genres="剧情"))
        db.commit()
    r = client.get("/crawl/movie/douban:1")
    assert r.status_code == 200
    body = r.json()
    assert body["intro"] == "一段简介"
    assert body["poster"] == "http://p/l.jpg"
    assert body["rating"] == 8.5
    assert body["review_count"] == 0

    lst = client.get("/crawl/movies").json()
    m = next(x for x in lst if x["movie_id"] == "douban:1")
    assert m["intro"] == "一段简介"

    assert client.get("/crawl/movie/douban:999").status_code == 404
