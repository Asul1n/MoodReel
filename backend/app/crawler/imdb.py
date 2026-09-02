"""IMDB 影评采集（英文，成员A）。

注意：IMDB 反爬较强 —— 必须做随机 UA/间隔/重试；现场不可用时依赖 get_sample 离线兜底。
样本放入 sample_pack/imdb/{movie_id}.csv
"""
from .base import CrawlSource, MovieRef, ReviewItem


class ImdbCrawler(CrawlSource):
    name = "imdb"

    def search(self, query: str) -> list[MovieRef]:
        raise NotImplementedError("成员A实现：IMDB 候选影片解析")

    def fetch(self, movie: MovieRef, limit: int = 60) -> list[ReviewItem]:
        raise NotImplementedError("成员A实现：抓取 IMDB reviews 页并解析（含节流重试）")

    def get_sample(self, movie_id: str) -> list[ReviewItem] | None:
        # 读取 sample_pack/imdb/{movie_id}.csv
        raise NotImplementedError("成员A实现：离线样本加载")
