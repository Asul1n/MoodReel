"""情感极性分析模块路由：英文 TextCNN / 中文腾讯 / 双引擎对照。

契约见 schemas.AnalyzeRequest / AnalyzeBatchOut。成员B实现 services 后接通。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import schemas
from ..services import textcnn, tencent

router = APIRouter(prefix="/analyze", tags=["sentiment"])


def _route(texts: list[str], lang: str | None):
    # 成员B：实现语言判定（en -> textcnn.analyze；zh -> tencent.analyze）
    raise HTTPException(status_code=501, detail="成员B实现：语言路由")


@router.post("/en", response_model=schemas.AnalyzeBatchOut)
def analyze_en(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """英文批量 -> TextCNN。返回含 throughput（>=200 条/s 在此展示）。"""
    if not textcnn.is_ready():
        raise HTTPException(status_code=503, detail="TextCNN 模型未就绪（成员B接入）")
    results, elapsed_ms, throughput = textcnn.analyze_batch(req.texts)
    return schemas.AnalyzeBatchOut(
        results=results, count=len(req.texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


@router.post("/zh", response_model=schemas.AnalyzeBatchOut)
def analyze_zh(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """中文 -> 腾讯情感 API（可开关/优雅降级）。"""
    if not tencent.enabled():
        raise HTTPException(status_code=503, detail="腾讯情感 API 未启用，请到后端 .env 配置")
    results, elapsed_ms, throughput = tencent.analyze_batch(req.texts)
    return schemas.AnalyzeBatchOut(
        results=results, count=len(req.texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


@router.post("", response_model=schemas.AnalyzeBatchOut)
def analyze_auto(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """按语言自动路由（App 主入口）。"""
    return _route(req.texts, req.lang)  # type: ignore[return-value]


class CompareReq(BaseModel):
    text: str


@router.post("/compare")
def compare(req: CompareReq) -> dict:
    """同一条英文：TextCNN vs 腾讯 对照（成员B实现）。"""
    raise HTTPException(status_code=501, detail="成员B实现：双引擎对照")
