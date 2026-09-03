"""TextCNN 推理服务（英文，进程内加载队友训练好的 model.pt）。

模型来源：成员B 训练的 TextCNN（交付包 textcnn_sentiment/model.pt）。模型类与
tokenizer 在 app/model_runtime/train.py（与训练逐字一致），保证"训练对得上线上"。

说明：torch 惰性导入——未安装 torch 或缺失 model.pt 时服务照常启动，
仅 model_ready=False，/health 里给出原因。
"""
from .. import config

_READY = False
_MSG = ""
_MODEL = None
_CFG = None
_VOCAB = None
_DEVICE = None


def load() -> None:
    """启动时调用一次：加载 model.pt 并置就绪标志。"""
    global _READY, _MSG, _MODEL, _CFG, _VOCAB, _DEVICE
    try:
        import torch  # noqa: F401  惰性：确认 torch 可用
        from ..model_runtime.loader import load_model
    except Exception as exc:  # torch 未安装等
        _READY, _MSG = False, f"torch/loader 不可用：{exc}"
        return
    path = config.MODEL_DIR / "model.pt"
    if not path.exists():
        _READY, _MSG = False, f"未找到模型 {path}（请让成员B把 model.pt 放到 backend/models/）"
        return
    try:
        _MODEL, _CFG, _VOCAB, _DEVICE = load_model(str(path))
        _READY, _MSG = True, ""
    except Exception as exc:
        _READY, _MSG = False, f"模型加载失败：{exc}"


def is_ready() -> bool:
    return _READY


def status() -> dict:
    return {"ready": _READY, "msg": _MSG}


def analyze_batch(texts: list[str]) -> tuple[list[dict], float, float]:
    """英文批量情感分析。

    返回 (results, elapsed_ms, throughput)；results 元素字段对齐 schemas.AnalyzeItem：
    {text, lang:'en', model:'textcnn', label, prob, ms}
    """
    if not _READY:
        raise RuntimeError("TextCNN 未就绪：" + _MSG)
    import time

    import torch

    from ..model_runtime.train import encode

    max_len = int(_CFG["max_len"])
    n = len(texts)
    t0 = time.perf_counter()
    xs = torch.tensor([encode(t, _VOCAB, max_len) for t in texts],
                      dtype=torch.long, device=_DEVICE)
    with torch.no_grad():
        probs = torch.softmax(_MODEL(xs), dim=1)  # [n, 2] = (p_neg, p_pos)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    per_ms = elapsed_ms / max(1, n)

    results: list[dict] = []
    for i, text in enumerate(texts):
        p_pos = float(probs[i, 1])
        p_neg = float(probs[i, 0])
        label = "positive" if p_pos >= p_neg else "negative"
        results.append({
            "text": text,
            "lang": "en",
            "model": "textcnn",
            "label": label,
            "prob": round(max(p_pos, p_neg), 4),
            "ms": round(per_ms, 3),
        })
    throughput = n / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0
    return results, round(elapsed_ms, 3), round(throughput, 1)
