"""在能打开豆瓣的机器上，抓某部影片的短评 JSON 存为夹具（校准/留档用）。

用法：
    python scripts/dump_douban_json.py --sid 1292052
保存位置：tests/fixtures/douban_interests.json
存在该文件时，pytest 里的 test_parse_real_interests 会自动启用。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许直接运行

from app.crawler.douban import INTERESTS_API, _headers_m, DoubanCrawler, parse_interests  # noqa: E402

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "douban_interests.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True, help="豆瓣 subject id，如 1292052")
    args = ap.parse_args()

    crawler = DoubanCrawler()
    url = INTERESTS_API.format(sid=args.sid, count=20, start=0)
    text = crawler._get(url, _headers_m(args.sid))
    if not text:
        print("[失败] 没有拿到数据（被挡/无网络）。")
        raise SystemExit(1)
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    items = parse_interests(text)
    print(f"[OK] 已保存 {FIXTURE}，解析到 {len(items)} 条真实短评")


if __name__ == "__main__":
    main()
