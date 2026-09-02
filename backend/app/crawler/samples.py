"""sample_pack 离线样本加载器（成员A）。

目录约定：
    sample_pack/manifest.json               影片目录
    sample_pack/{source}/{key}.csv          样本影评
        imdb    csv 头：text,sentiment（sentiment 可选 positive/negative）
        douban  csv 头：text,stars（1-5）

离线样本的作用是"兜底"：现场断网 / 目标站反爬时也能走通采集→分析→可视化。
"""
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .base import MovieRef, ReviewItem

SAMPLE_ROOT = Path(__file__).resolve().parent / "sample_pack"


@dataclass
class SampleMovie:
    movie_id: str   # 形如 imdb:tt0111161 / douban:1292052
    title: str
    source: str     # imdb / douban
    key: str        # 文件 key，如 tt0111161
    year: int | None = None
    note: str = ""

    def to_movie_ref(self) -> MovieRef:
        return MovieRef(
            movie_id=self.movie_id, title=self.title,
            source=self.source, year=self.year,
        )


def _manifest_path() -> Path:
    return SAMPLE_ROOT / "manifest.json"


def list_sample_movies() -> list[SampleMovie]:
    """返回 manifest 中登记的所有影片（供 /crawl/movies 选片）。"""
    p = _manifest_path()
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [SampleMovie(**m) for m in data]


def find_movie(source: str, query: str) -> SampleMovie | None:
    """按 source + 片名/编号/文件key 匹配离线影片。"""
    q = (query or "").strip().lower()
    for m in list_sample_movies():
        if m.source != source:
            continue
        if q and any(q in s for s in (m.movie_id.lower(), m.title.lower(), m.key.lower())):
            return m
    return None


def load_sample(movie: SampleMovie) -> list[ReviewItem]:
    """读取某部影片的离线样本影评（空/缺文件返回空列表）。"""
    p = SAMPLE_ROOT / movie.source / f"{movie.key}.csv"
    if not p.exists():
        return []
    items: list[ReviewItem] = []
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            stars: int | None = None
            if row.get("stars"):
                try:
                    stars = int(row["stars"].strip())
                except ValueError:
                    stars = None
            items.append(ReviewItem(text=text, stars=stars))
    return items
