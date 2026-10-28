"""ORM 模型 —— 电影域 movies / reviews / crawl_jobs（原系统）+ 动漫域 anime / anime_source / divergence。

动漫域对应 `2026-09-17-anime-cross-site-divergence-design.md` §5。
Review 同时服务两域：movie_id 为空即电影整库样本，anime_id 为空即非动漫域。
"""
from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Movie(Base):
    """动态采集影片索引（IMDB/豆瓣）。movie_id 形如 imdb:tt0111161 / douban:1292052。"""

    __tablename__ = "movies"

    movie_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(16))          # imdb / douban
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # —— 影片元数据（豆瓣详情接口抓取，供前端做影片简介页）——
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)            # 剧情简介
    poster: Mapped[str | None] = mapped_column(String(500), nullable=True)    # 海报 URL
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)        # 豆瓣评分 0-10
    genres: Mapped[str | None] = mapped_column(String(200), nullable=True)    # 类型："剧情 / 犯罪"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    """影评主表：静态 IMDB 语料与实时采集/手动新增统一落库。"""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # 空 = IMDB 整库样本
    anime_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # 动漫域；空 = 电影
    source: Mapped[str] = mapped_column(String(16), index=True)  # imdb_static / imdb_live / douban_live / manual
    lang: Mapped[str] = mapped_column(String(8), default="en")   # en / zh
    text: Mapped[str] = mapped_column(Text)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 豆瓣 1-5
    review_time: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # 评论原始发表时间 YYYY-MM-DD（趋势图用）
    ground_truth: Mapped[str | None] = mapped_column(String(16), nullable=True)  # IMDB 正/负标签
    pred_label: Mapped[str | None] = mapped_column(String(16), nullable=True)    # positive / negative
    pred_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    model: Mapped[str | None] = mapped_column(String(16), nullable=True)          # textcnn / tencent
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrawlJob(Base):
    """抓取任务进度（App 轮询）。"""

    __tablename__ = "crawl_jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(16))
    query: Mapped[str | None] = mapped_column(String(200), nullable=True)
    movie_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/running/done/failed/degraded
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    limit: Mapped[int] = mapped_column(Integer, default=200)
    refresh: Mapped[bool] = mapped_column(Boolean, default=False)  # true=强制重抓；false=已有评论则复用
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ======================= 动漫域（跨站口碑分歧分析） =======================


class Anime(Base):
    """番剧主表。anime_id 形如 bangumi:253 —— 取归并时的锚点站点 ID（规格 §5.1）。"""

    __tablename__ = "anime"

    anime_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title_cn: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    title_jp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_en: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    season: Mapped[str | None] = mapped_column(String(16), nullable=True)       # 如 2024春
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    studio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnimeSource(Base):
    """跨站映射与各站原始数据（规格 §5.1）。"""

    __tablename__ = "anime_source"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_anime_source_sid"),
        UniqueConstraint("anime_id", "source", name="uq_anime_source_anime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("anime.anime_id"), index=True)
    source: Mapped[str] = mapped_column(String(16), index=True)   # bangumi / bilibili / anilist / mal
    source_id: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rating_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_scale: Mapped[float | None] = mapped_column(Float, nullable=True)      # 10 或 100
    rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_weighted: Mapped[float | None] = mapped_column(Float, nullable=True)   # 收缩后(10分制)

    review_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment_neg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment_mean: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)   # 人工校正过的映射
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Divergence(Base):
    """分歧结果缓存（规格 §5.1）。"""

    __tablename__ = "divergence"

    anime_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("anime.anime_id"), primary_key=True)
    d_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    quadrant: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sources_rating: Mapped[str | None] = mapped_column(String(128), nullable=True)     # 逗号分隔
    sources_sentiment: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 逗号分隔
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)   # 完整结果 JSON
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ======================= 用户域（认证 + 推荐画像） =======================


class User(Base):
    """用户账号（规格 §2.4）。password_hash 为加盐哈希，任何接口都不得返回。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # 即接口 user_id
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # 单设备在线，新登录顶掉旧 token
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchEvent(Base):
    """用户搜索行为（规格 §2.5）：推荐画像的唯一数据源，不建冗余画像表。

    仅在 POST /crawl 处理成功并匹配到影片、且请求带有效 token 时写入；游客不记录。
    """

    __tablename__ = "search_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)       # 关联 users.id
    movie_id: Mapped[str] = mapped_column(String(64), index=True)   # 搜索并成功匹配到的影片
    keyword: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 用户原始搜索词
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
