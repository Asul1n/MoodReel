"""TextCNN 服务测试（需 torch 且 backend/models/model.pt 存在，否则自动跳过）。"""
import pathlib

import pytest

MODEL = pathlib.Path(__file__).resolve().parents[1] / "models" / "model.pt"

torch = pytest.importorskip("torch")  # 未安装 torch 则整文件跳过
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="model.pt 未放入 backend/models/")


def test_load_and_analyze_batch() -> None:
    from app.services import textcnn

    textcnn.load()
    assert textcnn.is_ready(), textcnn.status()

    results, elapsed_ms, throughput = textcnn.analyze_batch([
        "This movie is an absolute masterpiece.",
        "This movie is terrible and I want my money back.",
        "The cinematography and acting were brilliant.",
    ])
    assert len(results) == 3
    assert results[0]["label"] == "positive"
    assert results[1]["label"] == "negative"
    assert results[2]["label"] == "positive"
    for r in results:
        assert 0.0 < r["prob"] <= 1.0
        assert r["model"] == "textcnn"
        assert r["lang"] == "en"
    assert elapsed_ms > 0
    assert throughput > 0
