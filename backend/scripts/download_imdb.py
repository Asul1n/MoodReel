"""下载/放置 IMDB 50k 影评数据集（成员A）。

源：https://www.kaggle.com/datasets/lakshmi25npathi/imdb-dataset-of-50k-movie-reviews
CSV 需两列：review, sentiment（positive/negative，各 25k）。

用法：
    python scripts/download_imdb.py [--csv /path/to/IMDB_Dataset.csv]

Kaggle 需登录下载，故不在脚本内自动抓取。可手动下载后：
    mkdir -p data && mv IMDB_Dataset.csv data/IMDB_Dataset.csv
本脚本会校验列结构并给出提示。
"""
import argparse
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPECTED = Path(__file__).resolve().parent.parent / "data" / "IMDB_Dataset.csv"


def validate(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or [h.lower().strip() for h in header] != ["review", "sentiment"]:
            raise SystemExit(f"列结构不符：应依次为 review, sentiment，实际 {header}")
        n = sum(1 for _ in reader)
    print(f"[OK] {path} 共 {n} 条影评")
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=None)
    args = ap.parse_args()

    DATA_DIR.mkdir(exist_ok=True)
    src = args.csv or EXPECTED
    if not src.exists():
        print(f"未找到数据文件：{src}")
        print("请从 Kaggle 下载 IMDB_Dataset.csv 放到 backend/data/ 目录后重跑，或用 --csv 指定路径。")
        raise SystemExit(1)
    n = validate(src)
    if n != 50000:
        print(f"[警告] 期望 50000 条，实际 {n} 条")
    if args.csv:
        print(f"建议：mv {args.csv} {EXPECTED}")


if __name__ == "__main__":
    main()
