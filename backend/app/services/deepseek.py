"""DeepSeek 大模型情感分析 adapter（OpenAI 兼容；中/英文均可）。

用途：
- 对爬取的评论**批量打标**（全流程）：把整部片评论分批喂给 LLM，
  让它输出每条极性 positive / neutral / negative + confidence。
- 也承担 /analyze/zh 的实时中文判断（比百度便宜、更灵活）。

配置：.env 的 DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL / DEEPSEEK_ENABLED。
默认每次最多 15 条打包成一个请求以省 token；解析失败自动重试一次。
"""
import json
import logging
import re
import time

import requests

from .. import config

logger = logging.getLogger("moodreel")

BATCH = 15
LABELS = {"positive", "neutral", "negative"}
_SYSTEM = "你是电影评论情感分析器。只输出 JSON，不要输出任何多余文字。"
_USER = (
    "判断下面每条电影评论的情感极性。"
    "严格输出 JSON：{{\"results\":[{{\"label\":\"positive|neutral|negative\","
    "\"confidence\":0~1 小数}},...]}}，长度与输入完全一致、顺序一一对应，不要回显评论原文。\n"
    "评论列表：\n{items}"
)


def enabled() -> bool:
    return config.DEEPSEEK_ENABLED and bool(config.DEEPSEEK_API_KEY)


def _url() -> str:
    return config.DEEPSEEK_BASE_URL.rstrip("/") + "/chat/completions"


def _parse_json(text: str):
    """剥掉 ```json 围栏后解析。"""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    # 兜底：只截取第一个 { 到最后一个 }
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def _chat(texts: list[str]) -> list[dict]:
    """单次请求：返回 results 数组。失败抛 RuntimeError。"""
    items = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
    body = {
        "model": config.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(items=items)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
               "Content-Type": "application/json"}
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            r = requests.post(_url(), json=body, headers=headers, timeout=60)
            if r.status_code == 400 and "response_format" in r.text and attempt == 0:
                body.pop("response_format")          # 个别部署不支持 json 模式，去掉重试
                last_err = RuntimeError("response_format 不支持")
                continue
            if r.status_code != 200:
                raise RuntimeError(f"DeepSeek HTTP {r.status_code}: {r.text[:200]}")
            content = r.json()["choices"][0]["message"]["content"]
            parsed = _parse_json(content)
            if isinstance(parsed, dict):
                results = parsed.get("results") or parsed.get("labels") or []
            else:
                results = parsed
            return results
        except Exception as exc:  # 网络/解析错误
            last_err = exc
            if attempt == 0:
                time.sleep(1.5)
    raise RuntimeError(f"DeepSeek 调用失败：{last_err}")


def classify(texts: list[str]) -> list[dict]:
    """分批打标。返回 [{label, prob}, ...]，长度与输入一致。"""
    out: list[dict] = []
    total = len(texts)
    for i in range(0, total, BATCH):
        chunk = texts[i:i + BATCH]
        logger.info("DeepSeek 打标进度 %d/%d 条（本批 %d 条）", min(i + len(chunk), total), total, len(chunk))
        raw = _chat(chunk)
        for r in raw:
            label = str((r or {}).get("label", "")).lower()
            if label not in LABELS:
                label = "neutral"
            try:
                conf = float(r.get("confidence"))
            except (TypeError, ValueError):
                conf = 1.0
            out.append({"label": label, "prob": round(min(max(conf, 0.0), 1.0), 4)})
    if len(out) != len(texts):
        raise RuntimeError(f"DeepSeek 返回条数不符：期望 {len(texts)}，实际 {len(out)}")
    return out


def analyze_batch(texts: list[str], lang: str = "zh") -> tuple[list[dict], float, float]:
    """实时分析（/analyze/zh 用）。返回 (results, elapsed_ms, throughput)。"""
    if not enabled():
        raise RuntimeError("DeepSeek 未配置（.env 的 DEEPSEEK_API_KEY）")
    t0 = time.perf_counter()
    labels = classify(texts)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    results = [
        {"text": t, "lang": lang, "model": "deepseek",
         "label": lab["label"], "prob": lab["prob"], "ms": round(elapsed_ms / max(1, len(texts)), 3)}
        for t, lab in zip(texts, labels)
    ]
    n = len(texts)
    throughput = n / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0.0
    return results, round(elapsed_ms, 3), round(throughput, 1)
