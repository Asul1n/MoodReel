"""百度 AI 情感倾向分析 API adapter（中文，默认中文通道）。

文档：https://cloud.baidu.com/product/nlp_apply/sentiment_classify
鉴权：OAuth2 client_credentials 拿 access_token（~30 天有效，本地缓存临近过期才刷新）。
调用：POST https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify?access_token=...
      body {"text": "..."}
返回 items[0]：sentiment(0负/1中性/2正) + confidence + positive_prob/negative_prob

配置：.env 的 BAIDU_API_KEY / BAIDU_SECRET_KEY / BAIDU_ENABLED。
优雅降级：未配置/超时/配额尽 -> 抛 RuntimeError，由路由转 503 中文提示。
"""
import time

import requests

from .. import config

TOKEN: dict = {"value": None, "expire": 0.0}
_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
_API_URL = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify"
# sentiment: 0 负 / 1 中性 / 2 正
_SENTIMENT = {0: "negative", 1: "neutral", 2: "positive"}


def enabled() -> bool:
    return (config.BAIDU_ENABLED
            and bool(config.BAIDU_API_KEY) and bool(config.BAIDU_SECRET_KEY))


def _access_token() -> str:
    """取（并缓存）access_token；失效前 5 分钟刷新。"""
    if TOKEN["value"] and time.time() < TOKEN["expire"] - 300:
        return TOKEN["value"]
    r = requests.post(_TOKEN_URL, params={
        "grant_type": "client_credentials",
        "client_id": config.BAIDU_API_KEY,
        "client_secret": config.BAIDU_SECRET_KEY,
    }, timeout=8)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"百度鉴权失败：{data.get('error')} {data.get('error_description')}")
    TOKEN["value"] = data["access_token"]
    TOKEN["expire"] = time.time() + int(data.get("expires_in", 2592000))
    return TOKEN["value"]


def analyze(text: str) -> dict:
    """单条中文 -> {label, prob, ms, positive_prob, negative_prob}。"""
    if not enabled():
        raise RuntimeError("百度情感 API 未配置（.env 的 BAIDU_*）")
    text = (text or "").strip()
    if not text:
        raise ValueError("text 不能为空")
    t0 = time.perf_counter()
    r = requests.post(_API_URL,
                      params={"access_token": _access_token()},
                      json={"text": text},
                      headers={"Content-Type": "application/json"},
                      timeout=10)
    data = r.json()
    if "items" not in data:
        raise RuntimeError(
            f"百度 API 错误 {data.get('error_code')}: {data.get('error_msg')}")
    it = data["items"][0]
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "label": _SENTIMENT.get(it.get("sentiment"), "neutral"),
        "prob": round(float(it.get("confidence") or 0.0), 4),
        "ms": round(ms, 3),
        "positive_prob": it.get("positive_prob"),
        "negative_prob": it.get("negative_prob"),
    }


def analyze_batch(texts: list[str]) -> tuple[list[dict], float, float]:
    """批量（顺序调用，含配额保护）。返回 (results, elapsed_ms, throughput)。"""
    t0 = time.perf_counter()
    results: list[dict] = []
    for t in texts:
        r = analyze(t)
        results.append({"text": t, "lang": "zh", "model": "baidu", **r})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    n = len(texts)
    throughput = n / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0
    return results, round(elapsed_ms, 3), round(throughput, 1)
