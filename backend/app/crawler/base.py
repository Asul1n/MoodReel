"""采集抽象（成员A）。

约定：
- 每个数据源实现一个 CrawlSource 子类（IMDB / 豆瓣），可插拔、可加新源。
- 抓取礼仪：随机 UA、请求间隔、超时 + 指数退避重试；单任务默认 <=60-100 条。
- 兜底：get_sample() 命中 sample_pack 离线样本则返回，实时失败时路由降级。
"""
from dataclasses import dataclass


@dataclass
class MovieRef:
    movie_id: str
    title: str
    source: str
    year: int | None = None
    source_url: str | None = None


@dataclass
class ReviewItem:
    text: str
    stars: int | None = None  # 豆瓣 1-5；IMDB 无则 None


class CrawlSource:
    name = "base"

    def search(self, query: str) -> list[MovieRef]:
        """按片名/编号解析候选影片。"""
        raise NotImplementedError

    def fetch(self, movie: MovieRef, limit: int = 60) -> list[ReviewItem]:
        """抓取该片影评（含节流与重试）。"""
        raise NotImplementedError

    def get_sample(self, movie_id: str) -> list[ReviewItem] | None:
        """离线兜底：命中 sample_pack 返回样本，否则 None。"""
        return None
