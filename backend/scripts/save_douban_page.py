"""在本机抓一部豆瓣影片的短评首页，存为真实页面夹具（校准解析用）。

用法（在能正常打开豆瓣的机器上）：
    python scripts/save_douban_page.py --sid 1292052
保存位置：tests/fixtures/douban_comments.html
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许直接运行

from app.crawler.douban import COMMENTS_TPL, DoubanCrawler, looks_blocked, parse_comments  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "douban_comments.html"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True, help="豆瓣 subject id，如 1292052（肖申克的救赎）")
    args = ap.parse_args()

    crawler = DoubanCrawler()
    html = crawler._get(COMMENTS_TPL.format(sid=args.sid, start=0))
    if not html or looks_blocked(html):
        print("[失败] 返回的是验证页/空页，说明本机网络或豆瓣反爬拦截，无法保存真实页面。")
        raise SystemExit(1)

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(html, encoding="utf-8")
    items = parse_comments(html)
    print(f"[OK] 已保存 {FIXTURE}")
    print(f"[OK] 首页解析到 {len(items)} 条短评（供 test_parse_real_douban_page 使用）")
    if not items:
        print("[提示] 解析到 0 条：豆瓣页面结构可能已改版，把该文件发我，我更新选择器。")


if __name__ == "__main__":
    main()
