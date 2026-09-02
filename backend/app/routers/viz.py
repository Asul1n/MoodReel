"""可视化模块路由：一次返回所选上下文的图表聚合数据（App 只负责渲染）。

成员A/B 组合 dataset + sentiment + hotspot 后接通。
"""
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/viz", tags=["viz"])


@router.get("/summary")
def summary(context: str = Query("whole")) -> dict:
    # 返回：{dist:{positive,negative}, top_words:[...], polarity:{pos:[],neg:[]}, trend:[{date,count}]}
    raise HTTPException(status_code=501, detail="成员实现：可视化聚合")
