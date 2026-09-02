"""豆瓣短评采集（中文，成员A）。

注意：豆瓣限制严格 —— 控制频率/间隔、必要时带基础 cookie；顺带解析用户星级(1-5)，
供"星标 vs 预测"三方对照演示。样本放入 sample_pack/douban/{movie_id}.csv
"""
from .base import CrawlSource, MovieRef, ReviewItem


class DoubanCrawler(CrawlSource):
    name = "douban"

    def search(self, query: str) -> list[MovieRef]:
        raise NotImplementedError("成员A实现：豆瓣候选影片解析")

    def fetch(self, movie: MovieRef, limit: int = 60) -> list[ReviewItem]:
        raise NotImplementedError("成员A实现：抓取豆瓣短评页并解析星级（含节流重试）")

    def get_sample(self, movie_id: str) -> list[ReviewItem] | None:
        raise NotImplementedError("成员A实现：离线样本加载")
