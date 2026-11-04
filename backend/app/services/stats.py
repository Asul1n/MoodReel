"""分组差异的非参数统计检验（零新依赖，仅用 numpy）。

设计取舍见 docs/5_学术升级方案 中的方法说明，此处只记三条关键理由：

1. **效应量与检验统计量同源**。Cliff's delta 由秩和 U 导出，与
   Mann-Whitney U 同构，因此"效应量多大"和"p 值多小"不存在口径冲突。
   常见错误是效应量用 Cohen's d、显著性用 t 检验，而影评情感取值离散
   （只有 ±1）、分布双峰，正态前提根本不成立。

2. **显著性用置换检验而非正态近似**。在零假设（两组同分布）下重排标签
   构造经验零分布，不依赖任何分布假设，样本量小（几十条）时也稳健。

3. **多重比较必须校正**。一次分析会同时检验多部影片，若按 α=0.05 逐个判定，
   检验 14 次时至少出现 1 个假阳性的概率是 1−0.95¹⁴ ≈ 51%。用
   Benjamini-Hochberg 控制 FDR，并把校正后的 q 值一并输出。

所有随机过程都接受 seed，保证实验可复现——论文附录需要记录随机种子。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# 置换检验的默认次数。2000 次时 p 值的分辨率约 5e-4，足够判定 α=0.05。
DEFAULT_N_PERM = 2000
# bootstrap 默认次数。1000 次足以稳定估计 95% 区间的端点。
DEFAULT_N_BOOT = 1000
# 效应量"可忽略"的下界（Romano 2006）。低于此值时，即便 p 很小也只说明
# 差异真实存在，不说明差异值得关注——大样本下微小差异极易达到显著。
NEGLIGIBLE_THRESHOLD = 0.147


def _midranks(values: np.ndarray) -> np.ndarray:
    """计算平均秩（ties 取同秩均值），秩从 1 开始。

    用平均秩而非顺序秩，是为了让秩和 U 在存在并列值时仍然无偏——
    影评情感只有 +1/−1 两个取值，并列极多，这一步不能省。
    """
    n = values.size
    order = np.argsort(values, kind="mergesort")      # 稳定排序，保证同值顺序确定
    ranks = np.empty(n, dtype=float)
    sorted_vals = values[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0   # 并列段共享平均秩
        i = j + 1
    return ranks


def _delta_from_rank_sum(rank_sum_a: float, n_a: int, n_b: int) -> float:
    """秩和 → Cliff's delta。U = R_a − n_a(n_a+1)/2，delta = 2U/(n_a·n_b) − 1。"""
    u = rank_sum_a - n_a * (n_a + 1) / 2.0
    return float(2.0 * u / (n_a * n_b) - 1.0)


