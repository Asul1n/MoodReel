"""数据分析服务：把入库评论加工成前端要的图表数据。

情感口径（全系统唯一）：
    label = COALESCE(pred_label, ground_truth, 豆瓣星级映射)
    - imdb_static 用原文标签（ground_truth）
    - 豆瓣中文评论用用户星级（>=4 正 / 3 中性 / <=2 负）
    - /analyze 补标后走 pred_label（textcnn / tencent）
统一这样取，旧库/离线样本无需重爬也能直接出图。

产出：情感分布、按天趋势、热点词/词云、褒贬倾向词（夸什么/骂什么）。
"""
import re
from collections import Counter

import jieba
from sqlalchemy import case, func, select

from .. import models

EN_STOP = set("""
a an and are as at be but by for from has have he her his i if in is it its like of on one or
our she so that the their them they this to was we were what when which who will with you your
movie film watch see very just not no do does did also there here br get it's dont
""".split())
ZH_STOP = set("""
的 了 是 我 你 他 她 它 我们 你们 他们 这 那 这些 那些 就 都 也 和 与 在 不 没有 没
一 个 电影 这部 一部 片子 里 很 太 比较 真的 自己 什么 怎么 因为 所以 但是 还是
之后 时候 觉得 说 看 会 能 要 有 人 但 而 让
""".split())


# --------------------------------------------------------------------------- #
# 上下文 & 情感口径
# --------------------------------------------------------------------------- #

def _context_movie_id(context: str | None) -> str | None:
    """context: 'whole' | 'movie:douban:1292052' | 直接传 movie_id。"""
    ctx = (context or "whole").strip()
    if ctx in ("", "whole"):
        return None
    if ctx.startswith("movie:"):
        return ctx[len("movie:"):]
    return ctx


def _scope(db, context: str | None):
    mid = _context_movie_id(context)
    return [models.Review.movie_id == mid] if mid else []


def _label_expr():
    """COALESCE(pred_label, ground_truth, 星级映射)。"""
    return case(
        (models.Review.pred_label.isnot(None), models.Review.pred_label),
        (models.Review.ground_truth.isnot(None), models.Review.ground_truth),
        (models.Review.lang == "zh", case(
            (models.Review.stars >= 4, "positive"),
            (models.Review.stars <= 2, "negative"),
            else_=None)),   # 3 星(中性)不派极性 -> 归 unlabeled
        else_=None,
    ).label("label")


# --------------------------------------------------------------------------- #
# 情感分布 / 来源 / 趋势
# --------------------------------------------------------------------------- #

def stats(db, context: str | None = "whole") -> dict:
    conds = _scope(db, context)
    label = _label_expr()
    counts = dict(
        db.execute(select(label, func.count()).where(*conds).group_by(label)).all()
    )
    by_source = dict(
        db.execute(
            select(models.Review.source, func.count()).where(*conds)
            .group_by(models.Review.source)
        ).all()
    )
    # 统一二类口径：positive / negative；中性或未标注一律归 unlabeled
    pos = counts.get("positive", 0)
    neg = counts.get("negative", 0)
    total = sum(counts.values())
    return {
        "context": context or "whole",
        "total": total,
        "labeled": pos + neg,
        "unlabeled": total - pos - neg,
        "dist": {"positive": pos, "negative": neg},
        "by_source": by_source,
    }


def trend(db, context: str | None = "whole", limit_days: int | None = None) -> list[dict]:
    conds = _scope(db, context)
    label = _label_expr()
    # 按月统计（YYYY-MM，横轴"年份-月"）；时间优先取评论原始发表时间，否则回退入库时间
    month = func.strftime("%Y-%m",
                          func.coalesce(models.Review.review_time,
                                        models.Review.created_at))
    rows = db.execute(
        select(month, label, func.count())
        .where(*conds).group_by(month, label)
    ).all()
    by_day: dict[str, dict] = {}
    for day, lab, cnt in rows:
        day = str(day)
        b = by_day.setdefault(day, {"date": day, "total": 0,
                                    "positive": 0, "negative": 0, "neutral": 0})
        b["total"] += cnt
        if lab in b:
            b[lab] += cnt
    items = [by_day[k] for k in sorted(by_day)]
    if limit_days:
        items = items[-limit_days:]
    return items


def movie_info(db, context: str | None = "whole") -> dict | None:
    mid = _context_movie_id(context)
    if not mid:
        return None
    m = db.get(models.Movie, mid)
    if not m:
        return None
    return {"movie_id": m.movie_id, "title": m.title, "year": m.year,
            "source": m.source, "source_url": m.source_url}


# --------------------------------------------------------------------------- #
# 文本分词
# --------------------------------------------------------------------------- #

