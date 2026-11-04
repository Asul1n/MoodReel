"""观点洞察路由：分组差异的显著性分析。

与 `/divergence/{anime_id}` 的分工：
  - `/divergence/*`   跨站点的评分/情感差异，面向"哪部番口碑分裂"
  - `/insight/*`      任意分组的分布差异检验，面向"差异是否统计显著"

前者回答"有多大差距"，后者回答"这个差距是不是噪声"。两者互补，不互相替代。

所有参数都显式暴露，是为了让实验可复现：论文需记录 n_perm / n_boot / seed
与 alpha，否则结果无法被复算。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services import group_divergence
from ..services.group_divergence import (MAX_N_BOOT, MAX_N_PERM,
                                         SUPPORTED_GROUP_BY, SUPPORTED_MEASURE)

router = APIRouter(tags=["insight"])


def _validate(group_by: str, measure: str) -> None:
    """分组与度量都是可插拔的，当前仅实现一组，其余返回明确的 400 而非静默降级。"""
    if group_by not in SUPPORTED_GROUP_BY:
        raise HTTPException(
            400, f"不支持的 group_by: {group_by}；当前可用：{sorted(SUPPORTED_GROUP_BY)}")
    if measure not in SUPPORTED_MEASURE:
        raise HTTPException(
            400, f"不支持的 measure: {measure}；当前可用：{sorted(SUPPORTED_MEASURE)}")


@router.get("/insight/group-divergence")
def group_divergence_analysis(
    movie_id: str | None = Query(None, description="只分析指定影片；留空则分析全库"),
    group_by: str = Query("stars", description="分组变量：stars（4-5★ vs 1-2★，3★ 丢弃）"),
    measure: str = Query("polarity", description="度量：polarity（整句情感极性 ±1）"),
    min_group: int = Query(20, ge=2, le=500, description="每组的少样本门槛"),
    alpha: float = Query(0.05, gt=0.0, lt=1.0, description="FDR 控制的显著性水平"),
    n_perm: int = Query(2000, ge=100, le=MAX_N_PERM, description="置换次数"),
    n_boot: int = Query(500, ge=100, le=MAX_N_BOOT, description="bootstrap 次数"),
    seed: int = Query(42, description="随机种子，保证结果可复现"),
    db: Session = Depends(get_db),
) -> dict:
    """分组差异检验：Cliff's delta + 置换检验 + bootstrap 区间 + BH-FDR。

    论文级精度建议显式传 `n_perm=5000&n_boot=2000`；默认值为了交互响应速度
    做了折中，p 值分辨率受 n_perm 限制（2000 次时下限约 5e-4，报告应写
    `p < 0.001` 而非具体数值）。
    """
    _validate(group_by, measure)

    if movie_id is not None:
        if db.get(models.Movie, movie_id) is None:
            raise HTTPException(404, "影片不存在")
        try:
            result = group_divergence.analyze_movie(
                db, movie_id, min_group=min_group, alpha=alpha,
                n_perm=n_perm, n_boot=n_boot, seed=seed)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {
            "group_by": group_by,
            "measure": measure,
            "method": group_divergence._method_meta(
                alpha=alpha, n_perm=n_perm, n_boot=n_boot, seed=seed),
            "results": [result],
        }

    try:
        return group_divergence.analyze_all(
            db, min_group=min_group, alpha=alpha,
            n_perm=n_perm, n_boot=n_boot, seed=seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
