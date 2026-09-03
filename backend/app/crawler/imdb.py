"""IMDB 采集（成员A）——当前不做实时抓取（设计取舍）。

原因：IMDB 反爬/需登录/地域限制，课堂环境拿不到稳定评论。
本系统对 IMDB 使用**公开静态语料**（imdb_static，由 scripts/seed_db.py 灌入 IMDB 50k）
与 sample_pack 离线样本，足以支撑"用 IMDB 影评做情感/热点/可视化"的演示；
如日后需要实时抓取再补充本文件。
"""
from .base import CrawlSource, MovieRef, ReviewItem


class ImdbCrawler(CrawlSource):
    name = "imdb"

    def search(self, query: str) -> list[MovieRef]:
        raise NotImplementedError("IMDB 实时抓取未实现（设计取舍：使用静态语料/离线样本）")

    def fetch(self, movie: MovieRef, limit: int = 60) -> list[ReviewItem]:
        raise NotImplementedError("IMDB 实时抓取未实现（设计取舍：使用静态语料/离线样本）")
