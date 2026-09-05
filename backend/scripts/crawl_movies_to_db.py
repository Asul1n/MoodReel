"""批量抓取多部影片入库（采集集，供 build_zh_dataset --from-db 攒中文训练数据）。

逐片走 runner 真实抓取（HTML 深翻 + rexxar），reviews.source=douban_live，
带星级与发表时间入库。已抓过的片用 refresh=True 重抓/补齐到窗口上限。

用法：
    python scripts/crawl_movies_to_db.py --limit 250
    python scripts/crawl_movies_to_db.py --limit 250 --start 5   # 从中途某部继续
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models  # noqa: E402
from app.crawler.douban import DoubanCrawler  # noqa: E402
from app.crawler import runner  # noqa: E402
from app.db import SessionLocal  # noqa: E402

# 15 部高热度片 + 5 部偏"负评多"的片（用于平衡正负样本）
MOVIES = [
    "肖申克的救赎", "星际穿越", "千与千寻", "霸王别姬", "让子弹飞",
    "泰坦尼克号", "盗梦空间", "这个杀手不太冷", "楚门的世界", "疯狂动物城",
    "阿甘正传", "活着", "三傻大闹宝莱坞", "无间道", "寻梦环游记",
    "上海堡垒", "富春山居图", "小时代", "爵迹", "无极",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--start", type=int, default=0, help="从第几部开始（断点续跑）")
    ap.add_argument("--movies", nargs="*", default=None, help="自定义片名列表")
    args = ap.parse_args()

    movies = args.movies or MOVIES
    crawler = DoubanCrawler()

    for i, title in enumerate(movies):
        if i < args.start:
            continue
        try:
            refs = crawler.search(title)
            if not refs:
                print(f"[{i+1}/{len(movies)}] 跳过（找不到）{title}")
                continue
            movie = refs[0]
            job_id = None
            with SessionLocal() as db:
                job = models.CrawlJob(job_id=__import__("uuid").uuid4().hex,
                                      source="douban", query=title,
                                      limit=args.limit, refresh=True,
                                      status="pending")
                db.add(job)
                db.commit()
                job_id = job.job_id
            runner._run(job_id)
            with SessionLocal() as db:
                n = db.query(models.Review).filter(
                    models.Review.movie_id == movie.movie_id).count()
                stars = db.query(models.Review).filter(
                    models.Review.movie_id == movie.movie_id,
                    models.Review.stars.isnot(None)).count()
            print(f"[{i+1}/{len(movies)}] {title} ({movie.movie_id}) 评论{n}条/带星{stars}条")
        except Exception as exc:
            print(f"[{i+1}/{len(movies)}] {title} 出错: {exc}")
            time.sleep(3)

    with SessionLocal() as db:
        zh = db.query(models.Review).filter(models.Review.lang == "zh",
                                            models.Review.stars.isnot(None)).count()
    print(f"[OK] 全部完成。库中中文带星影评共 {zh} 条 -> 可跑 build_zh_dataset.py --from-db 生成训练集")


if __name__ == "__main__":
    main()
