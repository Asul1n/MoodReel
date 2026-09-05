"""中文情感 TextCNN 共享内核：jieba 分词 + 编码 + 模型类 + checkpoint 加载。

训练脚本 scripts/train_textcnn_zh.py 与线上服务 services/textcnn_zh.py
都用本模块，保证"分词/词表"完全一致（训练对得上线上）。
模型类复用 app/model_runtime/train.py 的 TextCNN（英文那套同构）。
"""
import json
from collections import Counter
from pathlib import Path

import jieba
import torch

from .train import TextCNN  # noqa: F401  同构模型类（复用）

PAD = "<pad>"
UNK = "<unk>"
PAD_IDX = 0
UNK_IDX = 1


def tokenize_zh(text: str) -> list[str]:
    """jieba 分词，仅保留非空 token（不过度过滤，方便通用中文）。"""
    return [w for w in jieba.lcut((text or "").strip()) if w.strip()]


def build_vocab(texts: list[str], max_vocab: int = 30000) -> dict[str, int]:
    counter: Counter = Counter()
    for t in texts:
        counter.update(tokenize_zh(t))
    vocab = {PAD: PAD_IDX, UNK: UNK_IDX}
    for w, _ in counter.most_common(max_vocab - 2):
        vocab[w] = len(vocab)
    return vocab


def encode_zh(text: str, vocab: dict[str, int], max_len: int) -> list[int]:
    ids = [vocab.get(w, UNK_IDX) for w in tokenize_zh(text)]
    if len(ids) > max_len:
        ids = ids[:max_len]
    else:
        ids = ids + [PAD_IDX] * (max_len - len(ids))
    return ids


def load_zh_model(model_path: str):
    """加载 model_zh.pt -> (model, cfg, vocab, device)。"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    cfg, vocab = ckpt["config"], ckpt["vocab"]
    model = TextCNN(vocab_size=len(vocab), embed_dim=cfg["embed_dim"],
                    num_filters=cfg["num_filters"], filter_sizes=cfg["filter_sizes"],
                    num_classes=2, dropout=cfg["dropout"]).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()
    return model, cfg, vocab, device
