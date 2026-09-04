"""DeepSeek 情感 adapter + 全流程补标 测试（mock 网络）。"""
import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient

from app import config, models
from app.crawler import runner
from app.db import SessionLocal
from app.main import app
from app.services import deepseek

client = TestClient(app)
CTX = "movie:douban:1292052"
_POS = ("好看", "精彩", "喜欢", "神", "天花板", "希望", "打动", "敬佩", "爱")
_NEG = ("无聊", "难看", "闷", "冗长", "不明白", "差", "看不懂")


class _Resp:
    def __init__(self, payload, status_code: int = 200):  # noqa: D107
        self._p = payload
        self.status_code = status_code

    def json(self):  # noqa: D102
        return self._p


def _fake_post(url, **kwargs):  # noqa: ANN003, ARG001
    """按关键词给每条评论定假标签，模拟 DeepSeek 返回。"""
    body = kwargs.get("json")
    user = body["messages"][1]["content"]
    items = re.findall(r"^\s*(\d+)\.\s*(.+)$", user, flags=re.M)
    results = []
    for _, text in items:
        if any(k in text for k in _POS):
            lab = "positive"
        elif any(k in text for k in _NEG):
            lab = "negative"
        else:
            lab = "neutral"
        results.append({"label": lab, "confidence": 0.9})
    return _Resp({"choices": [{"message": {"content": json.dumps({"results": results})}}]})


def _enable(monkeypatch, on: bool = True) -> None:
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "sk-test" if on else "")
    monkeypatch.setattr(config, "DEEPSEEK_ENABLED", on)


class _NoOnline:
    name = "douban"

    def search(self, query):  # noqa: D102
        raise NotImplementedError

    def fetch(self, movie, limit=60):  # noqa: D102
        raise NotImplementedError


def _seed_offline_douban() -> None:
    orig = runner.CRAWLERS["douban"]
    runner.CRAWLERS["douban"] = _NoOnline()
    job_id = uuid.uuid4().hex
    try:
        with SessionLocal() as db:
            db.add(models.CrawlJob(job_id=job_id, source="douban", query="肖申克的救赎",
                                   limit=10, status="pending"))
            db.commit()
        runner._run(job_id)
    finally:
        runner.CRAWLERS["douban"] = orig


def test_classify_labels(monkeypatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setattr(deepseek.requests, "post", _fake_post)
    labels = deepseek.classify(["这部电影很好看", "无聊透顶", "还行吧"])
    assert labels[0]["label"] == "positive"
    assert labels[1]["label"] == "negative"
    # 中性语义 -> 二类低置信度表达（prob≈0.5）
    assert labels[2]["prob"] == 0.5
    assert labels[2]["label"] in ("positive", "negative")


def test_disabled_raises(monkeypatch) -> None:
    _enable(monkeypatch, on=False)
    with pytest.raises(RuntimeError):
        deepseek.analyze_batch(["随便一句"])


def test_backfill_endpoint(monkeypatch) -> None:
    _seed_offline_douban()          # 8 条 zh 评论，pred_label 为空
    _enable(monkeypatch)
    monkeypatch.setattr(deepseek.requests, "post", _fake_post)

    r = client.post("/analyze/backfill", json={"context": CTX, "lang": "zh"})
    assert r.status_code == 200
    assert r.json()["updated"] == 8
    assert r.json()["model"] == "deepseek"

    with SessionLocal() as db:
        n = db.query(models.Review).filter(
            models.Review.movie_id == "douban:1292052",
            models.Review.model == "deepseek").count()
    assert n == 8

    # 再跑一次：没有待补标 -> 0
    r2 = client.post("/analyze/backfill", json={"context": CTX, "lang": "zh"})
    assert r2.json()["updated"] == 0
