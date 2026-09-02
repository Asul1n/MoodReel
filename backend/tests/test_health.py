"""冒烟：健康检查 + 空库统计（骨架期即可通过，验证整体可跑）。"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["model_ready"] is False  # 成员B接入模型前
    assert "version" in body


def test_dataset_stats_empty() -> None:
    r = client.get("/dataset/stats")
    assert r.status_code == 200
    assert r.json()["total"] == 0
