"""情感极性分析模块路由。

- /analyze/en      英文批量 -> 本地 TextCNN
- /analyze/zh      中文批量 -> DeepSeek（未配置回退百度）
- /analyze         自动语言路由（App 主入口）
- /analyze/backfill 给某上下文的评论批量补情感标签（全流程：爬取→模型→分析）
- /analyze/compare 同文本多引擎对照
契约见 schemas.AnalyzeRequest / AnalyzeBatchOut。
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger("moodreel")
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..services import deepseek, textcnn, textcnn_zh

router = APIRouter(prefix="/analyze", tags=["sentiment"])
_CJK = re.compile(r"[一-鿿]")


def _context_movie_id(context: str) -> str | None:
    ctx = (context or "whole").strip()
    if ctx in ("", "whole"):
        return None
    return ctx[len("movie:"):] if ctx.startswith("movie:") else ctx


def _detect_lang(texts: list[str], lang: str | None) -> str:
    if lang in ("en", "zh"):
        return lang
    return "zh" if any(_CJK.search(t) for t in texts) else "en"


def _en_batch(texts: list[str]) -> schemas.AnalyzeBatchOut:
    if not textcnn.is_ready():
        raise HTTPException(status_code=503,
                            detail="TextCNN 模型未就绪（需 torch + backend/models/model.pt）")
    results, elapsed_ms, throughput = textcnn.analyze_batch(texts)
    return schemas.AnalyzeBatchOut(
        results=results, count=len(texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


def _zh_results(texts: list[str]) -> tuple[list[dict], float, float]:
    """中文引擎选择：本地 TextCNN_zh 优先（免费/离线），否则 DeepSeek。"""
    if textcnn_zh.is_ready():
        return textcnn_zh.analyze_batch(texts)
    if deepseek.enabled():
        return deepseek.analyze_batch(texts)
    raise RuntimeError("中文情感通道不可用：本地模型未就绪，且 DeepSeek 未配置")


def _zh_batch(texts: list[str]) -> schemas.AnalyzeBatchOut:
    """中文 -> 本地 TextCNN_zh（优先）/ DeepSeek。"""
    try:
        results, elapsed_ms, throughput = _zh_results(texts)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return schemas.AnalyzeBatchOut(
        results=results, count=len(texts), elapsed_ms=elapsed_ms, throughput=throughput
    )


@router.post("/en", response_model=schemas.AnalyzeBatchOut)
def analyze_en(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """英文批量 -> TextCNN。"""
    return _en_batch(req.texts)


@router.post("/zh", response_model=schemas.AnalyzeBatchOut)
def analyze_zh(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """中文 -> DeepSeek（未配置回退百度）。"""
    return _zh_batch(req.texts)


@router.post("", response_model=schemas.AnalyzeBatchOut)
def analyze_auto(req: schemas.AnalyzeRequest) -> schemas.AnalyzeBatchOut:
    """按语言自动路由（App 主入口）。"""
    lang = _detect_lang(req.texts, req.lang)
    return _zh_batch(req.texts) if lang == "zh" else _en_batch(req.texts)


class BackfillReq(BaseModel):
    context: str = Field(min_length=1, description="whole 或 movie:{movie_id}")
    lang: str | None = "zh"
    force: bool = False
    limit: int = Field(300, ge=1, le=1000)


@router.post("/backfill", status_code=200)
def backfill(req: BackfillReq, db: Session = Depends(get_db)) -> dict:
    """全流程：把某上下文的评论批量交给 DeepSeek 打情感标签并回写。

    默认只给还没有 pred_label 的评论补标；force=true 则全部覆盖。
    """
    if not (textcnn_zh.is_ready() or deepseek.enabled()):
        raise HTTPException(status_code=503,
                            detail="中文情感通道不可用：本地模型未就绪，且 DeepSeek 未配置")
    mid = _context_movie_id(req.context)
    stmt = select(models.Review).order_by(models.Review.id.asc())
    if mid:
        stmt = stmt.where(models.Review.movie_id == mid)
    if req.lang:
        stmt = stmt.where(models.Review.lang == req.lang)
    if not req.force:
        stmt = stmt.where(models.Review.pred_label.is_(None))
    rows = db.scalars(stmt.limit(req.limit)).all()
    if not rows:
        return {"context": req.context, "updated": 0, "model": "deepseek",
                "message": "没有待补标的评论（force=true 可覆盖已有标签）"}
    engine = "textcnn_zh" if textcnn_zh.is_ready() else "deepseek"
    try:
        if engine == "textcnn_zh":
            res, _, _ = textcnn_zh.analyze_batch([r.text for r in rows])
            labels = [{"label": x["label"], "prob": x["prob"]} for x in res]
        else:
            labels = deepseek.classify([r.text for r in rows])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    for r, lab in zip(rows, labels):
        r.pred_label = lab["label"]
        r.pred_prob = lab["prob"]
        r.model = engine
    db.commit()
    logger.info("backfill context=%s updated=%s model=%s", req.context, len(rows), engine)
    return {"context": req.context, "updated": len(rows),
            "model": engine, "lang": req.lang}


class CompareReq(BaseModel):
    text: str


@router.post("/compare")
def compare(req: CompareReq) -> dict:
    """同文本多引擎对照（en：TextCNN；zh：DeepSeek/百度）。"""
    lang = _detect_lang([req.text], None)
    out: dict = {"text": req.text, "lang": lang}
    if lang == "en" and textcnn.is_ready():
        (item,) = textcnn.analyze_batch([req.text])[0][:1]
        out["textcnn"] = item
    if lang == "zh":
        try:
            results, _, _ = _zh_results([req.text])
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        out[results[0]["model"]] = results[0]
    if len(out) < 3:
        raise HTTPException(status_code=503,
                            detail="暂无可用的情感引擎：英文需本地模型，中文需本地模型或 DeepSeek")
    return out
