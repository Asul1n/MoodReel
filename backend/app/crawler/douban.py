"""豆瓣短评采集（中文，成员A）。

豆瓣网页版短评是 JS 渲染，直接 GET 只会拿到"载入中…"空壳；真实评论走**移动端
rexxar JSON 接口**：
    m.douban.com/rexxar/api/v2/movie/{id}/interests?count=&order_by=hot&start=
每条 interest 含 comment（正文）与 rating.value（星级 1-5）。

流程：
- search：subject_suggest JSON（片名 → 候选电影；也接受豆瓣纯数字 id）
- fetch ：rexxar interests 分页抓取 comment + 星级

反爬策略（豆瓣限制较严）：
- 会话先访问 douban.com 拿 bid cookie；
- iPhone UA + 对应 Referer；
- 分页间 1-2s 随机间隔、失败指数退避。
注意：需在**能打开豆瓣的机器**上运行；返回非 JSON/无数据时按空处理（runner 会离线兜底）。
"""
import json
import logging
import random
import re
import time
import urllib.parse

import requests

from .base import CrawlSource, MovieRef, ReviewItem

logger = logging.getLogger("moodreel")

HOME = "https://www.douban.com"
SEARCH_API = "https://movie.douban.com/j/subject_suggest?q={q}"
INTERESTS_API = ("https://m.douban.com/rexxar/api/v2/movie/{sid}/interests?"
                 "count={count}&order_by=hot&start={start}")
MOVIE_DETAIL_API = "https://m.douban.com/rexxar/api/v2/movie/{sid}"

_MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
              "Mobile/15E148 Safari/604.1")
PAGE_SIZE = 20


def _headers_movie() -> dict:
    return {"User-Agent": _MOBILE_UA, "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://movie.douban.com/"}


def _headers_m(sid: str) -> dict:
    return {"User-Agent": _MOBILE_UA, "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"https://m.douban.com/movie/subject/{sid}/"}


# ---------- 无状态解析函数（可脱离网络单测） ----------

def parse_subjects(text: str) -> list[MovieRef]:
    """解析 subject_suggest JSON，只保留电影。"""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out: list[MovieRef] = []
    for it in data or []:
        if it.get("subtype") not in (None, "movie"):
            continue
        sid = str(it.get("id", "")).strip()
        if not sid:
            continue
        year = it.get("year")
        try:
            year = int(year) if year not in (None, "") else None
        except (TypeError, ValueError):
            year = None
        title = str(it.get("title") or sid)
        out.append(MovieRef(
            movie_id=f"douban:{sid}", title=title, source="douban", year=year,
            source_url=f"https://movie.douban.com/subject/{sid}/",
        ))
    return out


def parse_interests(text: str) -> list[ReviewItem]:
    """解析 rexxar interests JSON -> 短评列表（正文 + 星级，可为空）。"""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out: list[ReviewItem] = []
    for it in (data or {}).get("interests") or []:
        comment = (it.get("comment") or "").strip()
        if not comment:
            continue
        stars: int | None = None
        rating = it.get("rating")
        if isinstance(rating, dict):
            try:
                stars = int(rating.get("value"))
            except (TypeError, ValueError):
                stars = None
        created = (it.get("create_time") or "").strip()
        created_date = created[:10] if created else None   # YYYY-MM-DD
        out.append(ReviewItem(text=comment, stars=stars, time=created_date))
    return out


def _to_int_year(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def parse_movie_detail(text: str) -> dict:
    """解析 rexxar 影片详情 -> 元数据（供前端简介页）。"""
    d = json.loads(text or "{}")
    rating = d.get("rating") or {}
    pic = d.get("pic") or {}
    directors = [x.get("name", "") for x in (d.get("directors") or []) if x.get("name")]
    return {
        "title": d.get("title"),
        "year": _to_int_year(d.get("year")),
        "intro": (d.get("intro") or "").strip(),
        "poster": (pic.get("large") or pic.get("normal") or None),
        "rating": float(rating["value"]) if rating.get("value") is not None else None,
        "genres": " / ".join(d.get("genres") or []),
        "directors": " / ".join(directors),
    }


# ---------- 真实抓取 ----------

class DoubanCrawler(CrawlSource):
    name = "douban"

    def __init__(self) -> None:
        self.session = requests.Session()
        self._primed = False

    def _ensure_session(self) -> None:
        """会话先访问一次主页，取得 bid cookie（豆瓣多数接口要求）。"""
        if self._primed:
            return
        try:
            self.session.get(HOME, headers=_headers_movie(), timeout=8)
        except requests.RequestException:
            pass
        self._primed = True

    def _get(self, url: str, headers: dict) -> str | None:
        """GET 返回文本；403/429/网络异常做指数退避重试。"""
        self._ensure_session()
        for attempt in range(3):
            try:
                r = self.session.get(url, headers=headers, timeout=12)
                if r.status_code == 200:
                    return r.text
                if r.status_code in (403, 429):
                    time.sleep(2 * (attempt + 1) + random.random() * 2)
                    continue
                return None
            except requests.RequestException:
                time.sleep(2 * (attempt + 1))
        return None

    def search(self, query: str) -> list[MovieRef]:
        q = (query or "").strip()
        if not q:
            return []
        if re.fullmatch(r"\d+", q):   # 直接是豆瓣 subject id
            return [MovieRef(movie_id=f"douban:{q}", title=q, source="douban")]
        url = SEARCH_API.format(q=urllib.parse.quote(q))
        text = self._get(url, _headers_movie())
        return parse_subjects(text) if text else []

    def fetch(self, movie: MovieRef, limit: int = 200) -> list[ReviewItem]:
        sid = (movie.movie_id or "").split("douban:")[-1]
        if not sid.isdigit():
            return []
        limit = max(1, min(int(limit or 200), 200))
        fetched: list[ReviewItem] = []
        start = 0
        logger.info("豆瓣抓取开始 movie=%s 目标 %d 条", movie.movie_id, limit)
        while len(fetched) < limit:
            url = INTERESTS_API.format(sid=sid, count=PAGE_SIZE, start=start)
            text = self._get(url, _headers_m(sid))
            page = parse_interests(text) if text else []
            if not page:              # 空/被挡
                logger.warning("豆瓣抓取 movie=%s 第 %d 页为空/被反爬拦截，提前结束",
                               movie.movie_id, start // PAGE_SIZE + 1)
                break
            fetched.extend(page)
            logger.info("豆瓣抓取 movie=%s 翻页进度 %d/%d 条",
                        movie.movie_id, min(len(fetched), limit), limit)
            if len(page) < PAGE_SIZE:  # 到末页
                logger.info("豆瓣抓取 movie=%s 已到末页", movie.movie_id)
                break
            start += PAGE_SIZE
            time.sleep(random.uniform(1.0, 2.0))   # 反爬限速
        return fetched[:limit]

    def movie_meta(self, movie: MovieRef) -> dict | None:
        """抓取影片简介/海报/评分等元数据（失败返回 None，不强依赖）。"""
        sid = (movie.movie_id or "").split("douban:")[-1]
        if not sid.isdigit():
            return None
        text = self._get(MOVIE_DETAIL_API.format(sid=sid), _headers_m(sid))
        if not text:
            return None
        try:
            return parse_movie_detail(text)
        except Exception:
            return None
