"""B站番剧适配器。

接口现状（2026-09 实测）：
- pgc/view/web/season  详情 + 评分  → 正常返回 JSON ✅
- pgc/web/timeline     时间表       → 正常返回 JSON ✅
- x/web-interface/search/type  搜索 → **被风控**：HTTP 200 但返回 HTML ❌

因此 search() 在无 cookie 时很可能被拦。适配器对此**如实报失败**，
绝不返回空列表——上层 /anime/search 会把原因记进 errors，其余站点照常工作。
"""
import json
import logging
import re

import requests

from ... import config
from . import register
from .base import (AnimeReview, Candidate, Meta, Rating, SourceResult,
                   degraded, failed, ok)

logger = logging.getLogger("moodreel")

SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
SEASON_API = "https://api.bilibili.com/pgc/view/web/season"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

_TAG = re.compile(r"<[^>]+>")


@register
class BilibiliAdapter:
    source = "bilibili"

    def __init__(self, timeout: int = 15, cookie: str | None = None) -> None:
        self.timeout = timeout
        # cookie 未显式传入时读配置（.env 的 BILIBILI_COOKIE），
        # 便于 get_adapter() 这样无参构造的调用方也能拿到凭证
        self.cookie = config.BILIBILI_COOKIE if cookie is None else cookie

    # —— 网络层：返回 (status_code, text)，异常不外抛 ——
    def _http_get(self, url: str, params: dict | None = None) -> tuple[int, str]:
        headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            r = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            return r.status_code, r.text
        except requests.RequestException as exc:
            logger.warning("B站请求异常 url=%s err=%s", url, exc)
            return 0, str(exc)

    def _get_json(self, url: str, params: dict | None = None):
        """返回 (data, SourceResult|None)；第二项非 None 表示失败。

        B站 风控会返回 HTTP 200 + HTML，所以**不能只看状态码**，必须验内容。
        """
        code, text = self._http_get(url, params)
        if code == 0:
            return None, failed(self.source, f"网络异常：{text}")
        if code != 200:
            return None, failed(self.source, f"HTTP {code}", http_status=code)
        try:
            return json.loads(text), None
        except ValueError:
            return None, failed(
                self.source,
                f"响应非 JSON，疑似被风控拦截（HTTP {code}，"
                f"Content-Type 为 HTML）",
                http_status=code)

    def search(self, query: str) -> SourceResult:
        q = (query or "").strip()
        if not q:
            return ok(self.source, [])
        data, err = self._get_json(
            SEARCH_API, {"search_type": "media_bangumi", "keyword": q})
        if err:
            return err

        items = ((data or {}).get("data") or {}).get("result") or []
        out: list[Candidate] = []
        for it in items:
            sid = it.get("season_id") or it.get("season_id_str")
            if not sid:
                continue
            out.append(Candidate(
                source=self.source,
                source_id=str(sid),
                title_cn=_clean(it.get("title")),
                year=_year_of(it.get("pubtime")),
                episodes=_episodes(it.get("ep_size")),
                url=it.get("url") or f"https://www.bilibili.com/bangumi/play/ss{sid}",
            ))
        return ok(self.source, out)

    def fetch_meta(self, source_id: str) -> SourceResult:
        res, err = self._season(source_id)
        if err:
            return err
        areas = res.get("areas") or []
        return ok(self.source, Meta(
            title_cn=res.get("title"),
            title_jp=res.get("origin_name"),
            year=_year_of((res.get("publish") or {}).get("pub_time")),
            episodes=_episodes(res.get("total")),
            studio=areas[0].get("name") if areas else None,
            synopsis=res.get("evaluate"),
            poster_url=res.get("cover"),
        ))

    def fetch_rating(self, source_id: str) -> SourceResult:
        res, err = self._season(source_id)
        if err:
            return err
        rating = res.get("rating") or {}
        score = rating.get("score")
        if not score:
            return ok(self.source, None)      # 确实无评分（在播新番常见）
        return ok(self.source, Rating(score_raw=float(score), scale=10.0,
                                      count=int(rating.get("count") or 0)))

    def fetch_reviews(self, source_id: str, limit: int = 200) -> SourceResult:
        """短评需登录 cookie（SESSDATA），且接口易被风控。

        未配置 cookie 时降级——评分通道仍可用，不该因此判整个源失败。
        """
        if not self.cookie:
            return degraded(self.source,
                            "未配置 B站 cookie（SESSDATA），短评通道降级", data=[])
        return degraded(self.source, "v1 短评解析待接入", data=[])

    def _season(self, source_id: str):
        """取番剧详情，返回 (result_dict, SourceResult|None)。"""
        data, err = self._get_json(SEASON_API, {"season_id": source_id})
        if err:
            return None, err
        if (data or {}).get("code") not in (0, None):
            return None, failed(
                self.source,
                f"接口返回 code={(data or {}).get('code')}："
                f"{(data or {}).get('message')}")
        res = (data or {}).get("result") or {}
        if not res:
            return None, failed(self.source, "番剧详情为空（可能已下架或 ID 无效）")
        return res, None


def _clean(html: str | None) -> str | None:
    """B站搜索结果的标题带 <em> 高亮标签，需洗掉。"""
    return _TAG.sub("", html).strip() if html else None


def _episodes(value) -> int | None:
    """B站用 -1 表示"连载中/集数未知"，不能当集数存库。"""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _year_of(value) -> int | None:
    """兼容 unix 时间戳与 'YYYY-MM-DD' 两种写法。"""
    if value is None:
        return None
    s = str(value)
    if len(s) >= 10 and s[:10].isdigit():          # unix 时间戳
        import datetime
        return datetime.datetime.fromtimestamp(int(s[:10])).year
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None
