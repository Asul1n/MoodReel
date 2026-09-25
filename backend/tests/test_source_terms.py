"""分站独有褒贬词归因测试（规格 §6.5）。

复用 analytics.hotspot 的既有语义：褒贬由"词在正/负评中的占比差异"判定，
而非静态词表；此处再加一层"相对其他站的独有性"。
"""
from app.services.analytics import build_source_terms


def _docs() -> dict:
    return {
        # bangumi：夸作画、骂节奏
        "bangumi": {
            "pos": ["作画精良 分镜出色"] * 10,
            "neg": ["节奏拖沓 剧情注水"] * 6,
        },
        # bilibili：夸打斗、骂崩坏
        "bilibili": {
            "pos": ["打斗精彩 燃到爆"] * 10,
            "neg": ["作画崩坏 崩坏严重"] * 6,
        },
    }


def test_finds_site_specific_terms() -> None:
    out = build_source_terms(_docs(), top_n=5)
    assert "bangumi" in out and "bilibili" in out

    bgm_pos = [t["word"] for t in out["bangumi"]["top_pos"]]
    bili_pos = [t["word"] for t in out["bilibili"]["top_pos"]]

    # B站独有的"打斗"不应出现在 bangumi 的独有词里
    assert any("打斗" in w for w in bili_pos)
    assert not any("打斗" in w for w in bgm_pos)


def test_pos_and_neg_are_separated() -> None:
    """褒贬必须分开：夸的进 top_pos，骂的进 top_neg。

    注意 jieba 会把"作画精良"切成 ['作画','精良']，断言须针对切分后的词。
    """
    out = build_source_terms(_docs(), top_n=5)
    bgm_pos = [t["word"] for t in out["bangumi"]["top_pos"]]
    bgm_neg = [t["word"] for t in out["bangumi"]["top_neg"]]
    assert {"作画", "精良", "分镜"} & set(bgm_pos)          # 夸作画/分镜
    assert {"节奏", "拖沓", "注水"} & set(bgm_neg)          # 骂节奏/注水


def test_empty_input_returns_empty() -> None:
    assert build_source_terms({}, top_n=5) == {}


def test_single_source_returns_empty_terms() -> None:
    """只有一个站时没有"独有"可言，返回空而非误导性结果。"""
    out = build_source_terms({"bangumi": {"pos": ["好看 好看"] * 5, "neg": []}}, top_n=5)
    assert out == {}


def test_shared_words_are_not_reported_as_distinctive() -> None:
    """两站都说的词不算任一站的"独有"。"""
    docs = {
        "bangumi": {"pos": ["神作 好看"] * 10, "neg": ["一般"] * 3},
        "bilibili": {"pos": ["神作 精彩"] * 10, "neg": ["一般"] * 3},
    }
    out = build_source_terms(docs, top_n=5)
    for src in ("bangumi", "bilibili"):
        words = [t["word"] for t in out.get(src, {}).get("top_pos", [])]
        assert "神作" not in words
