"""Pydantic 请求/响应模型（接口契约见规格 §6）。"""
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