def cliff_delta(a, b) -> float:
    """两组样本的 Cliff's delta 效应量，取值 ∈ [−1, 1]。

    含义是 P(a > b) − P(a < b)，即"随机取一个 a 与一个 b，a 更大的概率"
    减去"b 更大的概率"。并列（相等）对分子不贡献。

    解释阈值沿用 Romano 等人的惯例：
        |δ| < 0.147 可忽略 · < 0.33 小 · < 0.474 中 · ≥ 0.474 大
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.size == 0 or arr_b.size == 0:
        raise ValueError("两组样本都不能为空")
    n_a, n_b = arr_a.size, arr_b.size
    ranks = _midranks(np.concatenate([arr_a, arr_b]))
    return _delta_from_rank_sum(float(ranks[:n_a].sum()), n_a, n_b)


def permutation_test(a, b, *, n_perm: int = DEFAULT_N_PERM,
                     seed: int = 42) -> tuple[float, float]:
    """双侧置换检验，返回 (观测效应量, p 值)。

    做法：在零假设下两组来自同一总体，因此打乱组标签不改变联合分布。
    重排 n_perm 次得到 delta 的经验零分布，p 值是零分布中
    |delta| 不弱于观测值的比例。

    p 值用 (k+1)/(n_perm+1) 而不是 k/n_perm，避免出现 p=0——
    有限次重排无法证明概率恰为零，报 0 在审稿时会被质疑。

    向量化实现：秩在置换中保持不变，只需每次重新划分秩和，因此
    单次置换是 O(n_a) 而非重新排序的 O(n log n)。
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.size == 0 or arr_b.size == 0:
        raise ValueError("两组样本都不能为空")
    if n_perm < 100:
        raise ValueError("n_perm 至少为 100，否则 p 值分辨率不足")

    n_a, n_b = arr_a.size, arr_b.size
    pooled = np.concatenate([arr_a, arr_b])
    n = pooled.size
    ranks = _midranks(pooled)
    observed = _delta_from_rank_sum(float(ranks[:n_a].sum()), n_a, n_b)

    rng = np.random.default_rng(seed)
    # 每行是一个随机排列，取前 n_a 个位置作为"伪 A 组"
    perm = rng.permuted(np.tile(np.arange(n), (n_perm, 1)), axis=1)
    rank_sums = ranks[perm[:, :n_a]].sum(axis=1)
    null = 2.0 * (rank_sums - n_a * (n_a + 1) / 2.0) / (n_a * n_b) - 1.0

    exceed = int(np.sum(np.abs(null) >= abs(observed) - 1e-12))
    p_value = (exceed + 1) / (n_perm + 1)
    return observed, float(p_value)


def bootstrap_ci(a, b, *, n_boot: int = DEFAULT_N_BOOT, alpha: float = 0.05,
                 seed: int = 42) -> tuple[float, float]:
    """效应量的百分位 bootstrap 置信区间，返回 (下限, 上限)。

    两组各自有放回重采样后再算 delta。与置换检验的分工：
    置换检验回答"差异是否真实存在"，bootstrap 回答"效应量可能落在哪"。
    论文里两者都要报——只有 p 值没有区间，审稿人无法判断效应量精度。
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.size == 0 or arr_b.size == 0:
        raise ValueError("两组样本都不能为空")
    if n_boot < 100:
        raise ValueError("n_boot 至少为 100，否则区间端点不稳定")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha 必须落在 (0, 1) 区间")

    rng = np.random.default_rng(seed)
    n_a, n_b = arr_a.size, arr_b.size
    deltas = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample_a = rng.choice(arr_a, size=n_a, replace=True)
        sample_b = rng.choice(arr_b, size=n_b, replace=True)
        deltas[i] = cliff_delta(sample_a, sample_b)

    low = float(np.percentile(deltas, 100.0 * alpha / 2.0))
    high = float(np.percentile(deltas, 100.0 * (1.0 - alpha / 2.0)))
    return low, high


def bh_fdr(p_values, *, alpha: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg 校正，返回每个假设的 q 值（顺序与输入一致）。

    q_i = min_{j ≥ i} ( p_(j) · m / j )，其中 p_(j) 是升序排列的第 j 个 p 值。
    单调化（从后往前取累积最小）是必须的，否则 q 值会出现非单调，
    导致"p 更小反而 q 更大"的矛盾。

    判定规则：q < alpha 即在该 FDR 水平下显著。
    """
    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        return np.array([], dtype=float)
    if np.any((p < 0.0) | (p > 1.0)):
        raise ValueError("p 值必须落在 [0, 1] 区间")

    m = p.size
    order = np.argsort(p, kind="mergesort")
    ranked = p[order]
    raw_q = ranked * m / np.arange(1, m + 1)
    monotone = np.minimum.accumulate(raw_q[::-1])[::-1]   # 从大到小取累积最小
    q_sorted = np.clip(monotone, 0.0, 1.0)

    out = np.empty(m, dtype=float)
    out[order] = q_sorted
    return out


def effect_magnitude(delta: float) -> str:
    """把 Cliff's delta 映射成可读的效应量等级（Romano 2006 的阈値）。"""
    d = abs(float(delta))
    if d < 0.147:
        return "negligible"
    if d < 0.330:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


