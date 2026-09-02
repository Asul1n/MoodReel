"""建库 + 灌入 IMDB 静态语料（成员A）。

用法：
    python scripts/seed_db.py                 # 全量 50k
    python scripts/seed_db.py --sample 5000   # 快速抽样（联调用）
"""
import argparse
import csv
import sys
from pathlib import Path

# 允许直接 `python scripts/seed_db.py` 运行（把 backend/ 加进模块搜索路径）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "IMDB_Dataset.csv"


def ingest_imdb(db: Session, csv_path: Path, sample: int | None = None) -> int:
    n = 0
    batch: list[models.Review] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if sample and n >= sample:
                break
            batch.append(models.Review(
                source="imdb_static", lang="en", text=row["review"],
                ground_truth=row["sentiment"].strip().lower(),
            ))
            n += 1
            if len(batch) >= 5000:
                db.bulk_save_objects(batch)
                db.commit()
                batch.clear()
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DATA_FILE)
    ap.add_argument("--sample", type=int, default=None)
    args = ap.parse_args()

    init_db()
    if not args.csv.exists():
        print(f"未找到 IMDB 数据文件：{args.csv}，先运行 python scripts/download_imdb.py")
        raise SystemExit(1)

    with SessionLocal() as db:
        n = ingest_imdb(db, args.csv, sample=args.sample)
        total = db.query(models.Review).count()
    print(f"[OK] 本次灌入 {n} 条，reviews 表现有 {total} 条")
    print("下一步：python scripts/train_textcnn.py（成员B 产出模型），随后 uvicorn 启动。")


if __name__ == "__main__":
    main()
