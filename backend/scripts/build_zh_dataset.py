"""从豆瓣星标影评构建中文情感训练集（A 方案数据层）。

两种来源：
- `--from-db`：用库里已抓的豆瓣评论（lang=zh 且有星级）——快速/零网络。
- 默认：按片名列表用真实爬虫抓取（网络，攒十几部片）。需配好 DOUBAN_COOKIES。

星级映射：>=4 -> positive；<=2 -> negative；3 / 无星 丢弃。按评论文本去重。

用法：
    python scripts/build_zh_dataset.py --from-db            # 快速验证
    python scripts/build_zh_dataset.py --append             # 追加爬取结果
    python scripts/build_zh_dataset.py --limit 300
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 预置常见高热度中文片（可自行增删）
MOVIES = [
    "肖申克的救赎", "星际穿越", "千与千寻", "霸王别姬", "让子弹飞",
    "泰坦尼克号", "盗梦空间", "这个杀手不太冷", "楚门的世界", "疯狂动物城",
    "阿甘正传", "活着", "三傻大闹宝莱坞", "无间道", "寻梦环游记",
]

OUT = Path(__file__).resolve().parent.parent / "data" / "zh_train.csv"


def _label(stars: int | None) -> str | None:
    if stars is None:
        return None
    if stars >= 4:
        return "positive"
    if stars <= 2:
        return "negative"
    return None  # 3 星 = 中性，弃


def from_db() -> list[tuple[str, str]]:
    from app import models
    from app.db import SessionLocal

    rows: list[tuple[str, str]] = []
    with SessionLocal() as db:
        for text, stars in db.query(models.Review.text, models.Review.stars).filter(
                models.Review.lang == "zh",
                models.Review.text.isnot(None),
        ).all():
            lab = _label(stars)
            if text and lab:
                rows.append((text, lab))
    return rows


def crawl_all(limit: int) -> list[tuple[str, str]]:
    from app.crawler.base import MovieRef
    from app.crawler.douban import DoubanCrawler

    crawler = DoubanCrawler()
    rows: list[tuple[str, str]] = []
    for title in MOVIES:
        try:
            refs = crawler.search(title)
            if not refs:
                print(f"  [跳过] 找不到 {title}")
                continue
            movie = refs[0]
            items = crawler.fetch(movie, limit=limit)
            got = 0
            for it in items:
                lab = _label(it.stars)
                if lab:
                    rows.append((it.text, lab))
                    got += 1
            print(f"  {title} 抓取 {len(items)} 条，可标注 {got} 条")
        except Exception as exc:
            print(f"  [出错] {title}: {exc}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-db", action="store_true", help="用库里已抓的星级影评（零网络）")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--append", action="store_true", help="追加到已有 CSV")
    args = ap.parse_args()

    rows = from_db() if args.from_db else crawl_all(args.limit)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    uniq: list[tuple[str, str]] = []
    for text, lab in rows:
        if text not in seen:
            seen.add(text)
            uniq.append((text, lab))

    mode = "a" if args.append else "w"
    write_header = not (args.append and OUT.exists())
    with OUT.open(mode, encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["text", "label"])
        for text, lab in uniq:
            w.writerow([text, lab])
    from collections import Counter
    print(f"[OK] 新增 {len(uniq)} 条 -> {OUT}  分布={dict(Counter(l for _, l in uniq))}")


if __name__ == "__main__":
    main()
