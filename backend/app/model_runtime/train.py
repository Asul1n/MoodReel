# -*- coding: utf-8 -*-
"""
基于 TextCNN 的 IMDb 影评情感极性分类（二分类：pos / neg）。

数据：E:\\aclImdb（标准 IMDb 数据集）
    train/pos  12500 条, train/neg  12500 条
    test/pos   12500 条, test/neg   12500 条
    train/unsup 50000 条（无标签，本脚本忽略）

用法：
    训练：  python train.py
    预测：  python train.py --predict "This movie is absolutely wonderful!"
    指定 epoch / 批大小等：  python train.py --epochs 8 --batch_size 128

产物（默认输出到 ./output/）：
    model.pt      训练好的 TextCNN 权重 + 超参
    vocab.json    词表（word -> id）
    history.json  每个 epoch 的 loss / 准确率等指标
"""

import argparse
import json
import os
import random
import re
import time
from collections import Counter

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
CONFIG = {
    "data_dir": "E:/aclImdb",   # 数据根目录，可改成你自己的路径
    "max_vocab": 30000,         # 词表大小（按词频取 top N）
    "max_len": 200,             # 每条评论截断/补齐到该长度
    "embed_dim": 100,           # 词向量维度
    "num_filters": 100,         # 每种卷积核的数量
    "filter_sizes": [3, 4, 5],  # 卷积核窗口大小
    "dropout": 0.5,
    "batch_size": 64,
    "epochs": 10,
    "lr": 5e-4,
    "seed": 42,
    "output_dir": "output",
    # 预训练 GloVe 词向量：加载后作为初始化。
    # glove_freeze=False 时微调词向量（non-static，更准），True 时冻结（static）。
    "glove_path": "E:/glove/glove.6B.100d.txt",
    "glove_embed_dim": 100,
    "glove_freeze": False,
}

PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"
PAD_IDX = 0
UNK_IDX = 1


# --------------------------------------------------------------------------- #
# 文本预处理
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> list[str]:
    """英文分词：去 HTML 标签 -> 小写 -> 保留字母和撇号。"""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-zA-Z']+", " ", text.lower())
    return text.split()


def load_reviews(root: str, split: str, label: str) -> list[str]:
    """读取某个目录（如 train/pos）下的所有 .txt 文件内容。"""
    folder = os.path.join(root, split, label)
    texts = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            texts.append(f.read())
    return texts


def build_vocab(texts: list[str], max_vocab: int) -> dict[str, int]:
    """按词频构建词表，保留 top (max_vocab-2) 个词，加上 <pad> 和 <unk>。"""
    counter = Counter()
    for t in texts:
        counter.update(tokenize(t))
    vocab = {PAD_TOKEN: PAD_IDX, UNK_TOKEN: UNK_IDX}
    for word, _ in counter.most_common(max_vocab - 2):
        vocab[word] = len(vocab)
    return vocab


def encode(text: str, vocab: dict[str, int], max_len: int) -> list[int]:
    """把一条文本编码成固定长度的 id 序列（截断 / pad）。"""
    ids = [vocab.get(w, UNK_IDX) for w in tokenize(text)]
    if len(ids) > max_len:
        ids = ids[:max_len]
    else:
        ids = ids + [PAD_IDX] * (max_len - len(ids))
    return ids


# --------------------------------------------------------------------------- #
# 数据集
# --------------------------------------------------------------------------- #
class IMDBDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], vocab: dict[str, int], max_len: int):
        self.vocab = vocab
        self.max_len = max_len
        self.labels = labels
        self.data = [encode(t, vocab, max_len) for t in texts]

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return torch.tensor(self.data[idx], dtype=torch.long), torch.tensor(self.labels[idx], dtype=torch.long)


