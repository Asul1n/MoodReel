"""分歧接口测试（规格 §7 / §6.5）。"""
from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.services.divergence import HIDDEN_CONTROVERSY, SCALE_BIAS

client = TestClient(app)


def _seed(anime_id: str = "bangumi:253", *, r1: float = 8.5, r2: float = 8.5,
          pos1: int = 95, neg1: int = 5, pos2: int = 5, neg2: int = 95) -> None:
    """两站数据：默认构造"评分接近但情感两极"。

    source_id 从 anime_id 派生，否则多部番共用同一 source_id 会撞
    (source, source_id) 唯一约束。
    """
    suffix = anime_id.split(":")[-1]
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id=anime_id, title_cn="进击的巨人", year=2013))
        db.add(models.AnimeSource(anime_id=anime_id, source="bangumi",
                                  source_id=suffix, rating_raw=r1, rating_scale=10,
                                  rating_count=20000, review_count=100,
                                  sentiment_pos=pos1, sentiment_neg=neg1,
                                  sentiment_mean=0.9))
        db.add(models.AnimeSource(anime_id=anime_id, source="bilibili",
                                  source_id=f"{suffix}b", rating_raw=r2,
                                  rating_scale=10, rating_count=20000,
                                  review_count=100, sentiment_pos=pos2,
                                  sentiment_neg=neg2, sentiment_mean=-0.9))
        db.commit()
    finally:
        db.close()


def test_anime_sources_endpoint() -> None:
    _seed()
    r = client.get("/anime/bangumi:253/sources")
    assert r.status_code == 200
    body = r.json()
    assert body["anime"]["title_cn"] == "进击的巨人"
    assert {s["source"] for s in body["sources"]} == {"bangumi", "bilibili"}


def test_anime_sources_404() -> None:
    assert client.get("/anime/bangumi:999999/sources").status_code == 404


def test_divergence_hidden_controversy() -> None:
    """评分接近 + 情感两极 → 分数掩盖了争议。"""
    _seed(r1=8.5, r2=8.5, pos1=95, neg1=5, pos2=5, neg2=95)
    r = client.get("/divergence/bangumi:253")
    assert r.status_code == 200
    body = r.json()
    assert body["quadrant"] == HIDDEN_CONTROVERSY
    assert body["sources_used"]["rating"]
    assert body["sources_used"]["sentiment"]


def test_divergence_scale_bias() -> None:
    """评分悬殊 + 情感一致 → 打分习惯差异，而非真实口碑分歧。"""
    _seed(r1=4.0, r2=9.5, pos1=80, neg1=20, pos2=80, neg2=20)
    assert client.get("/divergence/bangumi:253").json()["quadrant"] == SCALE_BIAS


def test_divergence_404_for_unknown_anime() -> None:
    assert client.get("/divergence/bangumi:999999").status_code == 404


def test_divergence_insufficient_data_when_one_source() -> None:
    """只有一个站时不出结论，并说明原因。"""
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:1", title_cn="独站番"))
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi",
                                  source_id="1", rating_raw=8.0, rating_scale=10,
                                  rating_count=5000, review_count=50,
                                  sentiment_pos=10, sentiment_neg=5))
        db.commit()
    finally:
        db.close()

    body = client.get("/divergence/bangumi:1").json()
    assert body["status"] == "insufficient_data"
    assert body["reason"]
    assert body["quadrant"] is None


def test_divergence_cache_and_refresh() -> None:
    """命中缓存标记 cached=true；refresh=true 强制重算。"""
    _seed()
    first = client.get("/divergence/bangumi:253").json()
    assert first["cached"] is False
    second = client.get("/divergence/bangumi:253").json()
    assert second["cached"] is True
    refreshed = client.get("/divergence/bangumi:253",
                           params={"refresh": "true"}).json()
    assert refreshed["cached"] is False


def test_ranking_filters_by_quadrant() -> None:
    _seed(anime_id="bangumi:253", r1=8.5, r2=8.5, pos1=95, neg1=5, pos2=5, neg2=95)
    _seed(anime_id="bangumi:300", r1=4.0, r2=9.5, pos1=80, neg1=20, pos2=80, neg2=20)

    r = client.get("/ranking/divergence", params={"quadrant": HIDDEN_CONTROVERSY})
    assert r.status_code == 200
    assert [i["anime_id"] for i in r.json()["items"]] == ["bangumi:253"]


def test_ranking_returns_all_quadrants_when_unfiltered() -> None:
    _seed(anime_id="bangumi:253", r1=8.5, r2=8.5, pos1=95, neg1=5, pos2=5, neg2=95)
    _seed(anime_id="bangumi:300", r1=4.0, r2=9.5, pos1=80, neg1=20, pos2=80, neg2=20)
    items = client.get("/ranking/divergence").json()["items"]
    assert {i["anime_id"] for i in items} == {"bangumi:253", "bangumi:300"}


# --------------------------------------------------------------------------- #
# 分站褒贬词归因（规格 §6.5）
# --------------------------------------------------------------------------- #

def _seed_with_reviews() -> None:
    """两站各 20 条正面评论。走 pred_label（情感分析后的真实路径）。"""
    _seed(anime_id="bangumi:253", r1=8.5, r2=8.5, pos1=50, neg1=10, pos2=50, neg2=10)
    db = SessionLocal()
    try:
        for _ in range(20):
            db.add(models.Review(anime_id="bangumi:253", source="bangumi_live",
                                 lang="zh", text="作画精良 分镜出色",
                                 pred_label="positive"))
        for _ in range(20):
            db.add(models.Review(anime_id="bangumi:253", source="bilibili_live",
                                 lang="zh", text="打斗精彩 燃到爆",
                                 pred_label="positive"))
        db.commit()
    finally:
        db.close()


def test_divergence_includes_attribution() -> None:
    """分歧结果应带分站独有褒贬词，用于解释"为什么分歧"。"""
    _seed_with_reviews()
    body = client.get("/divergence/bangumi:253",
                      params={"refresh": "true"}).json()
    per_source = body["attribution"]["per_source"]
    assert "bangumi" in per_source
    assert "bilibili" in per_source
    bgm_words = [x["word"] for x in per_source["bangumi"]["top_pos"]]
    bili_words = [x["word"] for x in per_source["bilibili"]["top_pos"]]
    assert {"作画", "分镜", "精良"} & set(bgm_words)
    assert {"打斗", "燃到"} & set(bili_words)


def test_attribution_empty_without_reviews() -> None:
    """没有评论时归因应为空，而不是报错。"""
    _seed()
    body = client.get("/divergence/bangumi:253",
                      params={"refresh": "true"}).json()
    assert body["attribution"]["per_source"] == {}
