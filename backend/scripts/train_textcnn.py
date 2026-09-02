"""训练 TextCNN + 评测 + 导出（成员B）。

目标（规格 §7）：
- 留存测试集准确率 >= 85%（脚本内置断言，失败即退出非 0）
- 导出 models/vocab.json + models/textcnn.npz，供 app/services/textcnn.py 加载

模型结构约定（与线上一致）：
  Embedding(100d, vocab=15k, pad=256) -> conv[3,4,5]x128 -> 1-max pool
  -> concat -> dropout(0.5) -> Linear -> softmax(2)

注意：线上 tokenizer 与本脚本必须是同一份代码（建议把分词抽到 backend/app/tokenizer.py 共用）。
用法：
    python scripts/train_textcnn.py --csv data/IMDB_Dataset.csv --epochs 3
"""
import argparse
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "IMDB_Dataset.csv"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DATA_FILE)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--vocab-size", type=int, default=15000)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"未找到数据文件：{args.csv}，先运行 python scripts/download_imdb.py")
        raise SystemExit(1)

    # TODO(成员B)：实现
    #  1) 加载 CSV -> 切分 train/val/test
    #  2) 分词 -> 建词表(复用 backend/app/tokenizer.py) -> 向量化
    #  3) 构建并训练 TextCNN（CPU 即可，建议 3 epoch 起步）
    #  4) 测试集评测，断言 accuracy >= 0.85
    #  5) 导出 MODEL_DIR/vocab.json 与 textcnn.npz
    raise NotImplementedError("成员B实现训练主流程")


if __name__ == "__main__":
    main()
