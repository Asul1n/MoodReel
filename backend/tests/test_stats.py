"""统计检验函数测试（`app/services/stats.py`）。

关注三件事：
  1. 效应量在可解析的构造数据上取到理论值（完全分离/完全重叠/反向）
  2. 置换检验与 bootstrap 的行为符合预期，且 p 值不会退化为 0
  3. BH-FDR 与论文级复现的关键性质（单调性、经典算例、双条件判定）
"""
import numpy as np
import pytest

from app.services.stats import (GroupComparison, apply_fdr, bh_fdr,
                                bootstrap_ci, cliff_delta, cohens_h,
                                compare_groups, effect_magnitude,
                                permutation_test)

# —— Cliff's delta ——


def test_cliff_delta_full_separation_is_one() -> None:
    assert cliff_delta([5, 6, 7], [1, 2, 3]) == pytest.approx(1.0)


def test_cliff_delta_reversed_is_minus_one() -> None:
    assert cliff_delta([1, 2, 3], [5, 6, 7]) == pytest.approx(-1.0)


def test_cliff_delta_identical_samples_is_zero() -> None:
    assert cliff_delta([3, 3, 3], [3, 3, 3]) == pytest.approx(0.0)


def test_cliff_delta_is_antisymmetric() -> None:
    a, b = [1, 2, 2, 4], [2, 3, 5]
    assert cliff_delta(a, b) == pytest.approx(-cliff_delta(b, a))


def test_cliff_delta_handles_ties_without_bias() -> None:
    """大量并列时（情感只有 ±1，必然如此）不应被判成完全分离。"""
    delta = cliff_delta([1, 1, 1, -1], [1, -1, -1, -1])
    assert 0.0 < delta < 1.0


def test_cliff_delta_rejects_empty_group() -> None:
    with pytest.raises(ValueError):
        cliff_delta([], [1.0])


# —— 置换检验 ——


def test_permutation_detects_clear_difference() -> None:
    a = [1.0] * 60 + [-1.0] * 15
    b = [1.0] * 15 + [-1.0] * 60
    effect, p = permutation_test(a, b, n_perm=1000)
    assert effect > 0.5
    assert p < 0.01


def test_permutation_same_distribution_is_not_significant() -> None:
    """两组同分布（同比例正负各半）时不应判显著。"""
    a = [1.0] * 30 + [-1.0] * 30
    b = [1.0] * 30 + [-1.0] * 30
    _, p = permutation_test(a, b, n_perm=1000, seed=7)
    assert p > 0.05


def test_permutation_p_value_never_reaches_zero() -> None:
    """有限次重排无法证明 p 恰为 0；返回 0 会在审稿时被质疑。"""
    _, p = permutation_test([1.0] * 40, [-1.0] * 40, n_perm=500)
    assert p > 0.0
    assert p == pytest.approx(1 / 501)


def test_permutation_is_reproducible_with_seed() -> None:
    a = [1.0, -1.0, 1.0, 1.0, -1.0, 1.0]
    b = [1.0, 1.0, -1.0, -1.0, -1.0, -1.0]
    assert permutation_test(a, b, n_perm=500, seed=3) == \
        permutation_test(a, b, n_perm=500, seed=3)


def test_permutation_rejects_too_few_permutations() -> None:
    with pytest.raises(ValueError):
        permutation_test([1.0, 2.0], [3.0, 4.0], n_perm=50)


# —— bootstrap 置信区间 ——


def test_bootstrap_ci_brackets_observed_effect() -> None:
    a = [1.0] * 50 + [-1.0] * 20
    b = [1.0] * 25 + [-1.0] * 45
    observed = cliff_delta(a, b)
    low, high = bootstrap_ci(a, b, n_boot=400, seed=11)
    assert low <= observed <= high
    assert low < high


def test_bootstrap_ci_narrows_with_larger_sample() -> None:
    """样本量增大时区间应变窄，这是 bootstrap 一致性的基本要求。"""
    small_a = [1.0, -1.0] * 15
    small_b = [1.0] * 10 + [-1.0] * 20
    big_a = [1.0, -1.0] * 150
    big_b = [1.0] * 100 + [-1.0] * 200

    low_s, high_s = bootstrap_ci(small_a, small_b, n_boot=300, seed=5)
    low_b, high_b = bootstrap_ci(big_a, big_b, n_boot=300, seed=5)
    assert (high_b - low_b) < (high_s - low_s)


