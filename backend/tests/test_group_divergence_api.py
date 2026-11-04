"""分组分歧分析的服务层与接口测试。

数据用构造样本，确保断言可解析：
  - 高分组全正面、低分组全负面 → 效应量应为 1.0 且显著
  - 两组同分布 → 不应判显著
  - 样本不足门槛 → 返回 insufficient_data 而非硬算
  - 全库分析 → q 值不小于 p 值（FDR 只会放宽不会收紧）
"""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.services import group_divergence as G

client = TestClient(app)

# 用于越界参数测试：比模块上限大 1
MAX_OVER_LIMIT = G.MAX_N_PERM + 1


# —— 造数据 ——


def _add_movie(db, movie_id: str, title: str) -> None:
    db.add(models.Movie(movie_id=movie_id, title=title, source="douban"))
    db.commit()


def _add_reviews(db, movie_id: str, stars: int, label: str, count: int) -> None:
    for _ in range(count):
        db.add(models.Review(movie_id=movie_id, source="douban_live", lang="zh",
                             text="测试评论内容", stars=stars, pred_label=label))
    db.commit()


def _make_movie(db, movie_id: str, title: str, *,
                high_pos: int, high_neg: int, low_pos: int, low_neg: int) -> None:
    """按 4 组计数构造影片：高分组正/负、低分组正/负。"""
    _add_movie(db, movie_id, title)
    _add_reviews(db, movie_id, 5, "positive", high_pos)
    _add_reviews(db, movie_id, 5, "negative", high_neg)
    _add_reviews(db, movie_id, 1, "positive", low_pos)
    _add_reviews(db, movie_id, 1, "negative", low_neg)


# —— 纯函数 ——


def test_measure_polarity_maps_labels() -> None:
    assert G.measure_polarity("positive") == 1.0
    assert G.measure_polarity("negative") == -1.0
    assert G.measure_polarity(" POSITIVE ") == 1.0
    assert G.measure_polarity(None) is None
    assert G.measure_polarity("unknown") is None


def test_split_by_stars_drops_three_star_and_unlabeled() -> None:
    rows = [(5, "positive"), (4, "negative"), (3, "positive"),
            (2, "negative"), (1, None)]
    samples = G.split_by_stars(rows)

    assert samples.high == [1.0, -1.0]
    assert samples.low == [-1.0]
    assert samples.dropped_neutral == 1     # 3 星被丢弃
    assert samples.dropped_no_label == 1    # 1 星但无标签
    assert samples.total_used == 3


def test_split_by_stars_empty_input() -> None:
    samples = G.split_by_stars([])
    assert samples.high == [] and samples.low == []
    assert samples.total_used == 0


# —— 服务层 ——


def test_analyze_movie_reports_insufficient_data() -> None:
    db = SessionLocal()
    try:
        _make_movie(db, "m:small", "样本不足", high_pos=5, high_neg=0,
                    low_pos=0, low_neg=5)
        result = G.analyze_movie(db, "m:small", min_group=20, n_perm=200, n_boot=100)
        assert result["status"] == "insufficient_data"
        assert "20" in result["reason"]
        assert result["n_a"] == 5 and result["n_b"] == 5
    finally:
        db.close()


def test_analyze_movie_detects_clear_group_difference() -> None:
    db = SessionLocal()
    try:
        # 高分组 40 正 0 负，低分组 0 正 40 负 → 完全分离
        _make_movie(db, "m:clear", "完全分离", high_pos=40, high_neg=0,
                    low_pos=0, low_neg=40)
        result = G.analyze_movie(db, "m:clear", min_group=20,
                                 n_perm=500, n_boot=200, seed=42)

        assert result["status"] == "ok"
        assert result["effect_size"] == pytest.approx(1.0)
        assert result["direction"] == "a_gt_b"
        assert result["magnitude"] == "large"
        assert result["p_value"] < 0.01
        assert result["anomaly"] is False
        assert result["pos_rate_a"] == 1.0 and result["pos_rate_b"] == 0.0
        # 单次比较的 q 等于 p（m=1 的 BH），significant 照常给出
        assert result["q_value"] == pytest.approx(result["p_value"])
        assert result["significant"] is True
    finally:
        db.close()


