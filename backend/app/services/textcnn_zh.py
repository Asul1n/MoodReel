"""中文本地 TextCNN 服务（A 方案）。

加载 models/model_zh.pt（豆瓣星标弱标签训练），正/负二类 + 置信度。
就绪时 /analyze/zh 与 backfill 优先走它（免费、可离线），否则回退 DeepSeek。
"""
import logging
import time

from .. import config

logger = logging.getLogger("moodreel")

_READY = False
_MSG = ""
_MODEL = None
_CFG = None
_VOCAB = None
_DEVICE = None


def load() -> None:
    global _READY, _MSG, _MODEL, _CFG, _VOCAB, _DEVICE
    path = config.MODEL_DIR / "model_zh.pt"
    if not path.exists():
        _READY, _MSG = False, f"未找到中文模型 {path}（先跑 scripts/train_textcnn_zh.py）"
        return
    try:
        from ..model_runtime.zh_kernel import load_zh_model
        _MODEL, _CFG, _VOCAB, _DEVICE = load_zh_model(str(path))
        _READY, _MSG = True, ""
        logger.info("中文本地 TextCNN 加载成功 model_zh.pt")
    except Exception as exc:
        _READY, _MSG = False, f"中文模型加载失败：{exc}"


def is_ready() -> bool:
    return _READY


def status() -> dict:
    return {"ready": _READY, "msg": _MSG}


def analyze_batch(texts: list[str], lang: str = "zh") -> tuple[list[dict], float, float]:
    if not _READY:
        raise RuntimeError("中文本地模型未就绪：" + _MSG)
    import torch
    from ..model_runtime.zh_kernel import encode_zh

    t0 = time.perf_counter()
    xs = torch.tensor([encode_zh(t, _VOCAB, int(_CFG["max_len"])) for t in texts],
                      dtype=torch.long, device=_DEVICE)
    with torch.no_grad():
        probs = torch.softmax(_MODEL(xs), dim=1)   # [n,2] = (p_neg, p_pos)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    n = len(texts)
    results = []
    for i, text in enumerate(texts):
        p_pos = float(probs[i, 1])
        p_neg = float(probs[i, 0])
        results.append({
            "text": text, "lang": lang, "model": "textcnn_zh",
            "label": "positive" if p_pos >= p_neg else "negative",
            "prob": round(max(p_pos, p_neg), 4),
            "ms": round(elapsed_ms / max(1, n), 3),
        })
    throughput = n / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0
    return results, round(elapsed_ms, 3), round(throughput, 1)
