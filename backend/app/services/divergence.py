"""跨站口碑分歧引擎（规格 §6）。

本模块前半是纯函数（易测、无副作用），后半（Task 7）是站点筛选与结果汇总。
"""
import math
from dataclasses import dataclass, field

# 象限取值（规格 §6.3）
CONSENSUS = "consensus"                     # 共识番：评分接近 + 情感一致
HIDDEN_CONTROVERSY = "hidden_controversy"   # 分数掩盖了争议：评分接近 + 情感分裂
SCALE_BIAS = "scale_bias"                   # 打分习惯差异：评分悬殊 + 情感一致
FULL_CONTROVERSY = "full_controversy"       # 全面争议


def normalize_rating(raw: float, scale: float) -> float:
    """把任意分制归一到 10 分制（AniList 为 100 分制）。"""
    if scale <= 0:
        raise ValueError("rating_scale 必须为正数")
    return float(raw) * (10.0 / float(scale))


def bayesian_shrink(r_norm: float, v: int, c: float, m: int = 500) -> float:
    """IMDB 加权：小样本向先验 C 收缩（规格 §6.1）。

    R_weighted = (v·R + m·C) / (v + m)

    B站 10 万人打 9.2 与 AniList 5 千人打 8.1 直接比较不成立；
    收缩后样本量小的站向均值回归，避免小样本极端值主导分歧指数。
    """
    if v < 0:
        raise ValueError("评分人数不得为负")
    if m < 0:
        raise ValueError("先验权重不得为负")
    return (v * float(r_norm) + m * float(c)) / (v + m)


def weighted_std(values: list[float], weights: list[float]) -> float:
    """加权标准差 σ_w = sqrt( Σw(x−x̄w)² / Σw )（规格 §6.2）。"""
    if len(values) != len(weights):
        raise ValueError("values 与 weights 长度必须一致")
    total = sum(weights)
    if total <= 0:
        raise ValueError("权重之和必须为正")
    mean = sum(w * x for w, x in zip(weights, values)) / total
    var = sum(w * (x - mean) ** 2 for w, x in zip(weights, values)) / total
    return math.sqrt(var)


def polarity(pos: int, neg: int) -> float:
    """情感极性 ∈ [−1, 1]；无评论返回 0（不除零）。"""
    n = int(pos) + int(neg)
    if n <= 0:
        return 0.0
    return (int(pos) - int(neg)) / n


def classify_quadrant(d_rating: float, d_sent: float,
                      thr_r: float, thr_s: float) -> str:
    """四象限判定（规格 §6.3）。阈值处取"低位"（< 为低）。"""
    r_low = d_rating < thr_r
    s_low = d_sent < thr_s
    if r_low and s_low:
        return CONSENSUS
    if r_low and not s_low:
        return HIDDEN_CONTROVERSY
    if not r_low and s_low:
        return SCALE_BIAS
    return FULL_CONTROVERSY


@dataclass
class SourceStat:
    """单个站点参与计算所需的统计量。rating_norm 须已归一化到 10 分制。"""
    source: str
    rating_norm: float | None = None
    rating_count: int | None = None
    pos: int | None = None
    neg: int | None = None
    review_count: int | None = None


@dataclass
class DivergenceResult:
    status: str                                   # ok | insufficient_data
    d_rating: float | None = None
    d_sentiment: float | None = None
    quadrant: str | None = None
    sources_rating: list[str] = field(default_factory=list)
    sources_sentiment: list[str] = field(default_factory=list)
    ratings: list[dict] = field(default_factory=list)     # [{source, rating_weighted, weight}]
    sentiment: list[dict] = field(default_factory=list)   # [{source, mean, pos, neg, review_count}]
    reason: str | None = None


def compute_divergence(stats: list[SourceStat], *, thr_r: float, thr_s: float,
                       m: int, min_rating_count: int, min_reviews: int,
                       low_conf_weight: float = 0.5) -> DivergenceResult:
    """按规格 §6.2–§6.4 汇总分歧结果。

    两个指标的参与站点集合可以不同：
      - 无评分的站点不进 D_rating（也不计入先验 C 的均值）
      - 评论数 < min_reviews 的站点不进 D_sent

    `sources_rating` / `sources_sentiment` 的语义是**真正进入计算的站点**：
    某指标可用站点不足 2 个时算不出标准差，该列表即为空，对应值为 None。
    未进入计算的分站原始数据（各站评分与情感计数）仍可从
    `GET /anime/{id}/sources` 取得，不在此处重复。

    任一指标算得出即 status=ok；两个都算不出才 insufficient_data。
    """
    # —— 评分侧 ——
    rated = [s for s in stats if s.rating_norm is not None]
    sources_rating: list[str] = []
    ratings: list[dict] = []
    d_rating: float | None = None

    # 先验 C = 各站 R_norm 的均值（规格 §6.1）
    c = (sum(s.rating_norm for s in rated) / len(rated)) if rated else 0.0
    if len(rated) >= 2:
        vals, weights = [], []
        for s in rated:
            v = int(s.rating_count or 0)
            w = low_conf_weight if v < min_rating_count else 1.0
            rw = bayesian_shrink(s.rating_norm, v, c, m)
            vals.append(rw)
            weights.append(w)
            sources_rating.append(s.source)
            ratings.append({"source": s.source,
                            "rating_weighted": round(rw, 4), "weight": w})
        d_rating = weighted_std(vals, weights)

    # —— 情感侧 ——
    reviewed = [s for s in stats if int(s.review_count or 0) >= min_reviews]
    sources_sentiment: list[str] = []
    sentiment: list[dict] = []
    d_sent: float | None = None
    if len(reviewed) >= 2:
        vals, weights = [], []
        for s in reviewed:
            p = polarity(int(s.pos or 0), int(s.neg or 0))
            # 评分人数不足的站点在情感侧同样降权
            w = (low_conf_weight
                 if s.rating_count is not None
                 and int(s.rating_count) < min_rating_count else 1.0)
            vals.append(p)
            weights.append(w)
            sources_sentiment.append(s.source)
            sentiment.append({"source": s.source, "mean": round(p, 4),
                              "pos": int(s.pos or 0), "neg": int(s.neg or 0),
                              "review_count": int(s.review_count or 0)})
        d_sent = weighted_std(vals, weights)

    if d_rating is None and d_sent is None:
        return DivergenceResult(
            status="insufficient_data",
            reason=f"可用站点不足：评分 {len(rated)} 个、情感 {len(reviewed)} 个，均少于 2")

    quadrant = None
    if d_rating is not None and d_sent is not None:
        quadrant = classify_quadrant(d_rating, d_sent, thr_r, thr_s)

    return DivergenceResult(
        status="ok",
        d_rating=round(d_rating, 4) if d_rating is not None else None,
        d_sentiment=round(d_sent, 4) if d_sent is not None else None,
        quadrant=quadrant,
        sources_rating=sources_rating,
        sources_sentiment=sources_sentiment,
        ratings=ratings,
        sentiment=sentiment,
    )
