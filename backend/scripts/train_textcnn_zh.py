"""训练中文情感 TextCNN（豆瓣星标弱标签，二分类 positive/negative）。

数据：data/zh_train.csv（text,label，由 scripts/build_zh_dataset.py 生成）
结构：与英文 TextCNN 同构（embed 100 + conv[3,4,5]×100 + 池化 + fc），jieba 分词。
产物：models/zh/model_zh.pt  {model, config, vocab}

用法：
    python scripts/train_textcnn_zh.py --csv data/zh_train.csv --epochs 8 --max_len 200
"""
import argparse
import csv
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.model_runtime.zh_kernel import TextCNN, build_vocab, encode_zh  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "models" / "zh"


def load_csv(path: Path):
    texts, labels = [], []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = (row.get("text") or "").strip()
            lab = (row.get("label") or "").strip().lower()
            if t and lab in ("positive", "negative"):
                texts.append(t)
                labels.append(1 if lab == "positive" else 0)
    return texts, labels


class DS(Dataset):
    def __init__(self, texts, labels, vocab, max_len):
        self.data = [torch.tensor(encode_zh(t, vocab, max_len), dtype=torch.long) for t in texts]
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        return self.data[i], self.labels[i]


def evaluate(model, loader, device):
    model.eval()
    total = correct = 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            pred = model(x).argmax(1)
            total += y.size(0)
            correct += (pred == y).sum().item()
    return correct / total if total else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=Path("data/zh_train.csv"))
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--max_len", type=int, default=200)
    ap.add_argument("--vocab_size", type=int, default=30000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=5e-4)
    args = ap.parse_args()
    if not args.csv.exists():
        print(f"未找到 {args.csv}，先运行 scripts/build_zh_dataset.py")
        raise SystemExit(1)

    texts, labels = load_csv(args.csv)
    n = len(texts)
    if n == 0:
        raise SystemExit("训练集为空")
    idx = list(range(n))
    random.Random(42).shuffle(idx)
    texts = [texts[i] for i in idx]
    labels = [labels[i] for i in idx]
    split = max(1, int(n * 0.9))
    tr_t, te_t = texts[:split], texts[split:]
    tr_l, te_l = labels[:split], labels[split:]

    vocab = build_vocab(tr_t, args.vocab_size)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfg = {"embed_dim": 100, "num_filters": 100, "filter_sizes": [3, 4, 5],
           "dropout": 0.5, "max_len": args.max_len}
    model = TextCNN(vocab_size=len(vocab), embed_dim=cfg["embed_dim"],
                    num_filters=cfg["num_filters"], filter_sizes=cfg["filter_sizes"],
                    num_classes=2, dropout=cfg["dropout"]).to(device)
    crit = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    train_dl = DataLoader(DS(tr_t, tr_l, vocab, args.max_len), batch_size=args.batch, shuffle=True)
    val_dl = DataLoader(DS(te_t, te_l, vocab, args.max_len), batch_size=args.batch)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    best = 0.0
    print(f"样本 {n}（train {len(tr_t)} / val {len(te_t)}）词表 {len(vocab)} device {device}")
    for ep in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = crit(model(x), y)
            loss.backward()
            opt.step()
        acc = evaluate(model, val_dl, device)
        print(f"  epoch {ep}: val_acc={acc:.4f}  ({time.time()-t0:.0f}s)")
        if acc > best:
            best = acc
            torch.save({"model": model.state_dict(), "config": cfg, "vocab": vocab},
                       OUT_DIR / "model_zh.pt")
    print(f"[OK] 最佳 val_acc={best:.4f} 模型 -> {OUT_DIR / 'model_zh.pt'}")


if __name__ == "__main__":
    main()
