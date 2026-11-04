"""标注体系与一致性校验测试（`app/services/aspects.py` + 两个脚本）。

关注三件事：
  1. 方面体系的编码/解析可往返，非法输入立刻报错而不是被静默吞掉
  2. Kappa 在可手算的构造数据上取到理论值，且 PABAK / 条件 Kappa 的
     分工正确（这两者是为对抗 prevalence 问题而存在的）
  3. 抽样脚本的分层配额与 train/test 切分满足论文口径（不重叠、分布一致）
"""
import csv
import random

import pytest

from app.services.aspects import (ASPECT_KEYS, POLARITY_NA, POLARITY_NEG,
                                  POLARITY_POS, aspects_of, format_evidence,
                                  get_aspect, normalize_polarity, parse_evidence)
from scripts.compute_kappa import (cohens_kappa, conditional_kappa,
                                   interpret, mention_stats)
from scripts.sample_annotation import allocate, round_robin_pick, stratify

# ======================= 方面体系 =======================


def test_aspect_keys_are_stable() -> None:
    """列顺序变化会破坏已有标注文件与导出表的对应关系，锁死这 6 项。"""
    assert ASPECT_KEYS == ("plot", "act", "vis", "pace", "music", "theme")


def test_get_aspect_raises_on_unknown_key() -> None:
    with pytest.raises(KeyError):
        get_aspect("actin")


def test_normalize_polarity_accepts_common_variants() -> None:
    """Excel 会把 +1 存成 1，中文输入法会打出全角加号，都要能吃下。"""
    for raw in ("+", "+1", "1", "pos", "正面", "好评", "＋"):
        assert normalize_polarity(raw) == POLARITY_POS
    for raw in ("-", "-1", "neg", "负面", "－"):
        assert normalize_polarity(raw) == POLARITY_NEG
    for raw in ("", None, "NA", "无", "未提及"):
        assert normalize_polarity(raw) == POLARITY_NA


def test_normalize_polarity_rejects_garbage() -> None:
    """拼错必须报错——静默当成 NA 会让标注错误伪装成「未提及」。"""
    with pytest.raises(ValueError):
        normalize_polarity("好评+")


def test_evidence_roundtrip() -> None:
    spans = {"act": "演得真好", "plot": "剧情稀碎"}
    encoded = format_evidence(spans)
    assert parse_evidence(encoded) == spans


def test_evidence_replaces_structural_chars() -> None:
    """片段里的分号/冒号会破坏编码结构，写入前应被替换成全角。"""
    encoded = format_evidence({"plot": "前半段;后半段:乱"})
    assert ";" not in encoded.split(":", 1)[1]
    assert parse_evidence(encoded) == {"plot": "前半段；后半段：乱"}


def test_parse_evidence_skips_malformed_chunks() -> None:
    """一个格式小错不该让整批数据作废。"""
    parsed = parse_evidence("act:好;乱写;plot:")
    assert parsed == {"act": "好"}


def test_aspects_of_drops_na() -> None:
    row = {"asp_plot": "+", "asp_act": "NA", "asp_theme": "-"}
    assert aspects_of(row) == {"plot": "+", "theme": "-"}


# ======================= Cohen's Kappa =======================


def test_kappa_perfect_agreement_is_one() -> None:
    pairs = [("+", "+"), ("-", "-"), ("0", "0"), (POLARITY_NA, POLARITY_NA)] * 10
    stat = cohens_kappa(pairs)
    assert stat["kappa"] == pytest.approx(1.0)
    assert stat["po"] == pytest.approx(1.0)


def test_kappa_matches_hand_computed_value() -> None:
    """构造 100 条：A/B 各 85 个 +、15 个 -，一致 90 条。

    po = 0.90，pe = 0.85² + 0.15² = 0.745
    kappa = (0.90 − 0.745) / (1 − 0.745) = 0.6078…
    """
    pairs = ([("+", "+")] * 80 + [("-", "-")] * 10
             + [("+", "-")] * 5 + [("-", "+")] * 5)
    stat = cohens_kappa(pairs)
    assert stat["po"] == pytest.approx(0.90)
    assert stat["pe"] == pytest.approx(0.745)
    assert stat["kappa"] == pytest.approx(0.155 / 0.255, abs=1e-9)


def test_pabak_stays_high_when_kappa_is_pulled_down_by_prevalence() -> None:
    """这就是 Kappa 悖论：90 条都判「未提及」且一致，10 条都提及但极性相反。

    A 的分布是 NA:0.9 / +:0.1，B 是 NA:0.9 / -:0.1，两者只有 NA 类重合，
    因此 pe = 0.9 × 0.9 = 0.81。
    kappa = (0.90 − 0.81) / (1 − 0.81) = 0.4737
    PABAK = 2 × 0.90 − 1 = 0.80

    两人在 90% 的条目上完全一致，Kappa 只报「中等」；PABAK 不受
    prevalence 影响，更接近直觉。论文里两个都要报，不能只挑一个。
    """
    pairs = [(POLARITY_NA, POLARITY_NA)] * 90 + [("+", "-")] * 10
    stat = cohens_kappa(pairs)
    assert stat["po"] == pytest.approx(0.90)
    assert stat["pe"] == pytest.approx(0.81)
    assert stat["kappa"] == pytest.approx(0.09 / 0.19, abs=1e-9)
    assert stat["pabak"] == pytest.approx(0.80)
    assert stat["pabak"] > stat["kappa"]


