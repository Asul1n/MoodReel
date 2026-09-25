"""番剧身份归并：把各站条目对齐到同一部番（规格 §4.1）。

v1 策略：标题归一化 + 年份 + 集数加权匹配。
站间官方 ID 映射（AniList 的 idMal 等）与人工校正表留待后续阶段。

设计取向：宁可漏合并（返回 None），不可误合并——把两部不同的番并成一部，
会让整份跨站分歧结论全盘错误，且从结果上很难发现。
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .adapters.base import Candidate

# 季度/期数标记：参与匹配会误伤（"第二季" ≠ 同季），需单独抽取后比对
_SEASON_PAT = re.compile(
    r"第\s*[0-9一二三四五六七八九十]+\s*[季期部]"
    r"|\bseason\s*\d+\b"
    r"|\b\d+(st|nd|rd|th)\s+season\b",
    re.IGNORECASE,
)
# 标点与括号：中日英混排时噪声大，统一剔成空格
_NOISE_PAT = re.compile(r"[【】\[\]（）()《》<>「」『』·・:：!！?？,，.。、~～\-—_/\\|]")
# 媒介标记：同作品不同媒介（TV/剧场版）不应混为一谈
_TV_PAT = re.compile(r"\b(tv|ova|ona|oad|movie)\b|剧场版", re.IGNORECASE)


# 中文数字 → 阿拉伯数字：各站写法不一（"第一季" / "第1季"），必须归一
# 多字组合先替换，否则"十一"会被拆成"101"
_CN_MULTI = [("十一", "11"), ("十二", "12"), ("十三", "13"), ("十四", "14"),
             ("十五", "15"), ("十六", "16"), ("十七", "17"), ("十八", "18"),
             ("十九", "19"), ("二十", "20"), ("十", "10")]
_CN_SINGLE = {"一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
              "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}


def _num_normalize(s: str) -> str:
    for cn, ar in _CN_MULTI:
        s = s.replace(cn, ar)
    for cn, ar in _CN_SINGLE.items():
        s = s.replace(cn, ar)
    return s


def normalize_title(title: str | None) -> str:
    """归一化标题：去噪声、统一全半角/大小写/中文数字、压空白。"""
    if not title:
        return ""
    s = unicodedata.normalize("NFKC", str(title)).lower()
    s = _num_normalize(s)
    s = _NOISE_PAT.sub(" ", s)
    s = _TV_PAT.sub(" ", s)
    s = re.sub(r"\s+", "", s)          # 中日文无词间空格，去掉便于比较
    return s


def _season_of(title: str | None) -> str:
    """抽取季度标记，用于区分不同季。先做数字归一，"第一季"与"第1季"视为同季。"""
    if not title:
        return ""
    s = _num_normalize(unicodedata.normalize("NFKC", str(title)))
    m = _SEASON_PAT.search(s)
    return re.sub(r"\s+", "", m.group(0).lower()) if m else ""


def _title_similarity(a: Candidate, b: Candidate) -> float:
    """取各语言标题两两相似度的最大值。"""
    best = 0.0
    for ta in (a.title_cn, a.title_jp, a.title_en):
        for tb in (b.title_cn, b.title_jp, b.title_en):
            na, nb = normalize_title(ta), normalize_title(tb)
            if not na or not nb:
                continue
            sim = 1.0 if na == nb else SequenceMatcher(None, na, nb).ratio()
            best = max(best, sim)
    return best


def score_match(a: Candidate, b: Candidate) -> float:
    """两条候选属于同一部番的置信度 ∈ [0, 1]。"""
    sim = _title_similarity(a, b)
    if sim == 0.0:
        return 0.0

    # 季度标记不同 → 强判负，防止把第二季并进第一季
    sa = _season_of(a.title_cn or a.title_jp or a.title_en)
    sb = _season_of(b.title_cn or b.title_jp or b.title_en)
    if sa != sb:
        return min(sim, 0.3)

    score = sim * 0.7

    # 年份：一致加分，差异大减分
    if a.year and b.year:
        diff = abs(a.year - b.year)
        if diff == 0:
            score += 0.2
        elif diff == 1:
            score += 0.1
        else:
            score -= 0.2

    # 集数一致小幅加分
    if a.episodes and b.episodes and a.episodes == b.episodes:
        score += 0.1

    return max(0.0, min(1.0, score))


def match_candidates(anchor: Candidate, pool: list[Candidate],
                     threshold: float = 0.7) -> Candidate | None:
    """从 pool 中挑出与 anchor 最匹配且超过阈值的一条；都不够则 None。"""
    best: Candidate | None = None
    best_score = 0.0
    for cand in pool:
        if cand.source == anchor.source and cand.source_id == anchor.source_id:
            continue
        s = score_match(anchor, cand)
        if s > best_score:
            best, best_score = cand, s
    return best if best_score >= threshold else None
