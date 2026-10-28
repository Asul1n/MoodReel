"""推荐接口测试（接口契约「推荐约定」2026-10）。

口径：{mode, items[{movie_id,title,poster,rating,genres,reason}]}；
登录用户按 search_events 画像个性化推荐（同片去重、标签 1/n 归一、排除已搜索、
得分全 0 → hot 兜底）；游客/token 无效 → hot（review_count 降序，并列取最新）；
genres 统一 " / " 分隔返回。
"""
import datetime as dt

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def _seed_movie(mid, title, genres, n_reviews=0, minutes_ago=0) -> None:
    db = SessionLocal()
    try:
        db.add(models.Movie(
            movie_id=mid, title=title, source="douban", genres=genres,
            rating=8.0, poster=f"/p/{mid}.jpg",
            created_at=dt.datetime.utcnow() - dt.timedelta(minutes=minutes_ago)))
        for i in range(n_reviews):
            db.add(models.Review(movie_id=mid, source="douban_live", lang="zh",
                                 text=f"评论{i}"))
        db.commit()
    finally:
        db.close()


def _seed_event(user_id, movie_id, keyword="片名") -> None:
    db = SessionLocal()
    try:
        db.add(models.SearchEvent(user_id=user_id, movie_id=movie_id, keyword=keyword))
        db.commit()
    finally:
        db.close()


def _new_user_with_token(username="小明"):
    from app.services.auth import hash_password, new_token
    db = SessionLocal()
    try:
        u = models.User(username=username, password_hash=hash_password("pass123"),
                        token=new_token())
        db.add(u)
        db.commit()
        return u.id, u.token
    finally:
        db.close()


def test_empty_library_returns_hot_empty_items() -> None:
    r = client.get("/recommend")
    assert r.status_code == 200
    assert r.json() == {"mode": "hot", "items": []}


def test_guest_gets_hot_by_review_count() -> None:
    _seed_movie("douban:1", "老片", "剧情", n_reviews=50, minutes_ago=60)
    _seed_movie("douban:2", "热片", "科幻", n_reviews=100, minutes_ago=30)
    _seed_movie("douban:3", "新片", "科幻", n_reviews=100, minutes_ago=10)   # 并列取最新

    r = client.get("/recommend", params={"limit": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "hot"
    assert [i["movie_id"] for i in body["items"]] == ["douban:3", "douban:2"]
    assert all(i["reason"] == "近期热门" for i in body["items"])
    assert body["items"][0]["genres"] == "科幻"
    assert body["items"][0]["poster"] == "/p/douban:3.jpg"


def test_genres_normalized_to_slash_separator() -> None:
    _seed_movie("douban:9", "混合分隔", "科幻,冒险/动作")
    r = client.get("/recommend")
    assert r.json()["items"][0]["genres"] == "科幻 / 冒险 / 动作"


def test_all_scores_zero_falls_back_to_hot() -> None:
    """搜过的影片标签与候选无交集 → 得分全 0 → 冷启动兜底 hot。"""
    uid, token = _new_user_with_token("科幻迷")
    _seed_movie("douban:10", "科幻A", "科幻")
    _seed_movie("douban:11", "文艺片", "剧情 / 爱情")
    _seed_event(uid, "douban:10")

    r = client.get("/recommend", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["mode"] == "hot"
    assert [i["movie_id"] for i in body["items"]] == ["douban:11"]


def test_personalized_excludes_searched_and_carries_reason() -> None:
    uid, token = _new_user_with_token("科幻迷")
    _seed_movie("douban:20", "星海", "科幻 / 冒险")
    _seed_movie("douban:21", "机甲", "科幻 / 动作")
    _seed_movie("douban:22", "喜剧", "喜剧")
    _seed_event(uid, "douban:20", keyword="星海")
    _seed_event(uid, "douban:20", keyword="星海")     # 重复搜索同片去重
    _seed_event(uid, "douban:22", keyword="喜剧")

    r = client.get("/recommend", headers={"Authorization": f"Bearer {token}"})
    body = r.json()
    assert body["mode"] == "personalized"
    ids = [i["movie_id"] for i in body["items"]]
    assert ids == ["douban:21"]                        # 已搜索过的不推；无命中的不凑数
    assert "科幻 ×1" in body["items"][0]["reason"]
    assert body["items"][0]["title"] == "机甲"


def test_tag_weight_inverse_of_tag_count() -> None:
    """标签 1/n 归一：双标签候选（科幻+冒险各 0.5）得分高于单标签候选（科幻 0.5 之外无加成）。"""
    uid, token = _new_user_with_token("权重用户")
    _seed_movie("douban:30", "双标签源", "科幻 / 冒险")
    _seed_movie("douban:31", "单标签候选", "科幻 / 爱情")
    _seed_movie("douban:32", "双标签候选", "科幻 / 冒险")
    _seed_event(uid, "douban:30")

    r = client.get("/recommend", headers={"Authorization": f"Bearer {token}"})
    ids = [i["movie_id"] for i in r.json()["items"]]
    assert ids.index("douban:32") < ids.index("douban:31")


def test_cold_start_valid_token_no_events_falls_back_to_hot() -> None:
    _seed_movie("douban:40", "热片", "科幻", n_reviews=10)
    _, token = _new_user_with_token("新用户")
    r = client.get("/recommend", headers={"Authorization": f"Bearer {token}"})
    assert r.json()["mode"] == "hot"


def test_invalid_token_degrades_to_hot_not_401() -> None:
    _seed_movie("douban:50", "热片", "科幻", n_reviews=10)
    r = client.get("/recommend", headers={"Authorization": "Bearer deadbeef"})
    assert r.status_code == 200
    assert r.json()["mode"] == "hot"


def test_limit_bounds() -> None:
    _seed_movie("douban:60", "片", "剧情", n_reviews=1)
    assert client.get("/recommend", params={"limit": 0}).status_code == 422
    assert client.get("/recommend", params={"limit": 21}).status_code == 422
