"""词云图片接口测试。"""
from fastapi.testclient import TestClient

from app.main import app
from app.services import wordcloud_img

client = TestClient(app)


def test_build_returns_png() -> None:
    png = wordcloud_img.build([{"word": "希望", "weight": 5},
                               {"word": "自由", "weight": 3},
                               {"word": "安迪", "weight": 2}])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_wordcloud_endpoint_returns_image() -> None:
    r = client.get("/viz/wordcloud", params={"context": "whole", "top_n": 20})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"
