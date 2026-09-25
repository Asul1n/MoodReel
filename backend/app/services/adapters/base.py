"""四站适配器统一契约（规格 §4.2）。

设计要点：失败必须显式表达，禁止用空列表掩盖。
本模块由一次真实故障倒逼而来——豆瓣爬虫曾把"请求被限流"记成"搜索无结果"，
排障时完全看不出真实原因。
"""
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

Status = Literal["ok", "degraded", "failed"]


@dataclass
class Candidate:
    """检索候选（尚未归并到内部 anime_id）。"""
    source: str
    source_id: str
    title_cn: str | None = None
    title_jp: str | None = None
    title_en: str | None = None
    year: int | None = None
    episodes: int | None = None
    url: str | None = None


@dataclass
class Meta:
    """条目元数据。"""
    title_cn: str | None = None
    title_jp: str | None = None
    title_en: str | None = None
    year: int | None = None
    episodes: int | None = None
    studio: str | None = None
    synopsis: str | None = None
    poster_url: str | None = None


@dataclass
class Rating:
    """原始评分。scale 为该站满分（10 或 100）。"""
    score_raw: float
    scale: float
    count: int


@dataclass
class AnimeReview:
    """单条动漫评论。"""
    text: str
    stars: int | None = None      # 1-5 星；无则 None
    time: str | None = None       # YYYY-MM-DD


@dataclass
class SourceResult:
    """适配器统一返回。status != failed 时 data 可用。"""
    status: Status
    source: str
    data: Any = None
    error: str | None = None
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.status != "failed"


def ok(source: str, data: Any = None) -> SourceResult:
    return SourceResult(status="ok", source=source, data=data)


def degraded(source: str, reason: str, data: Any = None,
             http_status: int | None = None) -> SourceResult:
    """数据可用但质量有损（如走了兜底通道）。"""
    if not reason:
        raise ValueError("degraded 必须说明原因")
    return SourceResult(status="degraded", source=source, data=data,
                        error=reason, http_status=http_status)


def failed(source: str, reason: str, http_status: int | None = None) -> SourceResult:
    """请求失败。reason 必填——禁止用空列表掩盖失败。"""
    if not reason:
        raise ValueError("failed 必须说明原因（禁止用空列表掩盖失败）")
    return SourceResult(status="failed", source=source, error=reason,
                        http_status=http_status)


@runtime_checkable
class SourceAdapter(Protocol):
    """所有站点适配器实现的接口。"""
    source: str

    def search(self, query: str) -> SourceResult: ...
    def fetch_meta(self, source_id: str) -> SourceResult: ...
    def fetch_rating(self, source_id: str) -> SourceResult: ...
    def fetch_reviews(self, source_id: str, limit: int = 200) -> SourceResult: ...
