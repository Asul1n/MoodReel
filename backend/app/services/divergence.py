"""跨站口碑分歧引擎（规格 §6）。

本模块前半是纯函数（易测、无副作用），后半（Task 7）是站点筛选与结果汇总。
"""
import math

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
