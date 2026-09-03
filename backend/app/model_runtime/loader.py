"""从队友训练的 checkpoint(model.pt) 构建推理模型。

model.pt 内容：{"model": state_dict, "config": {...}, "vocab": {...}}。
模型类 TextCNN / tokenizer 定义在 .train.py（与队友训练代码逐字一致）。
"""
import torch

from .train import TextCNN


def load_model(model_path: str):
    """返回 (model, config, vocab, device)。"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = torch.load(model_path, map_location=device, weights_only=False)
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
    return model, cfg, vocab, device