# --------------------------------------------------------------------------- #
# TextCNN 模型（Yoon Kim, 2014）
# --------------------------------------------------------------------------- #
class TextCNN(nn.Module):
    def __init__(self, vocab_size: int, embed_dim: int, num_filters: int,
                 filter_sizes: list[int], num_classes: int, dropout: float,
                 pad_idx: int = PAD_IDX, pretrained_embed: torch.Tensor | None = None,
                 freeze_embed: bool = False):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_idx)
        if pretrained_embed is not None:
            self.embedding.weight.data.copy_(pretrained_embed)
            if freeze_embed:
                self.embedding.weight.requires_grad = False  # 冻结预训练词向量

        # 每种窗口大小一个二维卷积：kernel = (窗口, embed_dim)，输出通道 = num_filters
        self.convs = nn.ModuleList([
            nn.Conv2d(1, num_filters, (fs, embed_dim)) for fs in filter_sizes
        ])
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(len(filter_sizes) * num_filters, num_classes)

    def forward(self, x):
        # x: [batch, seq_len]
        x = self.embedding(x)                # [batch, seq_len, embed_dim]
        x = x.unsqueeze(1)                   # [batch, 1, seq_len, embed_dim]
        pooled = []
        for conv in self.convs:
            out = F.relu(conv(x))            # [batch, num_filters, seq_len-fs+1, 1]
            out = out.squeeze(3)             # [batch, num_filters, seq_len-fs+1]
            out = F.max_pool1d(out, out.size(2))  # max-over-time -> [batch, num_filters, 1]
            pooled.append(out.squeeze(2))    # [batch, num_filters]
        x = torch.cat(pooled, dim=1)         # [batch, len(filter_sizes) * num_filters]
        x = self.dropout(x)
        return self.fc(x)


