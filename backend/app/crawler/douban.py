"""豆瓣短评采集（中文，成员A）。

网页版短评是 JS 渲染，真实评论走**移动端 rexxar JSON 接口**：
    m.douban.com/rexxar/api/v2/movie/{id}/interests?count=&order_by=hot&start=
每条 interest 含 comment / rating.value / create_time。

反爬能力（可配置、默认低调匿名单会话）：
- **身份池**：.env 的 DOUBAN_COOKIES（每行一个账号 cookie）→ 多会话轮换；
  无 cookie 则匿名（单会话）。
- **代理池**：DOUBAN_PROXIES（每行一个，http://user:pass@ip:port）→ 每次请求随机换。
- **多排序并集去重**：同片按 hot + time 两路拉取，按评论文本去重，提高单次产量。
- **并发**：DOUBAN_WORKERS（默认 1，低调）；多路并发时共享轮换与去重。
- 被拦(403/429/空页) → 指数退避 + 换身份/代理重试。
"""
import json
import logging
import random
import re
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

from .. import config
from .base import CrawlSource, MovieRef, ReviewItem

logger = logging.getLogger("moodreel")

HOME = "https://www.douban.com"
SEARCH_API = "https://movie.douban.com/j/subject_suggest?q={q}"
INTERESTS_API = ("https://m.douban.com/rexxar/api/v2/movie/{sid}/interests?"
                 "count={count}&order_by={order}&start={start}")
MOVIE_DETAIL_API = "https://m.douban.com/rexxar/api/v2/movie/{sid}"

_MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
              "Mobile/15E148 Safari/604.1")
PAGE_SIZE = 20
ORDERS = ("hot", "time")            # 多排序并集：热门 + 最新
MAX_LIMIT = 1000                    # 单次抓取上限（放开到几千量级用分批多次）


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
    """解析 rexxar interests JSON -> 短评列表（正文 + 星级 + 发表时间）。"""
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


# ---------- 真实抓取（身份/代理池 + 并发 + 多排序并集） ----------

class DoubanCrawler(CrawlSource):
    name = "douban"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._spin = 0
        cookies = config.DOUBAN_COOKIES or [None]     # 没配 cookie 就是匿名（单会话）
        self._idents: list[dict] = []
        for ck in cookies:
            s = requests.Session()
            self._prime(s, ck)
            self._idents.append({"session": s, "cookie": ck})
        self._proxies = list(config.DOUBAN_PROXIES)
        logger.info("豆瓣爬虫身份池: %d 个会话, 代理 %d 个, 并发=%d",
                    len(self._idents), len(self._proxies),
                    max(1, int(config.DOUBAN_WORKERS)))

    def _prime(self, session: requests.Session, cookie: str | None) -> None:
        """会话先访问一次主页，拿 bid 等 cookie。"""
        headers = _headers_movie()
        if cookie:
            headers["Cookie"] = cookie
        try:
            session.get(HOME, headers=headers, timeout=8)
        except requests.RequestException:
            pass

    def _pick(self) -> dict:
        """轮换取一个身份（线程安全）。"""
        with self._lock:
            item = self._idents[self._spin % len(self._idents)]
            self._spin += 1
            return item

    def _get(self, url: str, headers: dict, retries: int = 3) -> str | None:
        """带身份/代理轮换的 GET；403/429/异常做指数退避并换身份。"""
        for attempt in range(retries):
            ident = self._pick()
            req_headers = dict(headers)
            if ident["cookie"]:
                req_headers["Cookie"] = ident["cookie"]
            kwargs = {"timeout": 12}
            if self._proxies:
                proxy = random.choice(self._proxies)
                kwargs["proxies"] = {"http": proxy, "https": proxy}
            try:
                r = ident["session"].get(url, headers=req_headers, **kwargs)
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
        limit = max(1, min(int(limit or 200), MAX_LIMIT))
        collected: list[ReviewItem] = []
        seen: set[str] = set()
        lock = threading.Lock()
        done = threading.Event()
        workers = max(1, int(config.DOUBAN_WORKERS))
        logger.info("豆瓣抓取开始 movie=%s 目标 %d 条 (多排序%s, workers=%d)",
                    movie.movie_id, limit, ORDERS, workers)

        def pull(order: str) -> None:
            start = 0
            while not done.is_set():
                if len(collected) >= limit:      # 近似读数，容忍轻微超量后截断
                    done.set()
                    return
                url = INTERESTS_API.format(sid=sid, count=PAGE_SIZE,
                                           order=order, start=start)
                text = self._get(url, _headers_m(sid))
                page = parse_interests(text) if text else []
                if not page:                      # 空页/被拦 -> 换下一路排序
                    logger.warning("豆瓣抓取 movie=%s order=%s start=%d 无数据/被拦，切下一路",
                                   movie.movie_id, order, start)
                    return
                added = 0
                with lock:
                    for it in page:
                        if len(collected) >= limit:
                            break
                        if it.text and it.text not in seen:
                            seen.add(it.text)
                            collected.append(it)
                            added += 1
                    if len(collected) >= limit:
                        done.set()
                logger.info("豆瓣抓取 movie=%s order=%s 累计 %d/%d 条",
                            movie.movie_id, order, min(len(collected), limit), limit)
                if len(page) < PAGE_SIZE or added == 0:   # 到末页 或 全是重复
                    return
                start += PAGE_SIZE
                time.sleep(random.uniform(1.0, 2.5))      # 限速（可配更保守）

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(pull, o) for o in ORDERS]
            while not done.is_set() and not all(f.done() for f in futures):
                time.sleep(0.2)
            done.set()
            for f in futures:                              # 吸收异常，不阻断
                f.cancel()
        return collected[:limit]

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
