"""番剧身份归并测试（规格 §4.1 / §12）。

归并是跨站分析的前提，错了全盘皆错，因此重点覆盖"误合并防护"。
"""
from app.services.adapters.base import Candidate
from app.services.identity import normalize_title, score_match, match_candidates


def test_normalize_strips_noise() -> None:
    assert normalize_title("进击的巨人 第一季") == normalize_title("进击的巨人 第1季")
    assert normalize_title("【TV】进击的巨人") == normalize_title("进击的巨人")
    assert normalize_title("ＡＢＣ") == normalize_title("abc")


def test_match_same_anime_across_sources() -> None:
    """同一部番在两站的标题应判定为同一部（远高于匹配阈值）。"""
    a = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="4450", title_cn="进击的巨人", year=2013)
    assert score_match(a, b) >= 0.85


def test_season_written_differently_still_same() -> None:
    """「第一季」与「第1季」是同一季，不得被季度强判负误伤。"""
    a = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人 第一季", year=2013)
    b = Candidate(source="bilibili", source_id="2", title_cn="进击的巨人 第1季", year=2013)
    assert score_match(a, b) >= 0.85


def test_different_seasons_do_not_merge() -> None:
    """误合并防护：第一季与第二季绝不能并成一部。"""
    a = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="9999", title_cn="进击的巨人 第二季", year=2017)
    assert score_match(a, b) < 0.7


def test_different_anime_do_not_merge() -> None:
    """误合并防护：完全不同的作品。"""
    a = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="2", title_cn="鬼灭之刃", year=2019)
    assert score_match(a, b) < 0.5


def test_year_mismatch_lowers_score() -> None:
    a = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="2", title_cn="进击的巨人", year=2020)
    assert score_match(a, b) < score_match(a, Candidate(
        source="bilibili", source_id="3", title_cn="进击的巨人", year=2013))


def test_match_candidates_picks_best_above_threshold() -> None:
    anchor = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    pool = [
        Candidate(source="bilibili", source_id="4450", title_cn="进击的巨人", year=2013),
        Candidate(source="bilibili", source_id="9999", title_cn="进击的巨人 第二季", year=2017),
        Candidate(source="bilibili", source_id="8888", title_cn="鬼灭之刃", year=2019),
    ]
    best = match_candidates(anchor, pool, threshold=0.7)
    assert best is not None
    assert best.source_id == "4450"


def test_match_candidates_returns_none_when_all_below_threshold() -> None:
    anchor = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    pool = [Candidate(source="bilibili", source_id="2", title_cn="鬼灭之刃", year=2019)]
    assert match_candidates(anchor, pool, threshold=0.7) is None
