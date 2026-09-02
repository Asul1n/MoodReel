"""评论热点挖掘模块路由：Top 热点词 / 褒贬倾向词 / 词云数据。

成员B基于 app/services/nlp.py 实现后接通。
"""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/hotspot", tags=["hotspot"])


@router.get("")
def hotspot(
    context: str = Query("whole", description="whole 或 movie:{movie_id}"),
    top_n: int = Query(30, ge=1, le=100),
) -> dict:
    # 返回示例结构：
    # {
    #   "context": ..., "keywords": [{"word","weight"}],
    #   "polarity_pos": [{"word","weight"}], "polarity_neg": [...],
    #   "cloud": [{"word","weight"}]
    # }
    raise HTTPException(status_code=501, detail="成员B实现：热点挖掘（见 services/nlp.py）")