def test_kappa_returns_none_when_pe_is_one() -> None:
    """双方都只用一个类别时 kappa 无定义，必须返回 None 而不是 0 或 1。"""
    stat = cohens_kappa([("+", "+")] * 20)
    assert stat["kappa"] is None
    assert stat["po"] == pytest.approx(1.0)


def test_kappa_empty_input() -> None:
    stat = cohens_kappa([])
    assert stat["n"] == 0 and stat["kappa"] is None


def test_mention_stats_separates_detection_from_polarity() -> None:
    """两人都提及但极性相反，不算 mention 错误。"""
    pairs = [("+", "-"), ("+", "+"), ("-", POLARITY_NA), (POLARITY_NA, "-")]
    stat = mention_stats(pairs)
    assert (stat["tp"], stat["fp"], stat["fn"]) == (2, 1, 1)
    assert stat["precision"] == pytest.approx(2 / 3)
    assert stat["recall"] == pytest.approx(2 / 3)


def test_conditional_kappa_ignores_na_rows() -> None:
    """条件 Kappa 只看双方都提及的样本，极性完全一致时应该接近 1。"""
    pairs = [("+", "+"), ("-", "-"), ("+", "+")] + [(POLARITY_NA, "-")] * 30
    stat = conditional_kappa(pairs)
    assert stat["n"] == 3
    assert stat["kappa"] == pytest.approx(1.0)


def test_interpret_thresholds() -> None:
    assert interpret(0.85) == "几乎完全"
    assert interpret(0.65) == "较高"
    assert interpret(0.10) == "轻微"
    assert interpret(None) == "不可计算"


# ======================= 分层抽样 =======================


def test_allocate_keeps_total_exact() -> None:
    """最大余数法：各层配额之和必须严格等于 target，不能多也不能少。"""
    counts = {1: 724, 2: 453, 3: 796, 4: 1209, 5: 1832}
    quota = allocate(240, counts)
    assert sum(quota.values()) == 240
    # 按比例，5 星最多、2 星最少
    assert quota[5] > quota[4] > quota[1] > quota[2]


def test_allocate_raises_when_pool_too_small() -> None:
    with pytest.raises(SystemExit):
        allocate(500, {1: 10, 2: 10})


def test_round_robin_spreads_across_movies() -> None:
    """某部片评论量极大时，轮转抽不应让它占满样本。"""
    rows = [{"movie_id": "a", "id": i} for i in range(50)]
    rows += [{"movie_id": "b", "id": 100 + i} for i in range(2)]
    picked = round_robin_pick(rows, 10, __import__("random").Random(0))
    movies = {r["movie_id"] for r in picked}
    assert movies == {"a", "b"}
    assert len(picked) == 10


def _fake_rows() -> list[dict]:
    rows = []
    rid = 1
    for star, n in ((1, 20), (2, 20), (3, 40), (4, 40), (5, 60)):
        for i in range(n):
            rows.append({"review_id": rid, "movie_id": f"m{i % 5}",
                         "movie_title": "t", "stars": star,
                         "review_time": "2024-01-01", "text": "x" * 30})
            rid += 1
    return rows


def test_stratify_splits_without_overlap() -> None:
    import random
    rows = _fake_rows()
    train, test, stats = stratify(rows, 60, 20, random.Random(1))
    assert len(train) == 40
    assert len(test) == 20
    assert not ({r["review_id"] for r in train} & {r["review_id"] for r in test})
    # 每个星级都应有测试样本
    assert all(s["taken_test"] > 0 for s in stats.values())


def test_stratify_preserves_star_distribution() -> None:
    """train 与 test 的星级占比应接近——否则评估指标与基线不可比。"""
    import random
    rows = _fake_rows()
    train, test, _ = stratify(rows, 60, 20, random.Random(7))
    from collections import Counter
    train_share = Counter(r["stars"] for r in train)
    test_share = Counter(r["stars"] for r in test)
    for star in train_share:
        diff = abs(train_share[star] / len(train) - test_share[star] / len(test))
        assert diff < 0.15, f"星级 {star} 的分布偏差过大：{diff:.2f}"


def test_sample_script_is_reproducible(tmp_path) -> None:
    """同 seed 两次抽样必须得到同一批 review_id，这是论文附录的要求。"""
    import json
    import random
    rows = _fake_rows()
    train1, test1, _ = stratify(rows, 60, 20, random.Random(42))
    train2, test2, _ = stratify(rows, 60, 20, random.Random(42))
    assert [r["review_id"] for r in train1] == [r["review_id"] for r in train2]
    assert [r["review_id"] for r in test1] == [r["review_id"] for r in test2]


def test_write_sheet_has_expected_columns(tmp_path) -> None:
    from scripts.sample_annotation import COLUMNS, write_sheet
    path = tmp_path / "sheet.csv"
    write_sheet(path, _fake_rows()[:3])
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == COLUMNS
        assert len(list(reader)) == 3
