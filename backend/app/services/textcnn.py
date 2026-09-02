"""TextCNN 推理服务（英文，成员B）。

约定：
- 训练脚本 scripts/train_textcnn.py 产出 models/vocab.json + models/textcnn.npz
- 训练与线上必须共用同一份 tokenizer 与词表，避免"训练对不上线上"
- 启动时一次性加载；推理放线程池；analyze_batch 返回耗时与吞吐（>=200 条/s 目标在此体现）
"""
from .. import config

_READY = False


def load() -> None:
    """成员B：加载 vocab + 权重，置 _READY=True。main.py lifespan 中调用。"""
    global _READY
    # 示例：
    #   vocab = load_json(config.MODEL_DIR / "vocab.json")
    #   params = np.load(config.MODEL_DIR / "textcnn.npz")
    #   _READY = True
    raise NotImplementedError("成员B实现 load()")


def is_ready() -> bool:
    return _READY


def _preprocess(text: str) -> list[str]:
    """成员B：与训练脚本完全一致的前处理 + tokenize。"""
    raise NotImplementedError("成员B实现：与 train_textcnn 共用 tokenizer")


def analyze_batch(texts: list[str]) -> tuple[list, float, float]:
    """返回 (results: list[AnalyzeItem], elapsed_ms, throughput)。"""
    raise NotImplementedError("成员B实现：批量前向推理并计时")
