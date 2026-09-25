"""分歧引擎站点筛选与汇总测试（规格 §6.2 / §6.4）。"""
import pytest

from app.services.divergence import (CONSENSUS, FULL_CONTROVERSY,
                                     HIDDEN_CONTROVERSY, SCALE_BIAS,
                                     SourceStat, compute_divergence)


def _cfg() -> dict:
    return dict(thr_r=0.5, thr_s=0.2, m=500, min_rating_count=100,
                min_reviews=30, low_conf_weight=0.5)


def test_two_sources_ok() -> None:
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=90, neg=10, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.status == "ok"
    assert r.d_rating is not None and r.d_rating > 0
    assert r.d_sentiment is not None
    assert r.quadrant in (CONSENSUS, HIDDEN_CONTROVERSY, SCALE_BIAS, FULL_CONTROVERSY)


def test_single_source_is_insufficient() -> None:
    """只有一个可用站点时不出结论（规格 §6.4）。"""
    stats = [SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                        pos=80, neg=20, review_count=100)]
    r = compute_divergence(stats, **_cfg())
    assert r.status == "insufficient_data"
    assert r.d_rating is None
    assert "站点" in r.reason


def test_no_rating_sites_excluded_from_d_rating() -> None:
    """两个指标的参与站点集合可以不同。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=20, neg=80, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert set(r.sources_rating) == {"bangumi", "bilibili"}
    assert set(r.sources_sentiment) == {"bangumi", "bilibili"}


def test_few_reviews_excluded_from_sentiment() -> None:
    """评论数不足的站点不参与情感分歧（规格 §6.4）。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=20, neg=80, review_count=5),      # 评论太少
    ]
    r = compute_divergence(stats, **_cfg())
    assert "bilibili" not in r.sources_sentiment      # 该站被排除
    assert r.d_sentiment is None                      # 情感只剩一个站 → 算不出
    assert r.sources_sentiment == []                  # 无站点进入计算 → 列表为空
    assert r.d_rating is not None                     # 评分仍可算
    assert r.status == "ok"                           # 有一个指标算得出就算 ok


def test_low_rating_count_gets_reduced_weight() -> None:
    """评分人数不足的站点权重被降低（规格 §6.4）。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.0, rating_count=50000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=4.0, rating_count=10,
                   pos=80, neg=20, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    weights = {x["source"]: x["weight"] for x in r.ratings}
    assert weights["bilibili"] == pytest.approx(0.5)
    assert weights["bangumi"] == pytest.approx(1.0)


def test_hidden_controversy_detected() -> None:
    """评分接近但情感两极 → 分数掩盖了争议（本系统最有价值的产出）。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.5, rating_count=20000,
                   pos=95, neg=5, review_count=100),
        SourceStat(source="bilibili", rating_norm=8.5, rating_count=20000,
                   pos=5, neg=95, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.quadrant == HIDDEN_CONTROVERSY


def test_scale_bias_detected() -> None:
    """评分差距大但情感一致 → 打分习惯差异，而非真实口碑分歧。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=4.0, rating_count=20000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=20000,
                   pos=80, neg=20, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.quadrant == SCALE_BIAS


def test_rating_only_site_can_still_produce_d_rating() -> None:
    """某站只有评分没有评论时，仍应参与评分分歧。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.0, rating_count=20000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.0, rating_count=20000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="anilist", rating_norm=4.0, rating_count=20000,
                   pos=None, neg=None, review_count=0),   # 无评论
    ]
    r = compute_divergence(stats, **_cfg())
    assert "anilist" in r.sources_rating
    assert "anilist" not in r.sources_sentiment
    assert r.d_rating is not None
