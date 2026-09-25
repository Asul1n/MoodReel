"""动漫域路由：跨站检索 / 采集 / 单番各站数据（规格 §7）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.adapters import get_adapter
from ..services.identity import match_candidates

router = APIRouter(prefix="/anime", tags=["anime"])

# 归并阈值：低于此分不认为是同一部番（宁可漏合并，不可误合并）
MATCH_THRESHOLD = 0.7


@router.get("/search")
def search(q: str, sources: str = "bangumi,bilibili",
           db: Session = Depends(get_db)) -> dict:
    """跨站检索并按归并结果聚合候选番剧。

    单站失败不阻断整体检索：其结果记入 errors，其余站点照常返回。
    """
    query = (q or "").strip()
    wanted = [s.strip() for s in (sources or "").split(",") if s.strip()]
    errors: list[dict] = []
    if not query:
        return {"items": [], "errors": errors}

    per_source: dict[str, list] = {}
    for src in wanted:
        adapter = get_adapter(src)
        if adapter is None:
            errors.append({"source": src, "reason": "v1 未实现该站点"})
            continue
        res = adapter.search(query)
        if not res.ok:
            errors.append({"source": src, "reason": res.error})
            continue
        per_source[src] = list(res.data or [])

    # 以首个有结果的站点为锚点，其余站点按归并匹配并入同一条
    items: list[dict] = []
    anchor_src = next((s for s in wanted if per_source.get(s)), None)
    if anchor_src:
        for anchor in per_source[anchor_src]:
            group = [{"source": anchor.source, "source_id": anchor.source_id,
                      "title": anchor.title_cn, "year": anchor.year,
                      "url": anchor.url}]
            for other in wanted:
                if other == anchor_src:
                    continue
                match = match_candidates(anchor, per_source.get(other, []),
                                         threshold=MATCH_THRESHOLD)
                if match:
                    group.append({"source": match.source, "source_id": match.source_id,
                                  "title": match.title_cn, "year": match.year,
                                  "url": match.url})
                    # 已被归并的候选不再单独成条
                    per_source[other] = [c for c in per_source[other]
                                         if c.source_id != match.source_id]
            items.append({
                "anime_id": None,          # 尚未入库；ingest 后分配
                "title_cn": anchor.title_cn,
                "title_jp": anchor.title_jp,
                "title_en": anchor.title_en,
                "year": anchor.year,
                "episodes": anchor.episodes,
                "sources": group,
            })

    return {"items": items, "errors": errors}