@dataclass
class GroupComparison:
    """单次两组比较的完整结果，字段与论文表格一一对应。"""

    n_a: int
    n_b: int
    effect_size: float
    ci_low: float
    ci_high: float
    p_value: float
    q_value: float | None = None
    significant: bool = False
    practically_significant: bool = False   # 显著 且 效应量非"可忽略"
    direction: str = "tie"          # a_gt_b | a_lt_b | tie
    magnitude: str = "negligible"

    def to_dict(self) -> dict:
        return {
            "n_a": self.n_a,
            "n_b": self.n_b,
            "effect_size": round(self.effect_size, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "p_value": round(self.p_value, 6),
            "q_value": round(self.q_value, 6) if self.q_value is not None else None,
            "significant": self.significant,
            "practically_significant": self.practically_significant,
            "direction": self.direction,
            "magnitude": self.magnitude,
        }


def compare_groups(a, b, *, n_perm: int = DEFAULT_N_PERM,
                   n_boot: int = DEFAULT_N_BOOT, alpha: float = 0.05,
                   seed: int = 42) -> GroupComparison:
    """一次完整的两组比较：效应量 + 置信区间 + 置换 p 值。

    注意 q 值与 significant 此处不判定——FDR 是跨多个假设做的，
    必须由上层在收集完全部 p 值后统一回填（见 apply_fdr）。
    """
    effect, p_value = permutation_test(a, b, n_perm=n_perm, seed=seed)
    ci_low, ci_high = bootstrap_ci(a, b, n_boot=n_boot, alpha=alpha, seed=seed)

    if effect > 0:
        direction = "a_gt_b"
    elif effect < 0:
        direction = "a_lt_b"
    else:
        direction = "tie"

    return GroupComparison(
        n_a=len(a), n_b=len(b),
        effect_size=effect, ci_low=ci_low, ci_high=ci_high,
        p_value=p_value, direction=direction,
        magnitude=effect_magnitude(effect),
    )


def apply_fdr(comparisons: list[GroupComparison], *, alpha: float = 0.05) -> None:
    """跨多个比较批量做 BH 校正，并就地回填 q_value 与 significant。

    显著判定要求同时满足两条：
      - q_value < alpha（控制 FDR 后仍显著）
      - 置信区间不跨 0（效应量方向确定）

    双条件比单看 p 值严格。只报 p 值的常见问题是：样本量一大，
    极小的、实务上无意义的差异也会"显著"，区间能挡住这种情况。

    此外单独标记 `practically_significant`：显著且 |δ| ≥ 0.147 才算有实质
    差异。两个字段并存而不是合并成一个，是因为"差异真实存在"与"差异值得
    关注"是两个问题——本地真实数据里就有 δ=0.128、q=0.029 的例子，合并后
    会丢掉这个区分。
    """
    if not comparisons:
        return
    q_values = bh_fdr([c.p_value for c in comparisons], alpha=alpha)
    for comp, q in zip(comparisons, q_values):
        comp.q_value = float(q)
        ci_excludes_zero = (comp.ci_low > 0.0) or (comp.ci_high < 0.0)
        comp.significant = bool(comp.q_value < alpha and ci_excludes_zero)
        comp.practically_significant = bool(
            comp.significant and abs(comp.effect_size) >= NEGLIGIBLE_THRESHOLD)


def cohens_h(p1: float, p2: float) -> float:
    """两比例差异的效应量（Cohen's h），用于报告情感极性占比差异。

    极性均值之差会被取值域 ±1 压缩，直观上偏小；h 先把比例做反正弦变换，
    对小/大比例更敏感，作为辅助指标与 Cliff's delta 并列报告。
    """
    if not (0.0 <= p1 <= 1.0 and 0.0 <= p2 <= 1.0):
        raise ValueError("比例必须落在 [0, 1] 区间")
    return float(2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2)))
