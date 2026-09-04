"""POST /dataset/ingest（手动新增/导入评论）测试。"""
from fastapi.testclient import TestClient

from app import config, models
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def test_ingest_store_only() -> None:
    r = client.post("/dataset/ingest", json={
        "texts": ["中文好评一条", "An english review here."], "analyze": False})
    assert r.status_code == 201
    body = r.json()
    assert body["count"] == 2 and len(body["ids"]) == 2

    with SessionLocal() as db:
        rows = (db.query(models.Review)
                .filter(models.Review.source == "manual")
                .order_by(models.Review.id.asc()).all())
    assert [x.lang for x in rows] == ["zh", "en"]
    assert all(x.pred_label is None for x in rows)


def test_ingest_analyze_zh_with_deepseek(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(config, "DEEPSEEK_ENABLED", True)
    from app.services import deepseek

    monkeypatch.setattr(deepseek, "classify",
                        lambda texts: [{"label": "positive", "prob": 0.95} for _ in texts])

    r = client.post("/dataset/ingest", json={"texts": ["这部电影太好了"], "analyze": True})
    rid = r.json()["ids"][0]
    with SessionLocal() as db:
        rev = db.get(models.Review, rid)
    assert rev.pred_label == "positive"
    assert rev.model == "deepseek"
