"""百度情感 API adapter 单测（mock 网络）。"""
import pytest

from app import config
from app.services import baidu


class _Resp:
    def __init__(self, payload):  # noqa: D107
        self._p = payload

    def json(self):  # noqa: D102
        return self._p


def _enable(monkeypatch, on: bool = True) -> None:
    monkeypatch.setattr(config, "BAIDU_API_KEY", "ak" if on else "")
    monkeypatch.setattr(config, "BAIDU_SECRET_KEY", "sk" if on else "")
    monkeypatch.setattr(config, "BAIDU_ENABLED", on)


def test_analyze_positive_and_negative(monkeypatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setattr(baidu, "_access_token", lambda: "tk")

    def fake_post(url, **kw):  # noqa: ARG001
        text = kw["json"]["text"]
        s = 2 if "好" in text else 0  # 0=负 2=正
        return _Resp({"items": [{"sentiment": s, "confidence": 0.91,
                                 "positive_prob": 0.91, "negative_prob": 0.09}]})

    monkeypatch.setattr(baidu.requests, "post", fake_post)

    pos = baidu.analyze("这部电影很好看")
    assert pos["label"] == "positive" and pos["prob"] == 0.91
    neg = baidu.analyze("这部电影太差了")
    assert neg["label"] == "negative"


def test_analyze_disabled_raises(monkeypatch) -> None:
    _enable(monkeypatch, on=False)
    with pytest.raises(RuntimeError):
        baidu.analyze("随便一句")


def test_analyze_batch_shape(monkeypatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setattr(baidu, "_access_token", lambda: "tk")

    def fake_post(url, **kw):  # noqa: ARG001
        return _Resp({"items": [{"sentiment": 1, "confidence": 0.5,
                                 "positive_prob": 0.5, "negative_prob": 0.5}]})

    monkeypatch.setattr(baidu.requests, "post", fake_post)
    results, elapsed_ms, throughput = baidu.analyze_batch(["一般般", "还行吧"])
    assert len(results) == 2
    assert results[0]["label"] == "neutral"
    assert results[0]["lang"] == "zh" and results[0]["model"] == "baidu"
    assert elapsed_ms > 0 and throughput > 0
