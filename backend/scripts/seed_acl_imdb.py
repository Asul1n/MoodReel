"""从 aclImdb 原始目录灌 IMDB 静态语料进 reviews（source=imdb_static）。

aclImdb 结构（队友训练 TextCNN 用的就是它）：
    aclImdb/train/pos/*.txt  (12500)   train/neg/*.txt (12500)
    aclImdb/test/pos/*.txt   (12500)   test/neg/*.txt  (12500)

用法：
    python scripts/seed_acl_imdb.py --root /path/to/aclImdb
    python scripts/seed_acl_imdb.py --root /path/to/aclImdb --sample 2000   # 快速抽样联调

灌入后即可测英文整库分析：/dataset/stats?context=whole 等。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 允许直接运行

from app import models  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402

SPLITS = ("train", "test")
LABELS = ("pos", "neg")


def collect(root: Path, sample: int | None = None) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for split in SPLITS:
        for label in LABELS:
            folder = root / split / label
            if not folder.exists():
                continue
            files = sorted(folder.glob("*.txt"))
            n = len(files)
            for f in files:
                texts.append((f.read_text(encoding="utf-8", errors="ignore"),
                              "positive" if label == "pos" else "negative"))
                if sample and len(texts) >= sample:
                    return texts
    print(f"收集到 {len(texts)} 条（期望 50000）")
    return texts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path, help="aclImdb 根目录")
    ap.add_argument("--sample", type=int, default=None, help="抽样条数（联调用）")
    ap.add_argument("--force", action="store_true", help="清空已有 imdb_static 再灌")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        exist = db.query(models.Review).filter(
            models.Review.source == "imdb_static").count()
        if exist and not args.force:
            print(f"已有 imdb_static {exist} 条，跳过。用 --force 可清空重灌。")
            raise SystemExit(0)
        if args.force and exist:
            db.query(models.Review).filter(
                models.Review.source == "imdb_static").delete()
            db.commit()

        texts = collect(args.root, args.sample)
        rows = [models.Review(source="imdb_static", lang="en",
                              text=t, ground_truth=lab) for t, lab in texts]
        batch = []
        for r in rows:
            batch.append(r)
            if len(batch) >= 5000:
                db.bulk_save_objects(batch)
                db.commit()
                batch.clear()
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
        total = db.query(models.Review).filter(
            models.Review.source == "imdb_static").count()
    print(f"[OK] 灌入 {len(rows)} 条，现 imdb_static 共 {total} 条")
    print("测试英文整库：/dataset/stats?context=whole 、/hotspot?context=whole 、/viz/summary?context=whole")


if __name__ == "__main__":
    main()
