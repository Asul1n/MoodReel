"""分组观点分歧分析：把"跨站分歧"抽象成可插拔的分组比较框架。

## 为什么这样抽象

项目最初的"跨站分歧"依赖至少两个站点有真实数据，而当前库中豆瓣外的站点
只有离线样本（合计 18 条），跨站比较事实上无法开展。若把结论依赖于某个
特定分组维度，方法就只在一种数据条件下成立。

因此这里把"分歧"重新定义为**任意两个群体在同一度量上的分布差异**：

    divergence = f(样本, 分组变量 group_by, 度量 measure)

- `group_by` 决定"谁和谁比"：评分档 stars / 站点 source / 时间窗 time_window
- `measure`  决定"比什么"：整句极性 polarity / 方面情感 aspect:剧情 …

分组与度量都做成可插拔，方法学是主干、数据只是实例。当前实现只落地
`stars` + `polarity` 一组，作为框架的正确性验证；ABSA（方面级情感）落地后
只需新增一个 measure，不动任何统计代码。

## 当前版本的已知局限

用 `stars` 分组、`pred_label` 度量，两者都源自"用户评价"，存在同义反复风险：
打 5 星的人文本更正面是近乎必然的。所以本版本**只用于验证框架正确性**
（高分组效应量应为正且显著），不能作为"发现了新知识"的结论。真正的发现
要等 measure 换成方面级——那时才能回答"低分组在哪个方面不满"。

## 多重比较

`analyze_all` 会同时对多部影片做检验，因此必须在**全部检验**上统一做
BH-FDR 校正，而不是逐片按 α=0.05 判定。逐片判定时，14 部影片中至少出现
一个假阳性的概率约 51%。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from .. import models
from . import stats

# —— 可插拔的度量与分组 ——
# 情感标签 → 数值。neutral 目前不存在于数据中，但保留以兼容后续三分类。
POLARITY_MAP: dict[str, float] = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

SUPPORTED_GROUP_BY = {"stars"}
SUPPORTED_MEASURE = {"polarity"}

# 评分档划分：4-5 星为高分组，1-2 星为低分组，3 星（中性）丢弃。
# 丢弃而非归入某组，是因为 3 星本身语义分裂（"还行"既可能偏正也可能偏负），
# 强行归类会向两组注入噪声。
HIGH_STARS = (4, 5)
LOW_STARS = (1, 2)

# 计算量上限，防止一次请求触发过长的置换/bootstap 循环
MAX_N_PERM = 10000
MAX_N_BOOT = 5000


@dataclass
class GroupSamples:
    """一部影片切分后的两组度量值。"""

    high: list[float]
    low: list[float]
    dropped_neutral: int      # 3 星被丢弃的条数
    dropped_no_label: int     # 有星级但无情感标签的条数

    @property
    def total_used(self) -> int:
        return len(self.high) + len(self.low)


def measure_polarity(label: str | None) -> float | None:
    """整句极性度量：positive→+1，negative→−1，未知→None（丢弃）。"""
    if label is None:
        return None
    return POLARITY_MAP.get(label.strip().lower())


def split_by_stars(rows: list[tuple[int | None, str | None]]) -> GroupSamples:
    """按星级切成高分组/低分组，丢弃 3 星与无标签样本。

    rows 是 (stars, pred_label) 序列，应由调用方保证 movie_id 与 source 已筛选。
    """
    high: list[float] = []
    low: list[float] = []
    dropped_neutral = 0
    dropped_no_label = 0

    for stars, label in rows:
        value = measure_polarity(label)
        if stars in HIGH_STARS:
            if value is None:
                dropped_no_label += 1
            else:
                high.append(value)
        elif stars in LOW_STARS:
            if value is None:
                dropped_no_label += 1
            else:
                low.append(value)
        else:
            dropped_neutral += 1

    return GroupSamples(high=high, low=low,
                        dropped_neutral=dropped_neutral,
                        dropped_no_label=dropped_no_label)


def _fetch_rows(db: Session, movie_id: str | None) -> dict[str, list[tuple[int | None, str | None]]]:
    """按影片归集 (stars, pred_label)。movie_id 为空时返回全库。"""
    query = db.query(models.Review.movie_id, models.Review.stars, models.Review.pred_label).filter(
        models.Review.movie_id.isnot(None),
        models.Review.stars.isnot(None),
        models.Review.pred_label.isnot(None),
    )
    if movie_id is not None:
        query = query.filter(models.Review.movie_id == movie_id)

    grouped: dict[str, list[tuple[int | None, str | None]]] = {}
    for mid, stars, label in query.all():
        grouped.setdefault(mid, []).append((stars, label))
    return grouped


def _titles(db: Session) -> dict[str, str]:
    return {mid: title for mid, title in db.query(models.Movie.movie_id, models.Movie.title).all()}


def _validate_params(*, min_group: int, alpha: float,
                     n_perm: int, n_boot: int) -> None:
    """两个入口共用的参数校验，避免批量分析绕过限制触发超长计算。"""
    if min_group < 2:
        raise ValueError("min_group 至少为 2")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha 必须落在 (0, 1) 区间")
    if n_perm > MAX_N_PERM or n_boot > MAX_N_BOOT:
        raise ValueError(f"计算量超限：n_perm ≤ {MAX_N_PERM}，n_boot ≤ {MAX_N_BOOT}")


def _method_meta(*, alpha: float, n_perm: int, n_boot: int, seed: int) -> dict:
    """实验方法元信息，必须随结果一起返回——论文的可复现性依赖这组参数。"""
    return {
        "effect_size": "cliffs_delta",
        "test": "permutation_two_sided",
        "correction": "benjamini_hochberg",
        "alpha": alpha,
        "n_perm": n_perm,
        "n_boot": n_boot,
        "seed": seed,
        "group_definition": {"high": "4-5 stars", "low": "1-2 stars", "dropped": "3 stars"},
        "measure": "pred_label polarity (+1 / -1)",
    }


def analyze_movie(db: Session, movie_id: str, *, min_group: int = 20,
                  alpha: float = 0.05, n_perm: int = stats.DEFAULT_N_PERM,
                  n_boot: int = stats.DEFAULT_N_BOOT, seed: int = 42) -> dict:
    """单部影片的分组比较。

    a 组固定为高分组、b 组为低分组，因此 delta > 0 表示"高分组文本更正面"，
    这是理论预期的方向；若出现 delta < 0 会被标记为 anomaly，提示数据或
    情感预测存在问题，属于质量控制信号而非结论。
    """
    _validate_params(min_group=min_group, alpha=alpha,
                     n_perm=n_perm, n_boot=n_boot)

    rows = _fetch_rows(db, movie_id).get(movie_id, [])
    samples = split_by_stars(rows)
    title = _titles(db).get(movie_id, movie_id)

    base = {
        "movie_id": movie_id,
        "title": title,
        "group_a": "high(4-5★)",
        "group_b": "low(1-2★)",
        "dropped": {"neutral_3star": samples.dropped_neutral,
                    "no_label": samples.dropped_no_label},
    }

    # 样本量门槛：两组都要够，否则置换检验的零分布不可靠
    if len(samples.high) < min_group or len(samples.low) < min_group:
        return {
            **base,
            "status": "insufficient_data",
            "reason": (f"高分组 {len(samples.high)} 条、低分组 {len(samples.low)} 条，"
                       f"未达每组最少 {min_group} 条"),
            "n_a": len(samples.high),
            "n_b": len(samples.low),
        }

    comparison = stats.compare_groups(samples.high, samples.low, n_perm=n_perm,
                                      n_boot=n_boot, alpha=alpha, seed=seed)
    # 单次比较也走一次 FDR：m=1 时 q 恒等于 p，语义与批量分析保持一致，
    # 否则 significant 字段会因"没走批量"而恒为 False，接口调用方无法判断。
    stats.apply_fdr([comparison], alpha=alpha)

    return {
        **base,
        "status": "ok",
        **comparison.to_dict(),
        # 理论一致性：高分组文本应更正面。相反即为数据质量信号
        "anomaly": comparison.effect_size < 0,
        "pos_rate_a": round(float(np.mean([v > 0 for v in samples.high])), 4),
        "pos_rate_b": round(float(np.mean([v > 0 for v in samples.low])), 4),
    }


def analyze_all(db: Session, *, min_group: int = 20, alpha: float = 0.05,
                n_perm: int = stats.DEFAULT_N_PERM,
                n_boot: int = stats.DEFAULT_N_BOOT, seed: int = 42) -> dict:
    """全库批量分析，统一做 FDR 校正后返回。

    p 值收集完才能校正，因此不能边算边判定显著——这是本函数存在的理由。
    """
    _validate_params(min_group=min_group, alpha=alpha,
                     n_perm=n_perm, n_boot=n_boot)

    grouped = _fetch_rows(db, None)
    titles = _titles(db)

    tested: list[dict] = []
    comparisons: list[stats.GroupComparison] = []
    skipped: list[dict] = []

    # 每部影片用 seed + 序号 生成独立随机流：若共用同一 seed，各片的置换
    # 序列完全相同，会让不同影片的 p 值产生人为相关性（inference 不独立）。
    # 序号来自排序后的 movie_id，因此仍然完全可复现。
    for index, movie_id in enumerate(sorted(grouped)):
        samples = split_by_stars(grouped[movie_id])
        if len(samples.high) < min_group or len(samples.low) < min_group:
            skipped.append({
                "movie_id": movie_id,
                "title": titles.get(movie_id, movie_id),
                "n_a": len(samples.high),
                "n_b": len(samples.low),
            })
            continue

        comparison = stats.compare_groups(samples.high, samples.low, n_perm=n_perm,
                                          n_boot=n_boot, alpha=alpha,
                                          seed=seed + index)
        comparisons.append(comparison)
        tested.append({
            "movie_id": movie_id,
            "title": titles.get(movie_id, movie_id),
            "n_a": comparison.n_a,
            "n_b": comparison.n_b,
            "pos_rate_a": round(float(np.mean([v > 0 for v in samples.high])), 4),
            "pos_rate_b": round(float(np.mean([v > 0 for v in samples.low])), 4),
            "_comparison": comparison,
        })

    stats.apply_fdr(comparisons, alpha=alpha)

    results: list[dict] = []
    for item, comparison in zip(tested, comparisons):
        item.pop("_comparison")
        results.append({
            **item,
            "group_a": "high(4-5★)",
            "group_b": "low(1-2★)",
            **comparison.to_dict(),
            "anomaly": comparison.effect_size < 0,
        })

    # 按效应量绝对值降序，最值得看的排前面
    results.sort(key=lambda r: -abs(r["effect_size"]))

    significant = [r for r in results if r["significant"]]
    practical = [r for r in results if r["practically_significant"]]
    median_effect = (round(float(np.median([r["effect_size"] for r in results])), 4)
                     if results else None)

    # 天花板效应检测：当多数比较的效应量都很大时，说明度量本身区分度饱和，
    # 分组与度量高度同源，此时"显著"不构成发现。这是引出更细粒度度量的依据，
    # 而不是需要庆祝的结果。论文的预实验小节应当如实报告这一点。
    ceiling = bool(median_effect is not None and abs(median_effect) > 0.7)

    return {
        "group_by": "stars",
        "measure": "polarity",
        "method": _method_meta(alpha=alpha, n_perm=n_perm, n_boot=n_boot, seed=seed),
        "summary": {
            "movies_eligible": len(grouped),
            "movies_tested": len(results),
            "movies_skipped": len(skipped),
            "significant": len(significant),
            "practically_significant": len(practical),
            "significant_but_negligible": len(significant) - len(practical),
            "anomalies": sum(1 for r in results if r["anomaly"]),
            "median_effect": median_effect,
            "ceiling_effect": ceiling,
            "note": ("效应量中位数超过 0.7，分组（星级）与度量（整句极性）高度同源，"
                     "结论接近同义反复；应改用方面级度量后重跑，才能观察到细分差异"
                     if ceiling else None),
        },
        "results": results,
        "skipped": skipped,
    }