def test_bootstrap_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([1.0, 2.0], [3.0, 4.0], n_boot=100, alpha=1.5)


# —— BH-FDR ——


def test_bh_fdr_known_example_from_paper() -> None:
    """Benjamini-Hochberg 1995 的教科书算例：p=0.01..0.05, m=5 → q 全为 0.05。"""
    q = bh_fdr([0.01, 0.02, 0.03, 0.04, 0.05])
    assert np.allclose(q, [0.05] * 5)


def test_bh_fdr_is_monotone_in_p_value() -> None:
    """p 更小的假设，q 不应更大——单调性由累积最小保证。"""
    p_values = [0.9, 0.04, 0.001, 0.2, 0.03]
    q = bh_fdr(p_values)
    order = np.argsort(p_values)
    assert np.all(np.diff(q[order]) >= -1e-12)


def test_bh_fdr_preserves_input_order() -> None:
    p_values = [0.5, 0.001, 0.02]
    q = bh_fdr(p_values)
    assert q[1] < q[2] < q[0]


def test_bh_fdr_handles_empty_input() -> None:
    assert bh_fdr([]).size == 0


def test_bh_fdr_rejects_invalid_p_value() -> None:
    with pytest.raises(ValueError):
        bh_fdr([0.5, 1.2])


# —— 效应量等级与显著判定 ——


def test_effect_magnitude_thresholds() -> None:
    assert effect_magnitude(0.10) == "negligible"
    assert effect_magnitude(-0.20) == "small"
    assert effect_magnitude(0.40) == "medium"
    assert effect_magnitude(-0.60) == "large"


def test_apply_fdr_requires_both_significance_conditions() -> None:
    """q 达标但置信区间跨 0 时不得判显著——这是双条件判定的核心。"""
    passing = GroupComparison(n_a=10, n_b=10, effect_size=0.5,
                              ci_low=0.2, ci_high=0.8, p_value=0.001)
    ci_straddles_zero = GroupComparison(n_a=10, n_b=10, effect_size=0.2,
                                        ci_low=-0.1, ci_high=0.5, p_value=0.001)
    apply_fdr([passing, ci_straddles_zero], alpha=0.05)

    assert passing.significant is True
    assert ci_straddles_zero.significant is False
    assert ci_straddles_zero.q_value is not None


def test_apply_fdr_separates_statistical_and_practical_significance() -> None:
    """效应量可忽略但 p 很小：统计上显著成立，但不构成实质差异。

    这不是构造出来的极端情况——本地真实数据里就有一部片 δ=0.128、
    q=0.029，若只报"显著"会读成"发现了分歧"。
    """
    trivial = GroupComparison(n_a=200, n_b=200, effect_size=0.10,
                              ci_low=0.03, ci_high=0.18, p_value=0.001)
    meaningful = GroupComparison(n_a=200, n_b=200, effect_size=0.60,
                                 ci_low=0.50, ci_high=0.70, p_value=0.001)
    apply_fdr([trivial, meaningful], alpha=0.05)

    assert trivial.significant is True
    assert trivial.practically_significant is False
    assert meaningful.practically_significant is True


def test_apply_fdr_fails_when_q_exceeds_alpha() -> None:
    weak = GroupComparison(n_a=10, n_b=10, effect_size=0.3,
                           ci_low=0.05, ci_high=0.55, p_value=0.6)
    apply_fdr([weak], alpha=0.05)
    assert weak.significant is False


def test_apply_fdr_on_empty_list_is_noop() -> None:
    apply_fdr([])   # 不应抛异常


def test_compare_groups_reports_direction() -> None:
    a = [1.0] * 40
    b = [-1.0] * 40
    comp = compare_groups(a, b, n_perm=500, n_boot=200, seed=1)
    assert comp.direction == "a_gt_b"
    assert comp.effect_size == pytest.approx(1.0)
    assert comp.to_dict()["magnitude"] == "large"


def test_cohens_h_known_values() -> None:
    """同比例时 h 为 0；比例差异越大 h 越大。"""
    assert cohens_h(0.5, 0.5) == pytest.approx(0.0)
    assert cohens_h(0.9, 0.1) > cohens_h(0.7, 0.3)
