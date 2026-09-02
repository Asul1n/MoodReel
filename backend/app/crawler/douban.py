"""豆瓣短评采集（中文，成员A）。

解析基于豆瓣「短评」页结构（div.comment-item / .allstarXX / .short）。
若豆瓣改版导致解析不到，把真实页面存进 tests/fixtures/douban_comments.html，
调整本文件选择器即可（已有解析器单测兜底）。

反爬策略（豆瓣限制较严）：
- 先用一个会话访问 douban.com 主页拿 bid cookie；
- 统一 UA + Accept-Language；
- 页间 2-4s 随机间隔；失败指数退避重试；遇到验证页/异常直接停。
注意：需在**能正常打开豆瓣的机器**上运行（测试/服务器 IP 常被挡，返回验证页）。
"""
import json
import random
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from .base import CrawlSource, MovieRef, ReviewItem

HOME = "https://www.douban.com"
SEARCH_API = "https://movie.douban.com/j/subject_suggest?q={q}"
COMMENTS_TPL = "https://movie.douban.com/subject/{sid}/comments?start={start}&limit=20&sort=new_score"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": HOME,
}
PAGE_SIZE = 20
# 反爬验证页特征
_BLOCK_HINTS = ("检测到有异常请求", "访问豆瓣", "sec.douban.com", "安全验证")
_ALLSTAR_TITLE = {"力荐": 5, "推荐": 4, "还行": 3, "较差": 2, "很差": 1}


# ---------- 无状态解析函数（可脱离网络单测） ----------

def looks_blocked(html: str) -> bool:
    """判断返回是否反爬验证页 / 空页。"""
    h = html or ""
    return (len(h) < 1500) or any(k in h for k in _BLOCK_HINTS)


def parse_subjects(text: str) -> list[MovieRef]:
    """解析 subject_suggest JSON 接口，只保留电影。"""
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


def _stars_of(comment_el) -> int | None:
    """从 .allstarXX class 或 title 提取星级 1-5。"""
    el = comment_el.select_one("span[class*=allstar]")
    if el is not None:
        for cls in (el.get("class") or []):
            m = re.fullmatch(r"allstar([1-5])0", cls)
            if m:
                return int(m.group(1))
        title = (el.get("title") or "").strip()
        if title in _ALLSTAR_TITLE:
            return _ALLSTAR_TITLE[title]
    return None


def _text_of(comment_el) -> str:
    node = (comment_el.select_one("p.comment-content span.short")
            or comment_el.select_one("p.comment-content")
            or comment_el.select_one(".comment-content"))
    return node.get_text(" ", strip=True) if node is not None else ""


def parse_comments(html: str) -> list[ReviewItem]:
    """解析短评页里的 div.comment-item。"""
    soup = BeautifulSoup(html or "", "html.parser")
    items: list[ReviewItem] = []
    for el in soup.select("div.comment-item"):
        text = _text_of(el)
        if not text:
            continue
        items.append(ReviewItem(text=text, stars=_stars_of(el)))
    return items


# ---------- 真实抓取 ----------

class DoubanCrawler(CrawlSource):
    name = "douban"

    def __init__(self) -> None:
        self.session = requests.Session()
        self._primed = False

    def _ensure_session(self) -> None:
        """先用会话访问一次主页，取得 bid 等 cookie（豆瓣要求带 cookie 请求短评页）。"""
        if self._primed:
            return
        try:
            self.session.get(HOME, headers=HEADERS, timeout=8)
        except requests.RequestException:
            pass
        self._primed = True

    def _get(self, url: str) -> str | None:
        """GET 并返回文本；403/429/网络异常做指数退避重试。"""
        self._ensure_session()
        for attempt in range(3):
            try:
                r = self.session.get(url, headers=HEADERS, timeout=10)
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
        # 直接是豆瓣 subject id（纯数字）
        if re.fullmatch(r"\d+", q):
            return [MovieRef(movie_id=f"douban:{q}", title=q, source="douban")]
        # 片名 -> subject_suggest JSON 候选
        url = SEARCH_API.format(q=urllib.parse.quote(q))
        text = self._get(url)
        if not text or looks_blocked(text):
            return []
        return parse_subjects(text)

    def fetch(self, movie: MovieRef, limit: int = 60) -> list[ReviewItem]:
        sid = (movie.movie_id or "").split("douban:")[-1]
        if not sid.isdigit():
            return []
        limit = max(1, min(int(limit or 60), 100))
        fetched: list[ReviewItem] = []
        start = 0
        while len(fetched) < limit:
            html = self._get(COMMENTS_TPL.format(sid=sid, start=start))
            if not html or looks_blocked(html):
                break
            page = parse_comments(html)
            fetched.extend(page)
            if len(page) < PAGE_SIZE:      # 到末页
                break
            start += PAGE_SIZE
            time.sleep(random.uniform(2.0, 4.0))   # 反爬限速
        return fetched[:limit]
