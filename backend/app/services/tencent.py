"""腾讯 AI 情感分析 API adapter（中文，成员B）。

说明：
- 以实际开通的平台为准（ai.qq.com 开放平台 / 腾讯云 NLP），签名与请求体差异收敛在本文件。
- 配置见 .env：TENCENT_APPID / TENCENT_SECRET_KEY / TENCENT_ENABLED。
- 必须"可开关 + 优雅降级"：未配置/超时/配额尽时抛可读异常，由路由转成 503 中文提示。
"""
from .. import config


def enabled() -> bool:
    return config.TENCENT_ENABLED and bool(config.TENCENT_APPID) and bool(config.TENCENT_SECRET_KEY)


def _sign(params: dict) -> dict:
    """成员B：按所选平台要求计算签名后返回请求参数。"""
    raise NotImplementedError("成员B实现：平台签名")


def analyze(text: str) -> dict:
    """单条中文 -> {label, prob, ms}。"""
    raise NotImplementedError("成员B实现：调用腾讯情感分析")


def analyze_batch(texts: list[str]) -> tuple[list, float, float]:
    """批量（顺序调用，含配额保护）。返回 (results, elapsed_ms, throughput)。"""
    raise NotImplementedError("成员B实现：批量调用 + 计时")
