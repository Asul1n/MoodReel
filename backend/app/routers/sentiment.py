"""情感极性分析模块路由：英文 TextCNN(本地) / 中文 百度情感API / 自动路由。

- /analyze/en  英文批量 -> TextCNN（本地模型，需 torch + model.pt）
- /analyze/zh  中文批量 -> 百度情感倾向分析 API
- /analyze     （App 主入口）按语言自动路由
契约见 schemas.AnalyzeRequest / AnalyzeBatchOut。
"""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import schemas
from ..services import baidu, textcnn

router = APIRouter(prefix="/analyze", tags=["sentiment"])
_CJK = re.compile(r"[一-鿿]")


def _en_batch(texts: list[str]) -> schemas.AnalyzeBatchOut:
    if not textcnn.is_ready():
        raise HTTPException(status_code=503,
                            detail="TextCNN 模型未就绪（需 torch + backend/models/model.pt）")
    results, elapsed_ms, throughput = textcnn.analyze_batch(texts)
    return schemas.AnalyzeBatchOut(
        results=results, count=len(texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


def _zh_batch(texts: list[str]) -> schemas.AnalyzeBatchOut:
    if not baidu.enabled():
        raise HTTPException(status_code=503,
                            detail="百度情感 API 未启用：请在 backend/.env 配置 BAIDU_* 后重试")
    results, elapsed_ms, throughput = baidu.analyze_batch(texts)
    return schemas.AnalyzeBatchOut(
        results=results, count=len(texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


def _detect_lang(texts: list[str], lang: str | None) -> str:
    if lang in ("en", "zh"):
        return lang
    return "zh" if any(_CJK.search(t) for t in texts) else "en"


@router.post("/en", response_model=schemas.AnalyzeBatchOut)
def analyze_en(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """英文批量 -> TextCNN。"""
    return _en_batch(req.texts)


@router.post("/zh", response_model=schemas.AnalyzeBatchOut)
def analyze_zh(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """中文 -> 百度情感 API（可开关/优雅降级）。"""
    return _zh_batch(req.texts)


@router.post("", response_model=schemas.AnalyzeBatchOut)
def analyze_auto(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """按语言自动路由（App 主入口）。"""
    lang = _detect_lang(req.texts, req.lang)
    return _zh_batch(req.texts) if lang == "zh" else _en_batch(req.texts)


class CompareReq(BaseModel):
    text: str


@router.post("/compare")
def compare(req: CompareReq) -> dict:
    """同一文本多引擎对照（当前实现：英文 TextCNN vs 百度；中文仅百度）。"""
    lang = _detect_lang([req.text], None)
    out: dict = {"text": req.text, "lang": lang}
    if lang == "en" and textcnn.is_ready():
        (item,) = textcnn.analyze_batch([req.text])[0][:1]
        out["textcnn"] = item
    if baidu.enabled():
        out["baidu"] = baidu.analyze(req.text)
    if not out.get("textcnn") and not out.get("baidu"):
        raise HTTPException(status_code=503, detail="暂无可用的情感引擎：请确认模型/百度配置")
    return out
