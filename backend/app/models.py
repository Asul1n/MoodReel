"""ORM 模型 —— movies / reviews / crawl_jobs 三表（对应设计规格 §4）。"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Review(Base):
    """影评主表：静态 IMDB 语料与实时采集/手动新增统一落库。"""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # 空 = IMDB 整库样本
    source: Mapped[str] = mapped_column(String(16), index=True)  # imdb_static / imdb_live / douban_live / manual
    lang: Mapped[str] = mapped_column(String(8), default="en")   # en / zh
    text: Mapped[str] = mapped_column(Text)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 豆瓣 1-5
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
    limit: Mapped[int] = mapped_column(Integer, default=60)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
