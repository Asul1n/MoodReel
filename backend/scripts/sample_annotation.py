"""标注集分层抽样：从真实影评库抽出可复现的 train / test 切片。

设计要点（论文方法与附录都需引用）：

1. **分层维度是星级，不是影片**。星级是唯一与情感极性高度相关、且在库里
   完整可用的先验标签；影片维度上做分层会让"上海堡垒"这类低分片被过度
   采样，训练集的情感先验被污染。层内再用按影片轮转（round-robin）
   抽，避免某部高评论量的片子占满整层。

2. **train / test 在同一层内切分，不做整层切**。若整层切分，测试集与
   训练集的星级分布会不同，评估指标无法与随机基线比较。

3. **测试集盲标两份**（raterA / raterB）。两份文件内容完全相同、都不含
   任何人的标注结果，第二标注者看不到第一人的答案，Cohen's Kappa 才有
   意义。若共用一份文件互相参考，得到的是"协商后的一致性"，不是
   "独立判断的一致性"，不能作为标注质量证据。

4. **不做模型预标注**。预标注能把工作量减半，但会引入锚定偏差
   （anchoring bias）：标注者倾向于接受屏幕上已有的答案，测出的一致性
   会虚高，且这个偏差无法从数据里事后扣除。300 条的量级不值得用
   数据可信度去换。

5. **全流程只依赖 seed 与库快照**。同 seed + 同库 → 同一批样本，
   论文附录记录 seed 即可复现。

用法：
    python -m scripts.sample_annotation                    # 默认 300 条
    python -m scripts.sample_annotation --dry-run          # 只看分层统计
    python -m scripts.sample_annotation --total 400 --test-size 80
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# 允许以 `python scripts/sample_annotation.py` 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.aspects import ASPECT_KEYS  # noqa: E402

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "moodreel.db"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "annotation"

# 表头顺序即人工填表时的阅读顺序：先看原文，再判整句，最后逐方面。
BASE_COLUMNS = [
    "review_id", "movie_id", "movie_title", "stars", "review_time", "text",
    "sent_polarity",
]
ASPECT_COLUMNS = [f"asp_{k}" for k in ASPECT_KEYS]
TAIL_COLUMNS = ["evidence", "note", "annotator"]
COLUMNS = BASE_COLUMNS + ASPECT_COLUMNS + TAIL_COLUMNS


def load_rows(db_path: Path, *, min_len: int,
              exclude_ids: set[str] | None = None) -> list[dict]:
    """读取候选池。过滤条件在 SQL 里做，减少内存与后续误用。

    exclude_ids 用于剔除经人工确认不属于研究对象的条目。库里混入了
    动画剧集、特摄剧与游戏条目（抓取按关键词匹配，豆瓣会把剧集一并返回），
    而 ABSA 的方面体系是按电影设计的（"节奏"在剧集里指单集还是整体、
    "剧情"的评价单位是季还是部，都与电影不同）。是否剔除取决于研究口径，
    不做自动判断——按片名猜"是不是电影"会引入主观错误。
    """
    if not db_path.exists():
        raise SystemExit(f"数据库不存在：{db_path}")

    # 只读打开，避免脚本误改生产库
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            """
            SELECT r.id AS review_id, r.movie_id, m.title AS movie_title,
                   r.stars, r.review_time, r.text, r.source, m.genres
            FROM reviews r
            LEFT JOIN movies m ON m.movie_id = r.movie_id
            WHERE r.stars IS NOT NULL
              AND r.anime_id IS NULL
              AND LENGTH(TRIM(r.text)) >= ?
            ORDER BY r.id
            """,
            (min_len,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    finally:
        con.close()

    if exclude_ids:
        rows = [r for r in rows if r["movie_id"] not in exclude_ids]
    return rows


def allocate(total: int, counts: dict[int, int]) -> dict[int, int]:
    """按各层存量比例分配配额，用最大余数法处理取整误差。

    直接四舍五入会让各层配额之和偏离 total，最大余数法保证总和严格
    相等且偏差不超过 1。余数相同时按星级升序分配，保证结果确定。
    """
    pool = sum(counts.values())
    if total > pool:
        raise SystemExit(
            f"可抽样本只有 {pool} 条，不足 {total} 条；请调低 --total 或 --min-len")

    raw = {k: total * v / pool for k, v in counts.items()}
    quota = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(quota.values())

    # 余数大者优先；余数并列时星级升序，保证确定性
    order = sorted(raw, key=lambda k: (-(raw[k] - quota[k]), k))
    for key in order[:remainder]:
        quota[key] += 1
    return quota


def round_robin_pick(rows: list[dict], k: int, rng: random.Random) -> list[dict]:
    """层内按影片轮转抽 k 条，保证样本横跨多部影片。

    单纯随机抽会在评论量大的影片上聚集（"星际穿越"单部就有 173 条），
    导致训练集实际只覆盖少数几部片，模型学到的是"这几部片的措辞"。
    轮转抽让每部片贡献的数量尽量均衡。
    """
    if k <= 0:
        return []
    if k >= len(rows):
        picked = list(rows)
        rng.shuffle(picked)
        return picked

    by_movie: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_movie[row["movie_id"]].append(row)

    movie_ids = sorted(by_movie)
    rng.shuffle(movie_ids)                 # 影片出场顺序也随机，避免固定偏好
    for mid in movie_ids:
        rng.shuffle(by_movie[mid])

    picked: list[dict] = []
    while len(picked) < k:
        progressed = False
        for mid in movie_ids:
            bucket = by_movie[mid]
            if not bucket:
                continue
            picked.append(bucket.pop())
            progressed = True
            if len(picked) >= k:
                break
        if not progressed:                 # 候选池已抽空
            break
    return picked


def stratify(rows: list[dict], total: int, test_size: int,
             rng: random.Random) -> tuple[list[dict], list[dict], dict]:
    """分层抽样并切分 train / test，返回 (train_rows, test_rows, stats)。

    同一层内先抽 train_k + test_k 条，再随机切分——这样两层样本来自同一
    分布，且不会重叠。
    """
    by_star: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        by_star[int(row["stars"])].append(row)

    counts = {k: len(v) for k, v in sorted(by_star.items())}
    # total 是标注总量（train + test），train 配额要先扣掉测试集。
    # 两层各自按同一份 counts 分配，保证星级分布在 train / test 上一致。
    total_quota = allocate(total - test_size, counts)
    test_quota = allocate(test_size, counts)

    train_rows: list[dict] = []
    test_rows: list[dict] = []
    stats: dict[str, dict] = {}

    for star in sorted(by_star):
        need = total_quota.get(star, 0) + test_quota.get(star, 0)
        picked = round_robin_pick(by_star[star], need, rng)
        n_test = min(test_quota.get(star, 0), len(picked))
        rng.shuffle(picked)
        star_test = picked[:n_test]
        star_train = picked[n_test:]

        train_rows.extend(star_train)
        test_rows.extend(star_test)
        stats[str(star)] = {
            "available": counts[star],
            "quota_total": total_quota.get(star, 0),
            "quota_test": test_quota.get(star, 0),
            "taken_train": len(star_train),
            "taken_test": len(star_test),
        }

    return train_rows, test_rows, stats


def write_sheet(path: Path, rows: list[dict]) -> None:
    """写出空白标注表。utf-8-sig 让 Excel 直接双击打开不乱码——
    GBK 环境下这是标注同学最容易卡住的地方。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r["review_id"]):
            out = {col: "" for col in COLUMNS}
            for col in ("review_id", "movie_id", "movie_title",
                        "stars", "review_time", "text"):
                value = row.get(col)
                out[col] = "" if value is None else value
            # 证据列给出格式提示，避免标注者自由发挥导致后续解析失败
            out["evidence"] = ""
            writer.writerow(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="从影评库分层抽样生成 ABSA 标注表")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--total", type=int, default=300,
                        help="标注总量（train + test），默认 300")
    parser.add_argument("--test-size", type=int, default=60,
                        help="测试集条数（双人盲标），默认 60")
    parser.add_argument("--min-len", type=int, default=20,
                        help="最短字符数，默认 20；过短的评论无法承载方面信息")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--exclude-ids", default="",
                        help="逗号分隔的 movie_id，经人工确认后剔除（如动画剧集）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印分层统计，不写文件")
    args = parser.parse_args(argv)

    if args.test_size >= args.total:
        raise SystemExit("--test-size 必须小于 --total")
    if args.test_size < 30:
        raise SystemExit("测试集少于 30 条时 Kappa 与 P/R/F1 的区间过宽，建议 ≥50")

    exclude_ids = {x.strip() for x in args.exclude_ids.split(",") if x.strip()}
    rows = load_rows(args.db, min_len=args.min_len, exclude_ids=exclude_ids)
    if not rows:
        raise SystemExit("候选池为空，检查 --min-len 或数据库路径")

    rng = random.Random(args.seed)
    train_rows, test_rows, stats = stratify(
        rows, args.total, args.test_size, rng)

    print(f"候选池：{len(rows)} 条（星级非空、长度 ≥ {args.min_len}）")
    print(f"分层抽样：train {len(train_rows)} + test {len(test_rows)}"
          f" = {len(train_rows) + len(test_rows)}，seed={args.seed}")
    print(f"{'星级':<6}{'存量':>8}{'train':>8}{'test':>8}")
    for star, s in stats.items():
        print(f"{star:<6}{s['available']:>8}{s['taken_train']:>8}{s['taken_test']:>8}")

    covered = {r["movie_id"] for r in train_rows + test_rows}
    print(f"覆盖影片：{len(covered)} 部")
    if exclude_ids:
        print(f"已排除：{len(exclude_ids)} 个 movie_id")

    # 库里混有动画剧集/特摄剧，类型标签里带「动画」的条目数超过电影数时，
    # 论文的研究对象表述应改为「影视条目」而非「电影」。这里只提示，不阻断。
    anime_titles = {r["movie_title"] for r in train_rows + test_rows
                    if r.get("genres") and "动画" in r["genres"]}
    if anime_titles:
        print(f"提示：样本含 {len(anime_titles)} 部动画类条目"
              f"（部分为剧集而非电影），研究口径见 docs/6_标注规范与一致性校验.md §2.1")

    if args.dry_run:
        print("（dry-run，未写文件）")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    train_path = args.out / "annotation_train.csv"
    test_a_path = args.out / "annotation_test_raterA.csv"
    test_b_path = args.out / "annotation_test_raterB.csv"

    write_sheet(train_path, train_rows)
    write_sheet(test_a_path, test_rows)
    write_sheet(test_b_path, test_rows)      # 内容相同，供第二人独立盲标

    meta = {
        "seed": args.seed,
        "db": str(args.db),
        "total": args.total,
        "test_size": args.test_size,
        "min_len": args.min_len,
        "exclude_ids": sorted(exclude_ids),
        "train_count": len(train_rows),
        "test_count": len(test_rows),
        "aspects": list(ASPECT_KEYS),
        "strata": stats,
        "train_review_ids": sorted(r["review_id"] for r in train_rows),
        "test_review_ids": sorted(r["review_id"] for r in test_rows),
    }
    (args.out / "sample_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"已写出：{train_path}")
    print(f"        {test_a_path}")
    print(f"        {test_b_path}")
    print(f"        {args.out / 'sample_meta.json'}")
    print()
    print("填写方式见 docs/6_标注规范与一致性校验.md。")
    print("raterA / raterB 两份必须由两人各自独立完成，不得互相参考。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
