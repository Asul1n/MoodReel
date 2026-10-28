"""推荐服务：热点兜底 + 基于 search_events 的实时标签画像。

口径见 `docs/3_接口契约文档.md`「推荐约定」（2026-10）：

1. 取该用户 `search_events` 中的影片集合（同一影片去重，只计一次）；
2. 拆 `genres` 标签（兼容 `/`、`,`、`，`、`、` 分隔，返回前端统一为 ` / `）；
3. 标签权重归一：每部影片的每个标签贡献 `1/标签数`（避免"剧情"等大众标签主导画像）；
4. 用户标签向量 = 已搜影片的标签贡献求和；
5. 候选打分 = 未搜索过的影片的各标签在用户向量中的权重之和，降序取前 limit；
6. 冷启动（无搜索记录 / 得分全 0）→ `mode: hot`，按 review_count 降序（并列取最新）取前 limit；
7. 不建画像表，全部实时聚合（单用户数据量小）。
"""
import re
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models

_GENRE_SEP_RE = re.compile(r"[/,，、]")


def split_genres(genres: str | None) -> list[str]:
    """把 "科幻,冒险 / 动作" 拆成去空去重后的标签列表（保持原顺序）。"""
    if not genres:
        return []
    out: list[str] = []
    for part in _GENRE_SEP_RE.split(genres):
        tag = part.strip()
        if tag and tag not in out:
            out.append(tag)
    return out


def join_genres(genres: str | None) -> str:
    """返回前端的统一展示口径：" / " 分隔。"""
    return " / ".join(split_genres(genres))


def _searched_ids(db: Session, user_id: int) -> set[str]:
    """该用户搜索过的影片集合（同一影片多次搜索只算一次）。"""
    rows = (db.query(models.SearchEvent.movie_id)
            .filter(models.SearchEvent.user_id == user_id)
            .distinct().all())
    return {r[0] for r in rows if r[0]}


def _profile(db: Session, searched: set[str]) -> tuple[dict[str, float], dict[str, int]]:
    """用户标签画像：{tag: 权重} 与 {tag: 贡献影片数}（后者供 reason 文案用）。"""
    weights: dict[str, float] = {}
    sources: dict[str, int] = {}
    if not searched:
        return weights, sources
    movies = db.query(models.Movie).filter(models.Movie.movie_id.in_(list(searched))).all()
    for m in movies:
        tags = split_genres(m.genres)
        if not tags:
            continue
        contribution = 1.0 / len(tags)          # 1/n 归一，抑制大众标签
        for tag in tags:
            weights[tag] = weights.get(tag, 0.0) + contribution
            sources[tag] = sources.get(tag, 0) + 1
    return weights, sources


def _item(movie: models.Movie, reason: str) -> dict:
    return {
        "movie_id": movie.movie_id,
        "title": movie.title,
        "poster": movie.poster,
        "rating": movie.rating,
        "genres": join_genres(movie.genres),
        "reason": reason,
    }


def hot(db: Session, limit: int, exclude: set[str] | None = None) -> list[dict]:
    """热点兜底：review_count 降序，并列取最新入库；可排除指定影片。"""
    review_count = (
        db.query(func.count(models.Review.id))
        .filter(models.Review.movie_id == models.Movie.movie_id)
        .correlate(models.Movie)
        .scalar_subquery()
    )
    q = db.query(models.Movie, review_count.label("review_count"))
    if exclude:
        q = q.filter(models.Movie.movie_id.notin_(list(exclude)))
    rows = (q.order_by(review_count.desc(), models.Movie.created_at.desc())
             .limit(limit).all())
    return [_item(m, "近期热门") for m, _ in rows]


def personalized(db: Session, user_id: int, limit: int) -> list[dict]:
    """个性化：按标签命中权重排序；无命中返回空列表（调用方据此降级 hot）。"""
    searched = _searched_ids(db, user_id)
    weights, sources = _profile(db, searched)

    q = db.query(models.Movie)
    if searched:
        q = q.filter(models.Movie.movie_id.notin_(list(searched)))
    candidates = q.all()
    scored: list[tuple[float, datetime, models.Movie, list[str]]] = []
    for m in candidates:
        tags = split_genres(m.genres)
        matched = [t for t in tags if t in weights]
        if not matched:
            continue
        score = sum(weights[t] for t in matched)
        scored.append((score, m.created_at or datetime.min, m, matched))

    # 得分降序；同分取较新入库的
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    out: list[dict] = []
    for score, _, movie, matched in scored[:limit]:
        matched.sort(key=lambda t: weights[t], reverse=True)
        reason = " · ".join(f"{t} ×{sources.get(t, 1)}" for t in matched)
        out.append(_item(movie, reason))
    return out


def recommend(db: Session, user_id: int | None, limit: int) -> dict:
    """对外统一入口：登录且有命中 → personalized；否则 hot（游客/失效 token 同 hot）。"""
    if user_id is not None:
        items = personalized(db, user_id, limit)
        if items:
            return {"mode": "personalized", "items": items}
        # 冷启动 / 得分全 0：热点兜底，且不把用户已搜过的片再推给他
        return {"mode": "hot", "items": hot(db, limit, exclude=_searched_ids(db, user_id))}
    return {"mode": "hot", "items": hot(db, limit)}
