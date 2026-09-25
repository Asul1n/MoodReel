"""动漫域三表建模测试。"""
from app.db import SessionLocal
from app import models


def test_create_anime_with_sources() -> None:
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:253", title_cn="进击的巨人",
                            title_jp="進撃の巨人", year=2013, episodes=25))
        db.add(models.AnimeSource(anime_id="bangumi:253", source="bangumi",
                                  source_id="253", rating_raw=8.6, rating_scale=10,
                                  rating_count=12000, review_count=340))
        db.add(models.AnimeSource(anime_id="bangumi:253", source="bilibili",
                                  source_id="4450", rating_raw=9.5, rating_scale=10,
                                  rating_count=98000, review_count=210))
        db.commit()

        a = db.get(models.Anime, "bangumi:253")
        assert a.title_jp == "進撃の巨人"
        rows = db.query(models.AnimeSource).filter_by(anime_id="bangumi:253").all()
        assert {r.source for r in rows} == {"bangumi", "bilibili"}
    finally:
        db.close()


def test_source_unique_constraint() -> None:
    """同一站同一 source_id 不得重复映射。"""
    import pytest
    from sqlalchemy.exc import IntegrityError
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:1", title_cn="测试"))
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi", source_id="1"))
        db.commit()
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi", source_id="1"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_review_accepts_anime_id() -> None:
    """Review 扩展 anime_id 后仍兼容旧电影数据（movie_id 用法不变）。"""
    db = SessionLocal()
    try:
        db.add(models.Review(movie_id="douban:1292052", source="douban_live",
                             lang="zh", text="老数据"))
        db.add(models.Review(anime_id="bangumi:253", source="bangumi_live",
                             lang="zh", text="新数据"))
        db.commit()
        assert db.query(models.Review).count() == 2
    finally:
        db.close()