def _tokens(lang: str, text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if lang == "zh":
        return [w for w in jieba.cut(text)
                if len(w.strip()) >= 2 and w not in ZH_STOP]
    words = re.findall(r"[a-z']+", text.lower())
    return [w for w in words if len(w) >= 3 and w not in EN_STOP]


def _labeled_rows(db, context):
    label = _label_expr()
    return db.execute(
        select(models.Review.text, models.Review.lang, label)
        .where(*_scope(db, context))
    ).all()


# --------------------------------------------------------------------------- #
# 热点词 / 词云 / 褒贬倾向词
# --------------------------------------------------------------------------- #

def hotspot(db, context: str | None = "whole", top_n: int = 30) -> dict:
    top_n = max(1, min(int(top_n or 30), 100))
    all_docs: Counter = Counter()   # 出现该词的评论数（整个上下文）
    pos_docs: Counter = Counter()   # 正评中包含该词的评论数
    neg_docs: Counter = Counter()   # 负评中包含该词的评论数

    rows = _labeled_rows(db, context)
    for text, lang, lab in rows:
        if not text:
            continue
        toks = set(_tokens(lang, text))
        for w in toks:
            all_docs[w] += 1
        if lab == "positive":
            for w in toks:
                pos_docs[w] += 1
        elif lab == "negative":
            for w in toks:
                neg_docs[w] += 1

    keywords = [{"word": w, "weight": c}
                for w, c in all_docs.most_common(top_n)]

    # 褒贬倾向：词在正/负评中的占比差异。weight = 该倾向强度(0.5~1)。
    def polarity(side: str) -> list[dict]:
        out = []
        for w in set(pos_docs) | set(neg_docs):
            p, g = pos_docs.get(w, 0), neg_docs.get(w, 0)
            tot = p + g
            if tot < 2:          # 至少要出现在 2 条评论里，避免单评偶然
                continue
            ratio = p / tot
            if side == "pos" and ratio >= 0.66:
                out.append((w, round(ratio, 3), tot))
            elif side == "neg" and ratio <= 0.34:
                out.append((w, round(1 - ratio, 3), tot))
        out.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return [{"word": w, "weight": wt} for w, wt, _ in out[:top_n]]

    return {
        "context": context or "whole",
        "total_reviews": len(rows),
        "keywords": keywords,
        "cloud": keywords,                     # 词云按 count 缩放即可
        "polarity": {"pos": polarity("pos"), "neg": polarity("neg")},
    }


# --------------------------------------------------------------------------- #
# 分站独有褒贬词（跨站分歧成因归因，规格 §6.5）
# --------------------------------------------------------------------------- #

def build_source_terms(docs: dict, top_n: int = 15) -> dict:
    """各站"独有"的高频褒贬词——直接回答"国内在意什么、国外在意什么"。

    docs: {source: {"pos": [评论文本, ...], "neg": [评论文本, ...]}}
          褒贬标签沿用全系统唯一口径（见模块 docstring）。

    返回: {source: {"top_pos": [{word, freq, score}], "top_neg": [...]}}
          站点数 < 2 时返回 {}——只有一个站时无所谓"独有"。

    与 hotspot 的关系：褒贬判定沿用同一套"词在正/负评中的占比差异"，
    本函数只在其上再加一层"相对其他站的独有性"（别站也常说的词不算独有）。
    """
    sources = [s for s, d in docs.items() if d.get("pos") or d.get("neg")]
    if len(sources) < 2:
        return {}

    # 各站词频（按"包含该词的评论数"计，与 hotspot 口径一致）
    pos_df: dict[str, Counter] = {}
    neg_df: dict[str, Counter] = {}
    all_df: dict[str, Counter] = {}
    for src in sources:
        p, g, a = Counter(), Counter(), Counter()
        for text in docs[src].get("pos") or []:
            for w in set(_tokens(_lang_of(text), text)):
                p[w] += 1
                a[w] += 1
        for text in docs[src].get("neg") or []:
            for w in set(_tokens(_lang_of(text), text)):
                g[w] += 1
                a[w] += 1
        pos_df[src], neg_df[src], all_df[src] = p, g, a

    out: dict[str, dict] = {}
    for src in sources:
        others = Counter()
        for other in sources:
            if other != src:
                others.update(all_df[other])
        n_others = len(sources) - 1

        # 独有度 = 本站文档频率 / (1 + 其他站平均文档频率)
        scores: dict[str, float] = {}
        for w, n in all_df[src].items():
            other_avg = others.get(w, 0) / n_others
            if other_avg > 0 and n <= other_avg:
                continue                     # 别站也这么说 → 不算独有
            scores[w] = n / (1.0 + other_avg)

        def side(kind: str, limit: int) -> list[dict]:
            rows = []
            for w, distinct in scores.items():
                p, g = pos_df[src].get(w, 0), neg_df[src].get(w, 0)
                tot = p + g
                if tot < 2:                  # 同 hotspot：至少 2 条评论才采信
                    continue
                ratio = p / tot
                if kind == "pos" and ratio >= 0.66:
                    rows.append((w, distinct, tot))
                elif kind == "neg" and ratio <= 0.34:
                    rows.append((w, distinct, tot))
            rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
            return [{"word": w, "freq": tot, "score": round(s, 3)}
                    for w, s, tot in rows[:limit]]

        out[src] = {"top_pos": side("pos", top_n), "top_neg": side("neg", top_n)}
    return out


def _lang_of(text: str) -> str:
    """按中文字符占比判断语料语言，供分词选择停用词表。"""
    if not text:
        return "en"
    zh = sum(1 for ch in text if "一" <= ch <= "鿿")
    return "zh" if zh * 2 >= len(text) else "en"


# --------------------------------------------------------------------------- #
# 可视化聚合（App 图表一次拿全）
# --------------------------------------------------------------------------- #

def summary(db, context: str | None = "whole", top_n: int = 30) -> dict:
    st = stats(db, context)
    hs = hotspot(db, context, top_n=top_n)
    conf = db.scalar(
        select(func.avg(models.Review.pred_prob)).where(
            *_scope(db, context), models.Review.pred_prob.isnot(None)
        )
    )
    return {
        "context": context or "whole",
        "movie": movie_info(db, context),
        "total": st["total"],
        "dist": st["dist"],
        "labeled": st["labeled"],
        "unlabeled": st["unlabeled"],
        "by_source": st["by_source"],
        "avg_confidence": round(float(conf), 3) if conf is not None else None,
        "trend": trend(db, context),
        "top_words": hs["keywords"][:10],
        "cloud": hs["cloud"],
        "polarity": hs["polarity"],
        "total_reviews": hs["total_reviews"],
    }
