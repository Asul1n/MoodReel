"""标注一致性校验：Cohen's Kappa + PABAK + 条件 Kappa。

为什么不能只看一个 Kappa：

**Kappa 悖论（prevalence problem）**。ABSA 标注里绝大多数 (评论, 方面) 组合
是"未提及"，即 NA 类别占比常超过 80%。此时即使两名标注者几乎完全一致，
Kappa 也会被压低——因为 pe 被高 prevalence 类别推到很高，分母 1-pe 变小，
微小分歧被放大。反过来，若两人都倾向于标同一个稀有类别，Kappa 也可能虚低。

因此本脚本同时报四个数，论文里应一并给出：

  po      原始一致率。最直观，但不扣除随机一致的基线。
  kappa   Cohen's Kappa。扣除随机一致，但对 prevalence 敏感。
  PABAK   2·po − 1。Byrt 等（1993）提出的 prevalence-adjusted、
          bias-adjusted kappa，在类别极不均衡时是更稳的参考。
  cond.κ  条件 Kappa：只在双方都判为"提及了该方面"的样本上算极性一致性。
          它回答的是"一旦都认为提到了，极性判断是否一致"，与"提没提"
          这个更基础的分歧分开看。

**两类分歧必须分开统计**。ABSA 的误差主要有两个来源：一是"提没提"
（mention detection），二是"提到了但极性相反"（polarity classification）。
合并成一个 Kappa 会把两者混在一起，无法定位标注规范里哪一条没写清。
因此输出里 mention_f1 与 cond.κ 分开报。

用法：
    python -m scripts.compute_kappa \
        --a data/annotation/annotation_test_raterA.csv \
        --b data/annotation/annotation_test_raterB.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.aspects import (  # noqa: E402
    ASPECTS, POLARITY_NA, VALID_POLARITIES, normalize_polarity)

# 论文采用的合格门槛。Landis & Koch 把 0.61-0.80 称为 substantial，
# 0.7 是 NLP 标注里较常见的下限，低于此值应回到规范里改定义再重标。
KAPPA_TARGET = 0.70


def read_annotations(path: Path) -> dict[int, dict]:
    """读取一份标注表，返回 {review_id: 行字典}。"""
    if not path.exists():
        raise SystemExit(f"标注文件不存在：{path}")

    out: dict[int, dict] = {}
    # utf-8-sig 兼容 Excel 另存时写入的 BOM
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            raw_id = (row.get("review_id") or "").strip()
            if not raw_id:
                continue
            try:
                review_id = int(float(raw_id))
            except ValueError:
                raise SystemExit(f"{path.name} 第 {lineno} 行 review_id 非法：{raw_id!r}")
            try:
                row["sent_polarity"] = normalize_polarity(row.get("sent_polarity"))
                for aspect in ASPECTS:
                    col = f"asp_{aspect.key}"
                    row[col] = normalize_polarity(row.get(col))
            except ValueError as exc:
                raise SystemExit(f"{path.name} 第 {lineno} 行（review {review_id}）：{exc}")
            out[review_id] = row
    return out


def cohens_kappa(pairs: list[tuple[str, str]]) -> dict:
    """多类别 Cohen's Kappa。

    kappa = (po − pe) / (1 − pe)，pe 是两人按各自边际分布独立标注时
    期望的偶然一致率。

    pe 接近 1（双方几乎只用一个类别）时 kappa 无定义——分母趋零，结果会
    剧烈震荡。此时返回 kappa=None 并保留 po，由调用方决定如何解读，
    不能拿一个数值上"看起来正常"的 kappa 蒙混过去。
    """
    n = len(pairs)
    if n == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None, "pabak": None}

    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n

    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    classes = set(count_a) | set(count_b)
    pe = sum((count_a.get(c, 0) / n) * (count_b.get(c, 0) / n) for c in classes)

    kappa = None if abs(1.0 - pe) < 1e-12 else (po - pe) / (1.0 - pe)
    return {
        "n": n,
        "po": po,
        "pe": pe,
        "kappa": kappa,
        "pabak": 2.0 * po - 1.0,      # 与 pe 无关的替代指标
    }


def mention_stats(pairs: list[tuple[str, str]]) -> dict:
    """按"是否提及"二分类统计，衡量 mention detection 的质量。

    把极性差异归入"都提及"桶里不算 mention 错误——两人都认为提到了，
    只是评价相反，这是分类分歧而非检测分歧。
    """
    tp = sum(1 for a, b in pairs if a != POLARITY_NA and b != POLARITY_NA)
    fp = sum(1 for a, b in pairs if a != POLARITY_NA and b == POLARITY_NA)
    fn = sum(1 for a, b in pairs if a == POLARITY_NA and b != POLARITY_NA)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1}


def conditional_kappa(pairs: list[tuple[str, str]]) -> dict:
    """只在双方都判为"提及"的样本上算极性 Kappa。

    这是"条件 Kappa"（conditional kappa）：给定两人都注意到了这个方面，
    极性判断的一致程度。分离出来看，才能判断标注规范的问题出在
    "什么算提到了"还是"什么算好评"。
    """
    subset = [(a, b) for a, b in pairs if a != POLARITY_NA and b != POLARITY_NA]
    return cohens_kappa(subset)


def interpret(kappa: float | None) -> str:
    """Landis & Koch（1977）的惯例分级。"""
    if kappa is None:
        return "不可计算"
    k = kappa
    if k < 0.0:
        return "差于随机"
    if k <= 0.20:
        return "轻微"
    if k <= 0.40:
        return "一般"
    if k <= 0.60:
        return "中等"
    if k <= 0.80:
        return "较高"
    return "几乎完全"


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def build_report(a: dict[int, dict], b: dict[int, dict],
                 path_a: Path, path_b: Path) -> tuple[str, list[dict]]:
    """生成 Markdown 报告与分歧明细。"""
    shared = sorted(set(a) & set(b))
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))

    # 未标注（整行全 NA 且 note 为空）视为漏标，不计入一致性计算，
    # 否则漏标会伪装成"两人都认为什么都没提"，人为抬高一致率。
    def is_blank(row: dict) -> bool:
        if row.get("sent_polarity") != POLARITY_NA:
            return False
        if any(row.get(f"asp_{x.key}") != POLARITY_NA for x in ASPECTS):
            return False
        return not (row.get("note") or "").strip()

    blank_a = {rid for rid in shared if is_blank(a[rid])}
    blank_b = {rid for rid in shared if is_blank(b[rid])}
    usable = [rid for rid in shared if rid not in blank_a and rid not in blank_b]

    lines: list[str] = []
    lines.append("# 标注一致性报告")
    lines.append("")
    lines.append(f"- raterA：`{path_a.name}`，{len(a)} 条")
    lines.append(f"- raterB：`{path_b.name}`，{len(b)} 条")
    lines.append(f"- 共同 review_id：{len(shared)} 条"
                 f"（仅 A 有 {len(only_a)}，仅 B 有 {len(only_b)}）")
    if blank_a or blank_b:
        lines.append(f"- 疑似未标注：A {len(blank_a)} 条，B {len(blank_b)} 条，已剔除")
    lines.append(f"- 参与计算：{len(usable)} 条")
    lines.append("")

    if not usable:
        lines.append("**没有可用于计算的样本**，请检查两份文件是否已填写。")
        return "\n".join(lines), []

    disagreements: list[dict] = []

    # —— 整句极性 ——
    sent_pairs = [(a[rid]["sent_polarity"], b[rid]["sent_polarity"]) for rid in usable]
    sent = cohens_kappa(sent_pairs)
    lines.append("## 整句极性")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 样本数 | {sent['n']} |")
    lines.append(f"| 原始一致率 po | {fmt(sent['po'])} |")
    lines.append(f"| Cohen's κ | {fmt(sent['kappa'])} |")
    lines.append(f"| PABAK | {fmt(sent['pabak'])} |")
    lines.append(f"| 一致性等级 | {interpret(sent['kappa'])} |")
    lines.append("")
    for rid in usable:
        pa, pb = a[rid]["sent_polarity"], b[rid]["sent_polarity"]
        if pa != pb:
            disagreements.append({
                "review_id": rid, "scope": "sent", "aspect": "",
                "raterA": pa, "raterB": pb,
                "text": (a[rid].get("text") or "")[:60],
                "note": f"A: {a[rid].get('note') or ''} / B: {b[rid].get('note') or ''}",
            })

    # —— 逐方面 ——
    lines.append("## 逐方面一致性")
    lines.append("")
    lines.append("| 方面 | κ | po | PABAK | 提及率A | 提及率B | mention F1 | 条件 κ | 等级 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    kappas: list[float] = []
    for aspect in ASPECTS:
        col = f"asp_{aspect.key}"
        pairs = [(a[rid][col], b[rid][col]) for rid in usable]
        stat = cohens_kappa(pairs)
        mention = mention_stats(pairs)
        cond = conditional_kappa(pairs)

        rate_a = sum(1 for x, _ in pairs if x != POLARITY_NA) / len(pairs)
        rate_b = sum(1 for _, y in pairs if y != POLARITY_NA) / len(pairs)

        if stat["kappa"] is not None:
            kappas.append(stat["kappa"])

        lines.append(
            f"| {aspect.name_zh}({aspect.key}) | {fmt(stat['kappa'])} "
            f"| {fmt(stat['po'])} | {fmt(stat['pabak'])} "
            f"| {fmt(rate_a, 2)} | {fmt(rate_b, 2)} "
            f"| {fmt(mention['f1'])} | {fmt(cond['kappa'])} "
            f"| {interpret(stat['kappa'])} |")

        for rid in usable:
            pa, pb = a[rid][col], b[rid][col]
            if pa != pb:
                disagreements.append({
                    "review_id": rid, "scope": "aspect",
                    "aspect": aspect.key,
                    "raterA": pa, "raterB": pb,
                    "text": (a[rid].get("text") or "")[:60],
                    "note": f"A: {a[rid].get('note') or ''} / B: {b[rid].get('note') or ''}",
                })

    lines.append("")
    macro = sum(kappas) / len(kappas) if kappas else None
    lines.append(f"**方面 Kappa 宏平均**：{fmt(macro)}（{interpret(macro)}）")
    lines.append("")
    lines.append(f"**论文门槛**：κ ≥ {KAPPA_TARGET:.2f}。"
                 f"当前 {'达标' if macro is not None and macro >= KAPPA_TARGET else '未达标'}。")
    lines.append("")

    # —— 分歧统计 ——
    n_mention = sum(1 for d in disagreements
                    if d["scope"] == "aspect"
                    and (d["raterA"] == POLARITY_NA) != (d["raterB"] == POLARITY_NA))
    n_polarity = len([d for d in disagreements
                      if d["scope"] == "aspect"]) - n_mention
    lines.append("## 分歧构成")
    lines.append("")
    lines.append(f"- 整句极性分歧：{sum(1 for d in disagreements if d['scope'] == 'sent')} 处")
    lines.append(f"- 方面「提没提」分歧（mention）：{n_mention} 处")
    lines.append(f"- 方面「极性相反」分歧（polarity）：{n_polarity} 处")
    lines.append("")
    lines.append("若 mention 分歧显著多于 polarity 分歧，说明规范里"
                 "「什么算提到了该方面」这一条定义不清，应优先修订该条并重标；"
                 "反之则应复核极性的三档边界（尤其「中性/混合」与「负面」之间）。")
    lines.append("")
    lines.append("## 解读提醒")
    lines.append("")
    lines.append("逐方面 Kappa 受 prevalence 影响明显：某个方面若只在少数评论里出现，"
                 "NA 占比极高，Kappa 会被压低而 po 依然很高。此时应同时看 PABAK "
                 "与条件 Kappa，并在论文中一并报告，而不是只挑 Kappa 报。")
    lines.append("")
    return "\n".join(lines), disagreements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="计算两份标注的 Cohen's Kappa")
    parser.add_argument("--a", type=Path, required=True, help="raterA 标注文件")
    parser.add_argument("--b", type=Path, required=True, help="raterB 标注文件")
    parser.add_argument("--out", type=Path, default=None,
                        help="报告输出路径，默认与 raterA 同目录")
    parser.add_argument("--disagreements", type=Path, default=None,
                        help="分歧明细 CSV 输出路径")
    args = parser.parse_args(argv)

    a = read_annotations(args.a)
    b = read_annotations(args.b)
    report, disagreements = build_report(a, b, args.a, args.b)

    out_path = args.out or args.a.parent / "kappa_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"报告已写出：{out_path}")

    if disagreements:
        dis_path = args.disagreements or args.a.parent / "disagreements.csv"
        with dis_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["review_id", "scope", "aspect",
                                "raterA", "raterB", "text", "note"])
            writer.writeheader()
            writer.writerows(sorted(disagreements,
                                    key=lambda d: (d["scope"], d["aspect"], d["review_id"])))
        print(f"分歧明细：{dis_path}（{len(disagreements)} 处）")

    print()
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
