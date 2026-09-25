"""分歧引擎纯函数测试（规格 §6.1–§6.3）。"""
import statistics

import pytest

from app.services.divergence import (bayesian_shrink, classify_quadrant,
                                     normalize_rating, polarity, weighted_std)


def test_normalize_10_scale_is_identity() -> None:
    assert normalize_rating(8.6, 10) == pytest.approx(8.6)


def test_normalize_100_scale_to_10() -> None:
    """AniList 是 100 分制，必须归一到 10 分制才能与其他站比较。"""
    assert normalize_rating(86.0, 100) == pytest.approx(8.6)


def test_normalize_rejects_bad_scale() -> None:
    with pytest.raises(ValueError):
        normalize_rating(5.0, 0)


def test_bayesian_shrink_pulls_small_sample_toward_prior() -> None:
    """小样本被拉向先验 C；大样本几乎不动。"""
    small = bayesian_shrink(9.5, v=10, c=7.0, m=500)
    large = bayesian_shrink(9.5, v=100000, c=7.0, m=500)
    assert small < large
    assert small == pytest.approx((10 * 9.5 + 500 * 7.0) / 510)
    assert large == pytest.approx(9.5, abs=0.02)


def test_bayesian_shrink_zero_count_returns_prior() -> None:
    assert bayesian_shrink(9.9, v=0, c=7.0, m=500) == pytest.approx(7.0)


def test_bayesian_shrink_rejects_negative() -> None:
    with pytest.raises(ValueError):
        bayesian_shrink(8.0, v=-1, c=7.0, m=500)


def test_weighted_std_matches_plain_std_when_weights_equal() -> None:
    vals = [8.0, 9.0, 10.0]
    assert weighted_std(vals, [1, 1, 1]) == pytest.approx(statistics.pstdev(vals))


def test_weighted_std_downweights_low_confidence_site() -> None:
    """低权重站点对分歧的贡献更小 —— 权重必须真的起作用。"""
    assert weighted_std([5.0, 9.0], [0.5, 1.0]) < weighted_std([5.0, 9.0], [1.0, 1.0])


def test_weighted_std_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError):
        weighted_std([8.0], [0.0])


def test_weighted_std_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        weighted_std([8.0, 9.0], [1.0])


def test_polarity_range() -> None:
    assert polarity(10, 0) == pytest.approx(1.0)
    assert polarity(0, 10) == pytest.approx(-1.0)
    assert polarity(5, 5) == pytest.approx(0.0)


def test_polarity_no_reviews_is_zero() -> None:
    """无评论时返回 0，而不是除零崩溃。"""
    assert polarity(0, 0) == pytest.approx(0.0)


def test_classify_quadrant_all_four() -> None:
    assert classify_quadrant(0.1, 0.05, 0.5, 0.2) == "consensus"
    assert classify_quadrant(0.1, 0.30, 0.5, 0.2) == "hidden_controversy"
    assert classify_quadrant(0.9, 0.05, 0.5, 0.2) == "scale_bias"
    assert classify_quadrant(0.9, 0.30, 0.5, 0.2) == "full_controversy"


def test_classify_quadrant_boundary_is_inclusive_low() -> None:
    """阈值处取低位（< 判低）。"""
    assert classify_quadrant(0.5, 0.2, 0.5, 0.2) == "full_controversy"