def test_analyze_movie_flags_anomaly_when_direction_reversed() -> None:
    """高分组文本反而更负面属于数据质量异常，应被标记而非当作结论。"""
    db = SessionLocal()
    try:
        _make_movie(db, "m:odd", "方向异常", high_pos=0, high_neg=40,
                    low_pos=40, low_neg=0)
        result = G.analyze_movie(db, "m:odd", min_group=20,
                                 n_perm=500, n_boot=200)
        assert result["effect_size"] < 0
        assert result["anomaly"] is True
        assert result["direction"] == "a_lt_b"
    finally:
        db.close()


def test_analyze_all_applies_fdr_across_movies() -> None:
    db = SessionLocal()
    try:
        _make_movie(db, "m:a", "甲片", high_pos=40, high_neg=0, low_pos=0, low_neg=40)
        _make_movie(db, "m:b", "乙片", high_pos=35, high_neg=5, low_pos=5, low_neg=35)
        _make_movie(db, "m:c", "丙片", high_pos=3, high_neg=0, low_pos=0, low_neg=3)

        out = G.analyze_all(db, min_group=20, n_perm=500, n_boot=200, seed=1)

        assert out["summary"]["movies_eligible"] == 3
        assert out["summary"]["movies_tested"] == 2      # 丙片样本不足
        assert out["summary"]["movies_skipped"] == 1
        assert out["method"]["correction"] == "benjamini_hochberg"

        for row in out["results"]:
            assert row["q_value"] >= row["p_value"] - 1e-12   # FDR 只会放宽
            assert row["significant"] is True
            assert row["practically_significant"] is True
        assert out["summary"]["significant_but_negligible"] == 0
    finally:
        db.close()


def test_analyze_all_ceiling_effect_flag() -> None:
    """构造效应量接近上限的数据，应触发天花板提示。"""
    db = SessionLocal()
    try:
        _make_movie(db, "m:x", "强分离", high_pos=60, high_neg=0, low_pos=0, low_neg=60)
        out = G.analyze_all(db, min_group=20, n_perm=500, n_boot=200)
        assert out["summary"]["ceiling_effect"] is True
        assert out["summary"]["note"]
    finally:
        db.close()


def test_analyze_rejects_invalid_params() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            G.analyze_all(db, min_group=1)
        with pytest.raises(ValueError):
            G.analyze_all(db, alpha=1.5)
        with pytest.raises(ValueError):
            G.analyze_all(db, n_perm=MAX_OVER_LIMIT)
    finally:
        db.close()


# —— HTTP 接口 ——


def test_api_returns_404_for_unknown_movie() -> None:
    r = client.get("/insight/group-divergence", params={"movie_id": "nope"})
    assert r.status_code == 404


def test_api_rejects_unsupported_group_by() -> None:
    r = client.get("/insight/group-divergence", params={"group_by": "author"})
    assert r.status_code == 400
    assert "group_by" in r.json()["detail"]


def test_api_rejects_unsupported_measure() -> None:
    r = client.get("/insight/group-divergence", params={"measure": "aspect"})
    assert r.status_code == 400


def test_api_rejects_out_of_range_n_perm() -> None:
    r = client.get("/insight/group-divergence",
                   params={"n_perm": G.MAX_N_PERM + 100})
    assert r.status_code == 422


def test_api_single_movie_end_to_end() -> None:
    db = SessionLocal()
    try:
        _make_movie(db, "m:api", "接口测试片", high_pos=40, high_neg=0,
                    low_pos=0, low_neg=40)
    finally:
        db.close()

    r = client.get("/insight/group-divergence",
                   params={"movie_id": "m:api", "min_group": 20,
                           "n_perm": 500, "n_boot": 200, "seed": 9})
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "stars"
    assert body["method"]["seed"] == 9
    assert body["method"]["n_perm"] == 500

    row = body["results"][0]
    assert row["status"] == "ok"
    assert row["effect_size"] == pytest.approx(1.0)
    assert row["significant"] is True      # m=1 的 BH，q 等于 p
