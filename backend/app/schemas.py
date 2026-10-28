"""Pydantic 请求/响应模型（接口契约见规格 §6）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    ok: bool
    model_ready: bool
    version: str


class AnalyzeRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=500)
    lang: str | None = None  # en / zh；缺省按文本自动判定


class AnalyzeItem(BaseModel):
    text: str
    lang: str
    model: str          # textcnn / tencent
    label: str          # positive / negative
    prob: float         # 置信度 0-1
    ms: float           # 单条耗时(ms)


class AnalyzeBatchOut(BaseModel):
    results: list[AnalyzeItem]
    count: int
    elapsed_ms: float
    throughput: float   # 条/秒（>=200 的目标在此体现）


class CrawlOut(BaseModel):
    job_id: str


class ReviewOut(BaseModel):
    id: int
    text: str
    lang: str
    source: str
    movie_id: str | None
    ground_truth: str | None
    pred_label: str | None
    pred_prob: float | None


class ReviewListOut(BaseModel):
    total: int
    items: list[ReviewOut]


# ======================= 用户认证（/auth，契约「用户认证约定」2026-10） =======================


class RegisterIn(BaseModel):
    username: str
    password: str


class RegisterOut(BaseModel):
    user_id: int
    username: str
    created_at: datetime


class AuthUserOut(BaseModel):
    user_id: int
    username: str


class LoginOut(BaseModel):
    token: str
    user: AuthUserOut


class LogoutOut(BaseModel):
    ok: bool = True


# ======================= 为你推荐（GET /recommend，契约「推荐约定」2026-10） =======================


class RecommendItem(BaseModel):
    movie_id: str
    title: str
    poster: str | None = None
    rating: float | None = None
    genres: str = ""            # 统一 " / " 分隔
    reason: str = ""            # 个性化=命中标签（"科幻 ×2"）；hot="近期热门"


class RecommendOut(BaseModel):
    mode: str                   # personalized / hot
    items: list[RecommendItem]