# --------------------------------------------------------------------------- #
# 评估
# --------------------------------------------------------------------------- #
def evaluate(model, loader, device):
    model.eval()
    total, correct = 0, 0
    tp = fp = tn = fn = 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            pred = logits.argmax(1)
            total += y.size(0)
            correct += (pred == y).sum().item()
            tp += ((pred == 1) & (y == 1)).sum().item()
            fp += ((pred == 1) & (y == 0)).sum().item()
            tn += ((pred == 0) & (y == 0)).sum().item()
            fn += ((pred == 0) & (y == 1)).sum().item()
    acc = correct / total
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return acc, precision, recall, f1


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    args = parse_args()
    cfg = dict(CONFIG)
    if args.data_dir:
        cfg["data_dir"] = args.data_dir
    for k in ("batch_size", "epochs", "max_len", "max_vocab", "embed_dim", "num_filters", "lr"):
        v = getattr(args, k)
        if v is not None:
            cfg[k] = v

    set_seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(cfg["output_dir"], exist_ok=True)

    print("=" * 64)
    print(f"数据目录: {cfg['data_dir']}   设备: {device}")
    print(f"超参: { {k: cfg[k] for k in ('max_vocab','max_len','embed_dim','num_filters','filter_sizes','batch_size','epochs','lr','dropout')} }")

    # ---------- 1. 读取数据 ----------
    print("\n[1/4] 读取数据 ...")
    t0 = time.time()
    train_pos = load_reviews(cfg["data_dir"], "train", "pos")
    train_neg = load_reviews(cfg["data_dir"], "train", "neg")
    test_pos = load_reviews(cfg["data_dir"], "test", "pos")
    test_neg = load_reviews(cfg["data_dir"], "test", "neg")
    print(f"  train: {len(train_pos)} pos / {len(train_neg)} neg    "
          f"test: {len(test_pos)} pos / {len(test_neg)} neg   ({(time.time()-t0):.1f}s)")

    train_texts = train_pos + train_neg
    train_labels = [1] * len(train_pos) + [0] * len(train_neg)
    test_texts = test_pos + test_neg
    test_labels = [1] * len(test_pos) + [0] * len(test_neg)

    # ---------- 2. 构建词表 & 编码 ----------
    print("[2/4] 构建词表 ...")
    vocab = build_vocab(train_texts, cfg["max_vocab"])
    print(f"  词表大小: {len(vocab)}")
    with open(os.path.join(cfg["output_dir"], "vocab.json"), "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False)

    train_ds = IMDBDataset(train_texts, train_labels, vocab, cfg["max_len"])
    test_ds = IMDBDataset(test_texts, test_labels, vocab, cfg["max_len"])
    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=cfg["batch_size"], shuffle=False)

    # ---------- 3. 构建模型 ----------
    print("[3/4] 构建模型 ...")
    pretrained = load_glove(cfg, vocab)
    model = TextCNN(
        vocab_size=len(vocab),
        embed_dim=cfg["embed_dim"],
        num_filters=cfg["num_filters"],
        filter_sizes=cfg["filter_sizes"],
        num_classes=2,
        dropout=cfg["dropout"],
        pretrained_embed=pretrained,
        freeze_embed=cfg["glove_freeze"],
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  可训练参数量: {n_params:,}")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])

    # ---------- 4. 训练 ----------
    print("[4/4] 训练 ...")
    history = []
    best_acc, best_epoch, patience = 0.0, 0, 0

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        running_loss, batches = 0.0, 0
        ep_t0 = time.time()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            batches += 1

        train_acc, *_ = evaluate(model, train_loader, device)
        test_acc, prec, rec, f1 = evaluate(model, test_loader, device)
        avg_loss = running_loss / batches
        history.append({
            "epoch": epoch, "loss": avg_loss,
            "train_acc": train_acc, "test_acc": test_acc,
            "precision": prec, "recall": rec, "f1": f1,
        })
        print(f"  Epoch {epoch}/{cfg['epochs']}  loss={avg_loss:.4f}  "
              f"train_acc={train_acc:.4f}  test_acc={test_acc:.4f}  "
              f"P={prec:.4f} R={rec:.4f} F1={f1:.4f}  ({(time.time()-ep_t0):.0f}s)")

        if test_acc > best_acc:
            best_acc, best_epoch = test_acc, epoch
            patience = 0
            torch.save({"model": model.state_dict(), "config": cfg, "vocab": vocab},
                       os.path.join(cfg["output_dir"], "model.pt"))
        else:
            patience += 1
            if patience >= 3:
                print(f"  验证准确率连续 {patience} 轮无提升，提前停止。")
                break

    with open(os.path.join(cfg["output_dir"], "history.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 64)
    print(f"训练完成。最佳 test 准确率 = {best_acc:.4f}（第 {best_epoch} 轮）")
    print(f"模型已保存: {os.path.join(cfg['output_dir'], 'model.pt')}")


def load_glove(cfg, vocab):
    """可选：从 GloVe 文本文件加载词向量。未配置则返回 None。"""
    path = cfg.get("glove_path")
    if not path or not os.path.exists(path):
        return None
    dim = cfg.get("glove_embed_dim", cfg["embed_dim"])
    print(f"  加载 GloVe 词向量: {path} ...")
    vecs = torch.zeros(len(vocab), dim)
    found = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip().split(" ")
            word = parts[0]
            if word in vocab:
                try:
                    vecs[vocab[word]] = torch.tensor([float(x) for x in parts[1:]], dtype=torch.float)
                    found += 1
                except ValueError:
                    continue
    print(f"  命中词表 {found}/{len(vocab)} 个词")
    return vecs


def predict(args):
    """加载已训练模型，对单条文本做预测。"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = args.output_dir or CONFIG["output_dir"]
    ckpt_path = os.path.join(out_dir, "model.pt")
    if not os.path.exists(ckpt_path):
        raise SystemExit(f"未找到模型 {ckpt_path}，请先运行 python train.py 训练。")

    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    vocab = ckpt["vocab"]

    model = TextCNN(
        vocab_size=len(vocab),
        embed_dim=cfg["embed_dim"],
        num_filters=cfg["num_filters"],
        filter_sizes=cfg["filter_sizes"],
        num_classes=2,
        dropout=cfg["dropout"],
    ).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    x = torch.tensor([encode(args.predict, vocab, cfg["max_len"])], dtype=torch.long).to(device)
    with torch.no_grad():
        logits = model(x)
        prob = F.softmax(logits, dim=1)[0]
    label = int(logits.argmax(1).item())
    print(f"文本: {args.predict}")
    print(f"预测: {'正面 (positive)' if label == 1 else '负面 (negative)'}")
    print(f"概率: pos={prob[1]:.4f}  neg={prob[0]:.4f}")


def set_seed(seed):
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args():
    p = argparse.ArgumentParser(description="TextCNN IMDb 情感分类")
    p.add_argument("--predict", type=str, default=None, help="预测模式：对给定文本做情感判断")
    p.add_argument("--data_dir", type=str, default=None)
    p.add_argument("--epochs", type=int, default=None)
    p.add_argument("--batch_size", type=int, default=None)
    p.add_argument("--max_len", type=int, default=None)
    p.add_argument("--max_vocab", type=int, default=None)
    p.add_argument("--embed_dim", type=int, default=None)
    p.add_argument("--num_filters", type=int, default=None)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--output_dir", type=str, default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.predict:
        predict(args)
    else:
        main()
