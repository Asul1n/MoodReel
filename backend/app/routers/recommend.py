"""为你推荐路由：登录按 search_events 画像个性化，游客/冷启动降级热点。

契约见 `docs/3_接口契约文档.md`「推荐约定」（2026-10）：
`GET /recommend?limit=6` → `{mode: personalized|hot, items:[{movie_id,title,poster,rating,genres,reason}]}`；
token 无效/过期**不报 401**，直接按游客降级 hot（非关键功能，优雅降级）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import RecommendOut
from ..services import auth, recommend as recommend_svc

router = APIRouter(tags=["recommend"])


@router.get("/recommend", response_model=RecommendOut)
def get_recommend(limit: int = Query(6, ge=1, le=20, description="返回条数(默认6,≤20)"),
                  user_id: int | None = Depends(auth.optional_user_id),
                  db: Session = Depends(get_db)) -> RecommendOut:
    return recommend_svc.recommend(db, user_id, limit)
