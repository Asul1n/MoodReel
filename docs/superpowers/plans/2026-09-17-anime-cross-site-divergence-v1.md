# 动漫评论跨站口碑分歧分析系统 v1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 MoodReel 后端上迭代出「国内两站（Bangumi + B站）跑通跨站口碑分歧分析」的能力，产出可演示的 REST 接口与前端对比页。

**Architecture:** 新增三层——① `services/adapters/` 四站统一适配器（v1 实现 bangumi/bilibili，API 优先 + 网页兜底）；② `services/identity.py` 番剧身份归并（把各站 ID 对齐到内部 `anime_id`）；③ `services/divergence.py` 纯函数分歧引擎（归一化 → 贝叶斯收缩 → 加权标准差 → 四象限）。三者之上挂 `routers/anime.py` 与 `routers/divergence.py`，复用现有 `CrawlJob` 异步任务、`nlp.py` 热点挖掘与 `textcnn_zh.py` 情感通道。

**Tech Stack:** Python 3.10+、FastAPI、SQLAlchemy 2.0（SQLite）、pydantic、requests、jieba、PyTorch（TextCNN）、pytest、ArkTS/ArkUI（Canvas 自绘图表）

**规格依据：** `docs/superpowers/specs/2026-09-17-anime-cross-site-divergence-design.md`

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|---|---|
| `backend/app/services/adapters/__init__.py` | 适配器注册表：`get_adapter(source)` |
| `backend/app/services/adapters/base.py` | 统一契约：`SourceResult` / `Candidate` / `Meta` / `Rating` / `AnimeReview` / `SourceAdapter` |
| `backend/app/services/adapters/bangumi.py` | Bangumi REST API 适配器 |
| `backend/app/services/adapters/bilibili.py` | B站适配器（API + 网页兜底） |
| `backend/app/services/identity.py` | 番剧身份归并：标题归一化、跨站映射、误合并防护 |
| `backend/app/services/divergence.py` | 分歧引擎纯函数：归一化/收缩/加权标准差/象限/门槛/汇总 |
| `backend/app/routers/anime.py` | `/anime/search`、`/anime/ingest`、`/anime/{id}/sources` |
| `backend/app/routers/divergence.py` | `/divergence/{id}`、`/ranking/divergence` |
| `backend/scripts/collect_anime_corpus.py` | 采集两站动漫评论 → 自动建训练集 CSV |
| `backend/scripts/train_textcnn_anime.py` | 动漫领域中文 TextCNN 训练与留存集评测 |
| `backend/scripts/calibrate_thresholds.py` | 用真实分布标定象限阈值 |
| `backend/scripts/measure_identity_accuracy.py` | 归并准确率离线测定（100 对基准集） |
| `backend/data/identity_benchmark.csv` | 人工标注的归并基准集（正负各约 50 对） |
| `backend/tests/test_adapters_base.py` | 适配器契约测试 |
| `backend/tests/test_adapters_bangumi.py` | Bangumi 适配器（fixture 离线） |
| `backend/tests/test_adapters_bilibili.py` | B站适配器（fixture 离线） |
| `backend/tests/test_identity.py` | 归并测试（含误合并防护） |
| `backend/tests/test_divergence.py` | 分歧引擎纯函数测试 |
| `backend/tests/test_anime_api.py` | `/anime/*` 接口测试 |
| `backend/tests/test_divergence_api.py` | `/divergence/*` 接口测试 |
| `backend/tests/fixtures/bangumi_*.json` | Bangumi 真实响应录制 |
| `backend/tests/fixtures/bilibili_*.json` | B站真实响应录制 |
| `app/mood_reel_GUI/entry/src/main/ets/components/charts/QuadrantChart.ets` | 分歧象限散点图（Canvas 自绘） |
| `app/mood_reel_GUI/entry/src/main/ets/views/TabCompare.ets` | 跨站对比页 |

### 修改文件

| 文件 | 改动 |
|---|---|
| `backend/app/models.py` | 新增 `Anime` / `AnimeSource` / `Divergence`；`Review` 加可空 `anime_id` |
| `backend/app/db.py` | `_COLUMNS_BY_TABLE["reviews"]` 登记 `anime_id` |
| `backend/app/config.py` | 新增动漫域配置项（阈值、门槛、贝叶斯先验） |
| `backend/app/schemas.py` | 新增 `Anime*` / `Divergence*` 响应模型 |
| `backend/app/main.py` | 注册两个新路由 |
| `backend/app/crawler/douban.py` | 修复 `_get` 失败信息丢失（§11 第 2 条） |
| `backend/app/services/nlp.py` | 新增 `build_source_terms()`：分站独有词 |
| `app/mood_reel_GUI/entry/src/main/ets/model/Models.ets` | 新增动漫域类型 |
| `app/mood_reel_GUI/entry/src/main/ets/services/api.ets` | 新增动漫接口封装 |
| `app/mood_reel_GUI/entry/src/main/ets/pages/Index.ets` | 挂载新 Tab |
| `docs/3_接口契约文档.md`、`docs/2_数据库设计.md` | 同步 |

---

## Task 1: 数据层 —— 新增三表与 Review 扩展

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_models_anime.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_models_anime.py`：

```python
"""动漫域三表建模测试。"""
from app.db import SessionLocal
from app import models


def test_create_anime_with_sources() -> None:
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:253", title_cn="进击的巨人",
                            title_jp="進撃の巨人", year=2013, episodes=25))
        db.add(models.AnimeSource(anime_id="bangumi:253", source="bangumi",
                                  source_id="253", rating_raw=8.6, rating_scale=10,
                                  rating_count=12000, review_count=340))
        db.add(models.AnimeSource(anime_id="bangumi:253", source="bilibili",
                                  source_id="4450", rating_raw=9.5, rating_scale=10,
                                  rating_count=98000, review_count=210))
        db.commit()

        a = db.get(models.Anime, "bangumi:253")
        assert a.title_jp == "進撃の巨人"
        rows = db.query(models.AnimeSource).filter_by(anime_id="bangumi:253").all()
        assert {r.source for r in rows} == {"bangumi", "bilibili"}
    finally:
        db.close()


def test_source_unique_constraint() -> None:
    """同一站同一 source_id 不得重复映射。"""
    import pytest
    from sqlalchemy.exc import IntegrityError
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:1", title_cn="测试"))
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi", source_id="1"))
        db.commit()
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi", source_id="1"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_review_accepts_anime_id() -> None:
    """Review 扩展 anime_id 后仍兼容旧电影数据（movie_id 用法不变）。"""
    db = SessionLocal()
    try:
        db.add(models.Review(movie_id="douban:1292052", source="douban_live",
                             lang="zh", text="老数据"))
        db.add(models.Review(anime_id="bangumi:253", source="bangumi_live",
                             lang="zh", text="新数据"))
        db.commit()
        assert db.query(models.Review).count() == 2
    finally:
        db.close()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_models_anime.py -q`
Expected: FAIL — `AttributeError: module 'app.models' has no attribute 'Anime'`

- [ ] **Step 3: 实现模型**

在 `backend/app/models.py` 顶部 import 增加 `UniqueConstraint`：

```python
from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
```

在文件末尾追加：

```python
class Anime(Base):
    """番剧主表（动漫域）。anime_id 形如 bangumi:253 —— 取归并时的锚点站点 ID。"""

    __tablename__ = "anime"

    anime_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title_cn: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    title_jp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_en: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    season: Mapped[str | None] = mapped_column(String(16), nullable=True)      # 如 2024春
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    studio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnimeSource(Base):
    """跨站映射与各站原始数据（规格 §5.1）。"""

    __tablename__ = "anime_source"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_anime_source_sid"),
        UniqueConstraint("anime_id", "source", name="uq_anime_source_anime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anime_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("anime.anime_id"), index=True)
    source: Mapped[str] = mapped_column(String(16), index=True)   # bangumi / bilibili
    source_id: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    rating_raw: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_scale: Mapped[float | None] = mapped_column(Float, nullable=True)   # 10 或 100
    rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_weighted: Mapped[float | None] = mapped_column(Float, nullable=True)  # 收缩后(10分制)

    review_count: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment_neg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment_mean: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)   # 人工校正过的映射
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Divergence(Base):
    """分歧结果缓存（规格 §5.1）。"""

    __tablename__ = "divergence"

    anime_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("anime.anime_id"), primary_key=True)
    d_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    d_sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    quadrant: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sources_rating: Mapped[str | None] = mapped_column(String(128), nullable=True)     # 逗号分隔
    sources_sentiment: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 逗号分隔
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)   # 完整结果 JSON
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

在 `Review` 类中，于 `movie_id` 之后加入一行：

```python
    anime_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
```

- [ ] **Step 4: 登记老库迁移列**

在 `backend/app/db.py` 的 `_COLUMNS_BY_TABLE["reviews"]` 中加入 `anime_id`：

```python
    "reviews": {
        "review_time": "VARCHAR(32)",
        "anime_id": "VARCHAR(64)",
    },
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_models_anime.py -q`
Expected: PASS（3 passed）

- [ ] **Step 6: 跑全量测试确认无回归**

Run: `cd backend && python3 -m pytest -q`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/models.py backend/app/db.py backend/tests/test_models_anime.py
git commit -m "feat(models): 新增动漫域三表 Anime/AnimeSource/Divergence，Review 扩展 anime_id"
```

---

## Task 2: 适配器统一契约

**Files:**
- Create: `backend/app/services/adapters/__init__.py`
- Create: `backend/app/services/adapters/base.py`
- Test: `backend/tests/test_adapters_base.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_adapters_base.py`：

```python
"""适配器契约测试：SourceResult 必须能表达失败原因（规格 §11）。"""
from app.services.adapters.base import SourceResult, ok, failed, degraded


def test_ok_result_has_no_reason() -> None:
    r = ok("bangumi", data=[1, 2])
    assert r.status == "ok"
    assert r.ok is True
    assert r.error is None
    assert r.data == [1, 2]


def test_failed_result_must_carry_reason_and_http_status() -> None:
    """失败必须带原因 —— 禁止用空列表掩盖失败。"""
    r = failed("bangumi", reason="HTTP 429 限流", http_status=429)
    assert r.status == "failed"
    assert r.ok is False
    assert "429" in r.error
    assert r.http_status == 429


def test_failed_requires_non_empty_reason() -> None:
    import pytest
    with pytest.raises(ValueError):
        failed("bangumi", reason="")


def test_degraded_is_still_ok_for_callers() -> None:
    """降级数据可用，但调用方能看到降级标记。"""
    r = degraded("bilibili", reason="网页兜底命中", data=[1])
    assert r.ok is True
    assert r.status == "degraded"
    assert r.error == "网页兜底命中"


def test_empty_ok_is_distinct_from_failure() -> None:
    """『确实没有数据』与『请求失败』必须可区分。"""
    empty = ok("bangumi", data=[])
    fail = failed("bangumi", reason="连接超时", http_status=None)
    assert empty.ok is True and empty.status == "ok"
    assert fail.ok is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_adapters_base.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.adapters'`

- [ ] **Step 3: 实现契约**

创建 `backend/app/services/adapters/base.py`：

```python
"""四站适配器统一契约（规格 §4.2）。

设计要点：失败必须显式表达，禁止用空列表掩盖。
"""
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

Status = Literal["ok", "degraded", "failed"]


@dataclass
class Candidate:
    """检索候选（尚未归并）。"""
    source: str
    source_id: str
    title_cn: str | None = None
    title_jp: str | None = None
    title_en: str | None = None
    year: int | None = None
    episodes: int | None = None
    url: str | None = None


@dataclass
class Meta:
    """条目元数据。"""
    title_cn: str | None = None
    title_jp: str | None = None
    title_en: str | None = None
    year: int | None = None
    episodes: int | None = None
    studio: str | None = None
    synopsis: str | None = None
    poster_url: str | None = None


@dataclass
class Rating:
    """原始评分。scale 为该站满分（10 或 100）。"""
    score_raw: float
    scale: float
    count: int


@dataclass
class AnimeReview:
    """单条动漫评论。"""
    text: str
    stars: int | None = None      # B站/豆瓣 1-5 星；无则 None
    time: str | None = None       # YYYY-MM-DD


@dataclass
class SourceResult:
    """适配器统一返回。status != failed 时 data 可用。"""
    status: Status
    source: str
    data: Any = None
    error: str | None = None
    http_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.status != "failed"


def ok(source: str, data: Any = None) -> SourceResult:
    return SourceResult(status="ok", source=source, data=data)


def degraded(source: str, reason: str, data: Any = None,
             http_status: int | None = None) -> SourceResult:
    if not reason:
        raise ValueError("degraded 必须说明原因")
    return SourceResult(status="degraded", source=source, data=data,
                        error=reason, http_status=http_status)


def failed(source: str, reason: str, http_status: int | None = None) -> SourceResult:
    if not reason:
        raise ValueError("failed 必须说明原因（禁止用空列表掩盖失败）")
    return SourceResult(status="failed", source=source, error=reason,
                        http_status=http_status)


@runtime_checkable
class SourceAdapter(Protocol):
    """所有站点适配器实现的接口。"""
    source: str

    def search(self, query: str) -> SourceResult: ...
    def fetch_meta(self, source_id: str) -> SourceResult: ...
    def fetch_rating(self, source_id: str) -> SourceResult: ...
    def fetch_reviews(self, source_id: str, limit: int = 200) -> SourceResult: ...
```

创建 `backend/app/services/adapters/__init__.py`：

```python
"""适配器注册表。v1 仅实现 bangumi / bilibili（规格 §3.3）。"""
from .base import (AnimeReview, Candidate, Meta, Rating, SourceAdapter,
                   SourceResult, degraded, failed, ok)

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """类装饰器：把适配器登记进注册表。"""
    _REGISTRY[cls.source] = cls
    return cls


def get_adapter(source: str):
    """按站点名取适配器实例；未实现返回 None（v2 站点在 v1 为 None）。"""
    if source not in _REGISTRY:
        return None
    return _REGISTRY[source]()


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


from . import bangumi as _bangumi  # noqa: E402,F401 触发注册
from . import bilibili as _bilibili  # noqa: E402,F401 触发注册
```

> 注意：`__init__.py` 末尾的两行 import 依赖 Task 3、Task 4 创建的文件。**本任务先只写前三行注册表逻辑与 base.py，把末尾两行 import 留到 Task 4 结束时再加**，否则本任务测试会因缺模块而失败。本任务测试只 import `base`，不受影响。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_adapters_base.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/adapters/ backend/tests/test_adapters_base.py
git commit -m "feat(adapters): 四站适配器统一契约，失败必须携带原因"
```

---

## Task 3: Bangumi 适配器

**Files:**
- Create: `backend/app/services/adapters/bangumi.py`
- Create: `backend/tests/fixtures/bangumi_search.json`
- Create: `backend/tests/fixtures/bangumi_subject.json`
- Test: `backend/tests/test_adapters_bangumi.py`

Bangumi 公开 API：`https://api.bgm.tv/search/subject/{keywords}?type=2&responseGroup=small`（type=2 为动画）；条目详情 `https://api.bgm.tv/v0/subjects/{id}`。**必须设置 User-Agent**（Bangumi 会拒绝空 UA）。

- [ ] **Step 1: 录制真实响应为 fixture**

先真跑一次把响应存下来（离线测试依赖它）：

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel/backend
python3 - <<'PY'
import json, pathlib, requests
UA = {"User-Agent": "MoodReel/0.2 (https://github.com/Asul1n/MoodReel)"}
d = pathlib.Path("tests/fixtures"); d.mkdir(parents=True, exist_ok=True)

r = requests.get("https://api.bgm.tv/search/subject/%E8%BF%9B%E5%87%BB%E7%9A%84%E5%B7%A8%E4%BA%BA",
                 params={"type": 2, "responseGroup": "small"}, headers=UA, timeout=20)
print("search:", r.status_code)
(d / "bangumi_search.json").write_text(r.text, encoding="utf-8")

r2 = requests.get("https://api.bgm.tv/v0/subjects/253", headers=UA, timeout=20)
print("subject:", r2.status_code)
(d / "bangumi_subject.json").write_text(r2.text, encoding="utf-8")
PY
```

Expected: 两个文件写入成功且为合法 JSON。**若返回非 200，改用返回 200 的其他条目 ID，并把测试里的 fixture 断言同步调整。**

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_adapters_bangumi.py`：

```python
"""Bangumi 适配器离线测试（用录制的真实响应）。"""
import json
import pathlib

import pytest

from app.services.adapters.bangumi import BangumiAdapter

FIX = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def adapter() -> BangumiAdapter:
    a = BangumiAdapter()
    a._load_fixture = True          # 测试期禁用真实网络
    return a


def test_parse_search_returns_animation_candidates(adapter, monkeypatch) -> None:
    raw = (FIX / "bangumi_search.json").read_text(encoding="utf-8")
    monkeypatch.setattr(adapter, "_http_get", lambda url, params=None: (200, raw))

    r = adapter.search("进击的巨人")
    assert r.status == "ok"
    assert len(r.data) > 0
    c = r.data[0]
    assert c.source == "bangumi"
    assert c.source_id.isdigit()
    assert c.title_cn


def test_parse_subject_extracts_meta_and_rating(adapter, monkeypatch) -> None:
    raw = (FIX / "bangumi_subject.json").read_text(encoding="utf-8")
    monkeypatch.setattr(adapter, "_http_get", lambda url, params=None: (200, raw))

    meta = adapter.fetch_meta("253")
    assert meta.status == "ok"
    assert meta.data.title_cn

    rating = adapter.fetch_rating("253")
    assert rating.status == "ok"
    assert rating.data.scale == 10
    assert 0 < rating.data.score_raw <= 10
    assert rating.data.count >= 0


def test_http_failure_is_reported_not_swallowed(adapter, monkeypatch) -> None:
    """回归：请求失败必须返回 failed + 原因，绝不能返回空列表。"""
    monkeypatch.setattr(adapter, "_http_get", lambda url, params=None: (429, ""))

    r = adapter.search("任意")
    assert r.status == "failed"
    assert r.ok is False
    assert "429" in r.error
    assert r.http_status == 429


def test_bad_json_is_failure_not_empty(adapter, monkeypatch) -> None:
    monkeypatch.setattr(adapter, "_http_get", lambda url, params=None: (200, "<html>blocked</html>"))

    r = adapter.search("任意")
    assert r.status == "failed"
    assert "解析" in r.error or "JSON" in r.error
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_adapters_bangumi.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.adapters.bangumi'`

- [ ] **Step 4: 实现适配器**

创建 `backend/app/services/adapters/bangumi.py`：

```python
"""Bangumi 番组计划适配器（公开 REST API，需设 User-Agent）。"""
import logging

import requests

from .base import (AnimeReview, Candidate, Meta, Rating, SourceResult,
                   degraded, failed, ok)

logger = logging.getLogger("moodreel")

SEARCH_API = "https://api.bgm.tv/search/subject/{q}"
SUBJECT_API = "https://api.bgm.tv/v0/subjects/{sid}"
EPISODES_API = "https://api.bgm.tv/v0/episodes"
USER_AGENT = "MoodReel/0.2 (https://github.com/Asul1n/MoodReel)"


class BangumiAdapter:
    source = "bangumi"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self._load_fixture = False

    # —— 网络层：返回 (status_code, text)，绝不吞异常 ——
    def _http_get(self, url: str, params: dict | None = None) -> tuple[int, str]:
        try:
            r = requests.get(url, params=params, timeout=self.timeout,
                             headers={"User-Agent": USER_AGENT})
            return r.status_code, r.text
        except requests.RequestException as exc:
            logger.warning("Bangumi 请求异常 url=%s err=%s", url, exc)
            return 0, str(exc)

    def _get_json(self, url: str, params: dict | None = None):
        """返回 (data, SourceResult|None)。失败时第二项非 None。"""
        code, text = self._http_get(url, params)
        if code == 0:
            return None, failed(self.source, f"网络异常：{text}", http_status=None)
        if code != 200:
            return None, failed(self.source, f"HTTP {code}", http_status=code)
        try:
            import json
            return json.loads(text), None
        except ValueError as exc:
            return None, failed(
                self.source, f"响应非 JSON（可能被拦截）：{exc}", http_status=code)

    def search(self, query: str) -> SourceResult:
        q = (query or "").strip()
        if not q:
            return ok(self.source, [])
        import urllib.parse
        data, err = self._get_json(SEARCH_API.format(q=urllib.parse.quote(q)),
                                   {"type": 2, "responseGroup": "small"})
        if err:
            return err
        items = (data or {}).get("list") or []
        out: list[Candidate] = []
        for it in items:
            images = it.get("images") or {}
            out.append(Candidate(
                source=self.source,
                source_id=str(it.get("id")),
                title_cn=it.get("name_cn") or it.get("name"),
                title_jp=it.get("name"),
                year=_year_of(it.get("air_date")),
                episodes=it.get("eps_count") or it.get("eps"),
                url=f"https://bgm.tv/subject/{it.get('id')}",
            ))
        return ok(self.source, out)

    def fetch_meta(self, source_id: str) -> SourceResult:
        data, err = self._get_json(SUBJECT_API.format(sid=source_id))
        if err:
            return err
        if not isinstance(data, dict):
            return failed(self.source, "条目详情结构异常")
        infobox = {b.get("key"): b.get("value") for b in (data.get("infobox") or [])}
        return ok(self.source, Meta(
            title_cn=data.get("name_cn") or data.get("name"),
            title_jp=data.get("name"),
            year=_year_of(data.get("date")),
            episodes=data.get("eps") or data.get("total_episodes"),
            studio=_first_infobox(infobox, "动画制作"),
            synopsis=data.get("summary"),
            poster_url=((data.get("images") or {}).get("large")
                        or (data.get("images") or {}).get("common")),
        ))

    def fetch_rating(self, source_id: str) -> SourceResult:
        data, err = self._get_json(SUBJECT_API.format(sid=source_id))
        if err:
            return err
        rating = (data or {}).get("rating") or {}
        score = rating.get("score")
        if score in (None, 0):
            return ok(self.source, None)      # 确实无评分 —— 与失败区分
        return ok(self.source, Rating(
            score_raw=float(score), scale=10.0,
            count=int(rating.get("total") or 0)))

    def fetch_reviews(self, source_id: str, limit: int = 200) -> SourceResult:
        """v1 不抓 Bangumi 长评（正文需另走网页）；返回空但状态为 ok。"""
        return ok(self.source, [])


def _year_of(date_str: str | None) -> int | None:
    if not date_str or len(str(date_str)) < 4:
        return None
    try:
        return int(str(date_str)[:4])
    except ValueError:
        return None


def _first_infobox(infobox: dict, key: str) -> str | None:
    v = infobox.get(key)
    if isinstance(v, list):
        return v[0] if v else None
    return v if isinstance(v, str) else None
```

在 `backend/app/services/adapters/__init__.py` 末尾加入注册（若 Task 2 注释掉的行尚未加）：

```python
from . import bangumi as _bangumi  # noqa: E402,F401
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_adapters_bangumi.py -q`
Expected: PASS（4 passed）

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/adapters/bangumi.py backend/app/services/adapters/__init__.py \
        backend/tests/test_adapters_bangumi.py backend/tests/fixtures/bangumi_*.json
git commit -m "feat(adapters): Bangumi 适配器（检索/元数据/评分），失败显式上报"
```

---

## Task 4: B站适配器

**Files:**
- Create: `backend/app/services/adapters/bilibili.py`
- Create: `backend/tests/fixtures/bilibili_search.json`
- Test: `backend/tests/test_adapters_bilibili.py`

B站番剧检索：`https://api.bilibili.com/x/web-interface/search/type?search_type=media_bangumi&keyword=…`（需 `Referer: https://www.bilibili.com`）；番剧详情 `https://api.bilibili.com/pgc/view/web/season?season_id=…`（含 `rating.score` / `rating.count`、`stat`）。短评接口需登录 cookie，**v1 走网页兜底并允许降级**。

- [ ] **Step 1: 录制 fixture**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel/backend
python3 - <<'PY'
import json, pathlib, requests
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Referer": "https://www.bilibili.com"}
d = pathlib.Path("tests/fixtures"); d.mkdir(parents=True, exist_ok=True)

r = requests.get("https://api.bilibili.com/x/web-interface/search/type",
                 params={"search_type": "media_bangumi", "keyword": "进击的巨人"},
                 headers=H, timeout=20)
print("search:", r.status_code, r.text[:120])
(d / "bilibili_search.json").write_text(r.text, encoding="utf-8")
PY
```

再从返回结果里取一个 `season_id`，抓详情存为 `bilibili_season.json`：

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel/backend
python3 - <<'PY'
import json, pathlib, requests
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126 Safari/537.36",
     "Referer": "https://www.bilibili.com"}
d = pathlib.Path("tests/fixtures")
data = json.loads((d / "bilibili_search.json").read_text(encoding="utf-8"))
items = (((data.get("data") or {}).get("result")) or [])
assert items, "搜索无结果，换个关键词重试"
sid = items[0].get("season_id") or items[0].get("season_id_str")
print("season_id:", sid)
r = requests.get("https://api.bilibili.com/pgc/view/web/season",
                 params={"season_id": sid}, headers=H, timeout=20)
print("season:", r.status_code)
(d / "bilibili_season.json").write_text(r.text, encoding="utf-8")
PY
```

Expected: 两个 fixture 文件为合法 JSON，`bilibili_season.json` 的 `result.rating.score` 有值。

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_adapters_bilibili.py`：

```python
"""B站适配器离线测试。"""
import pathlib

import pytest

from app.services.adapters.bilibili import BilibiliAdapter

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_search_parses_candidates(monkeypatch) -> None:
    a = BilibiliAdapter()
    raw = (FIX / "bilibili_search.json").read_text(encoding="utf-8")
    monkeypatch.setattr(a, "_http_get", lambda url, params=None: (200, raw))

    r = a.search("进击的巨人")
    assert r.status == "ok"
    assert r.data
    c = r.data[0]
    assert c.source == "bilibili"
    assert c.source_id
    assert c.title_cn


def test_season_rating(monkeypatch) -> None:
    a = BilibiliAdapter()
    raw = (FIX / "bilibili_season.json").read_text(encoding="utf-8")
    monkeypatch.setattr(a, "_http_get", lambda url, params=None: (200, raw))

    r = a.fetch_rating("1")
    assert r.status == "ok"
    assert r.data.scale == 10
    assert 0 < r.data.score_raw <= 10


def test_failure_reports_status_code(monkeypatch) -> None:
    a = BilibiliAdapter()
    monkeypatch.setattr(a, "_http_get", lambda url, params=None: (412, ""))
    r = a.search("任意")
    assert r.status == "failed"
    assert r.http_status == 412


def test_reviews_degrades_when_no_cookie(monkeypatch) -> None:
    """无 cookie 时短评走网页兜底；失败应 degraded 而非 failed。"""
    a = BilibiliAdapter()
    monkeypatch.setattr(a, "_http_get", lambda url, params=None: (200, "<html></html>"))
    r = a.fetch_reviews("1", limit=10)
    assert r.status in ("degraded", "ok")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_adapters_bilibili.py -q`
Expected: FAIL — `No module named 'app.services.adapters.bilibili'`

- [ ] **Step 4: 实现适配器**

创建 `backend/app/services/adapters/bilibili.py`：

```python
"""B站番剧适配器：检索与评分走公开 API，短评走网页兜底（可降级）。"""
import logging
import re

import requests

from .base import (AnimeReview, Candidate, Meta, Rating, SourceResult,
                   degraded, failed, ok)

logger = logging.getLogger("moodreel")

SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
SEASON_API = "https://api.bilibili.com/pgc/view/web/season"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
_TAG = re.compile(r"<[^>]+>")


class BilibiliAdapter:
    source = "bilibili"

    def __init__(self, timeout: int = 15, cookie: str = "") -> None:
        self.timeout = timeout
        self.cookie = cookie

    def _http_get(self, url: str, params: dict | None = None) -> tuple[int, str]:
        headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        try:
            r = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            return r.status_code, r.text
        except requests.RequestException as exc:
            logger.warning("B站请求异常 url=%s err=%s", url, exc)
            return 0, str(exc)

    def _get_json(self, url: str, params: dict | None = None):
        code, text = self._http_get(url, params)
        if code == 0:
            return None, failed(self.source, f"网络异常：{text}")
        if code != 200:
            return None, failed(self.source, f"HTTP {code}", http_status=code)
        try:
            import json
            return json.loads(text), None
        except ValueError as exc:
            return None, failed(self.source, f"响应非 JSON（可能被拦截）：{exc}",
                                http_status=code)

    def search(self, query: str) -> SourceResult:
        q = (query or "").strip()
        if not q:
            return ok(self.source, [])
        data, err = self._get_json(
            SEARCH_API, {"search_type": "media_bangumi", "keyword": q})
        if err:
            return err
        items = ((data.get("data") or {}).get("result")) or []
        out: list[Candidate] = []
        for it in items:
            sid = it.get("season_id") or it.get("season_id_str")
            if not sid:
                continue
            out.append(Candidate(
                source=self.source,
                source_id=str(sid),
                title_cn=_clean(it.get("title")),
                year=_year_of(it.get("pubtime")),
                episodes=it.get("ep_size"),
                url=it.get("url") or f"https://www.bilibili.com/bangumi/play/ss{sid}",
            ))
        return ok(self.source, out)

    def fetch_meta(self, source_id: str) -> SourceResult:
        data, err = self._get_json(SEASON_API, {"season_id": source_id})
        if err:
            return err
        res = (data or {}).get("result") or {}
        if not res:
            return failed(self.source, "番剧详情为空（可能已下架）")
        return ok(self.source, Meta(
            title_cn=res.get("title"),
            title_jp=res.get("origin_name"),
            year=_year_of(res.get("publish", {}).get("pub_time")),
            episodes=res.get("total"),
            studio=res.get("areas", [{}])[0].get("name") if res.get("areas") else None,
            synopsis=res.get("evaluate"),
            poster_url=res.get("cover"),
        ))

    def fetch_rating(self, source_id: str) -> SourceResult:
        data, err = self._get_json(SEASON_API, {"season_id": source_id})
        if err:
            return err
        rating = ((data or {}).get("result") or {}).get("rating") or {}
        score = rating.get("score")
        if not score:
            return ok(self.source, None)     # 确实无评分
        return ok(self.source, Rating(score_raw=float(score), scale=10.0,
                                      count=int(rating.get("count") or 0)))

    def fetch_reviews(self, source_id: str, limit: int = 200) -> SourceResult:
        """短评需登录 cookie；未配置时降级为空结果（不算失败）。"""
        if not self.cookie:
            return degraded(self.source, "未配置 B站 cookie，短评通道降级",
                            data=[])
        return degraded(self.source, "v1 短评网页解析待接入", data=[])


def _clean(html: str | None) -> str | None:
    return _TAG.sub("", html).strip() if html else None


def _year_of(value) -> int | None:
    if value is None:
        return None
    s = str(value)
    if len(s) >= 10 and s.isdigit():          # unix 时间戳
        import datetime
        return datetime.datetime.utcfromtimestamp(int(s[:10])).year
    if len(s) >= 4 and s[:4].isdigit():
        return int(s[:4])
    return None
```

在 `backend/app/services/adapters/__init__.py` 末尾补齐：

```python
from . import bangumi as _bangumi  # noqa: E402,F401
from . import bilibili as _bilibili  # noqa: E402,F401
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_adapters_bilibili.py -q`
Expected: PASS（4 passed）

- [ ] **Step 6: 验证注册表可用**

```bash
cd backend && python3 -c "from app.services.adapters import available_sources, get_adapter; print(available_sources()); print(get_adapter('bangumi').source, get_adapter('bilibili').source); print(get_adapter('mal'))"
```

Expected: 打印 `['bangumi', 'bilibili']`、`bangumi bilibili`、`None`

- [ ] **Step 7: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/adapters/ backend/tests/test_adapters_bilibili.py \
        backend/tests/fixtures/bilibili_*.json
git commit -m "feat(adapters): B站适配器（检索/评分走 API，短评降级）"
```

---

## Task 5: 番剧身份归并

**Files:**
- Create: `backend/app/services/identity.py`
- Test: `backend/tests/test_identity.py`

归并是跨站分析的前提，**错了全盘皆错**（规格 §4.1、§12）。本任务实现纯函数部分：标题归一化 + 候选打分。官方 ID 映射（AniList `idMal`）留到 v2，v1 依赖标题+年份匹配 + 人工校正表（`AnimeSource.is_manual`）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_identity.py`：

```python
"""番剧身份归并测试（规格 §4.1 / §12）。"""
from app.services.adapters.base import Candidate
from app.services.identity import normalize_title, score_match, match_candidates


def test_normalize_strips_noise() -> None:
    assert normalize_title("进击的巨人 第一季") == normalize_title("进击的巨人 第1季")
    assert normalize_title("【TV】进击的巨人") == normalize_title("进击的巨人")
    assert normalize_title("ＡＢＣ") == normalize_title("abc")


def test_match_same_anime_across_sources() -> None:
    """同一部番在两站的标题应判定为同一部。"""
    a = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="4450", title_cn="进击的巨人", year=2013)
    assert score_match(a, b) >= 0.9


def test_different_seasons_do_not_merge() -> None:
    """误合并防护：第一季与第二季绝不能并成一部。"""
    a = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="9999", title_cn="进击的巨人 第二季", year=2017)
    assert score_match(a, b) < 0.7


def test_different_anime_do_not_merge() -> None:
    """误合并防护：完全不同的作品。"""
    a = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="2", title_cn="鬼灭之刃", year=2019)
    assert score_match(a, b) < 0.5


def test_year_mismatch_lowers_score() -> None:
    a = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    b = Candidate(source="bilibili", source_id="2", title_cn="进击的巨人", year=2020)
    assert score_match(a, b) < score_match(a, Candidate(
        source="bilibili", source_id="3", title_cn="进击的巨人", year=2013))


def test_match_candidates_picks_best_above_threshold() -> None:
    anchor = Candidate(source="bangumi", source_id="253", title_cn="进击的巨人", year=2013)
    pool = [
        Candidate(source="bilibili", source_id="4450", title_cn="进击的巨人", year=2013),
        Candidate(source="bilibili", source_id="9999", title_cn="进击的巨人 第二季", year=2017),
        Candidate(source="bilibili", source_id="8888", title_cn="鬼灭之刃", year=2019),
    ]
    best = match_candidates(anchor, pool, threshold=0.7)
    assert best is not None
    assert best.source_id == "4450"


def test_match_candidates_returns_none_when_all_below_threshold() -> None:
    anchor = Candidate(source="bangumi", source_id="1", title_cn="进击的巨人", year=2013)
    pool = [Candidate(source="bilibili", source_id="2", title_cn="鬼灭之刃", year=2019)]
    assert match_candidates(anchor, pool, threshold=0.7) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_identity.py -q`
Expected: FAIL — `No module named 'app.services.identity'`

- [ ] **Step 3: 实现归并**

创建 `backend/app/services/identity.py`：

```python
"""番剧身份归并：把各站条目对齐到同一部番（规格 §4.1）。

v1 策略：标题归一化 + 年份 + 集数加权匹配；官方 ID 映射与 AniList idMal 留 v2。
"""
import re
import unicodedata
from difflib import SequenceMatcher

from .adapters.base import Candidate

# 噪声词：季度/格式标记，参与匹配会误伤（"第二季" ≠ 同季）
_SEASON_PAT = re.compile(r"第\s*[0-9一二三四五六七八九十]+\s*[季期部]|\bseason\s*\d+\b|\b\d+(st|nd|rd|th)\s+season\b",
                         re.IGNORECASE)
_NOISE_PAT = re.compile(r"[【】\[\]（）()《》<>「」『』·・:：!！?？,，.。、~～\-—_/\\|]")
_TV_PAT = re.compile(r"\b(tv|ova|ona|oad|movie|剧场版)\b", re.IGNORECASE)


def normalize_title(title: str | None) -> str:
    """归一化标题：去噪声、统一全半角与大小写、压空白。"""
    if not title:
        return ""
    s = unicodedata.normalize("NFKC", str(title)).lower()
    s = _NOISE_PAT.sub(" ", s)
    s = _TV_PAT.sub(" ", s)
    s = re.sub(r"\s+", "", s)          # 中日文无空格，统一去掉便于比较
    return s


def _season_of(title: str | None) -> str:
    """抽取季度标记（用于区分不同季）。"""
    if not title:
        return ""
    m = _SEASON_PAT.search(unicodedata.normalize("NFKC", str(title)))
    return re.sub(r"\s+", "", m.group(0).lower()) if m else ""


def _title_similarity(a: Candidate, b: Candidate) -> float:
    """取各语言标题两两相似度的最大值。"""
    best = 0.0
    for ta in (a.title_cn, a.title_jp, a.title_en):
        for tb in (b.title_cn, b.title_jp, b.title_en):
            na, nb = normalize_title(ta), normalize_title(tb)
            if not na or not nb:
                continue
            sim = SequenceMatcher(None, na, nb).ratio()
            if na == nb:
                sim = 1.0
            best = max(best, sim)
    return best


def score_match(a: Candidate, b: Candidate) -> float:
    """两条候选属于同一部番的置信度 ∈ [0, 1]。"""
    sim = _title_similarity(a, b)
    if sim == 0.0:
        return 0.0

    # 季度标记不同 —— 强判负，防止把第二季并进第一季
    sa, sb = _season_of(a.title_cn or a.title_jp), _season_of(b.title_cn or b.title_jp)
    if sa != sb:
        return min(sim, 0.3)

    score = sim * 0.7

    # 年份：一致加分，差异大减分
    if a.year and b.year:
        diff = abs(a.year - b.year)
        if diff == 0:
            score += 0.2
        elif diff == 1:
            score += 0.1
        else:
            score -= 0.2

    # 集数一致小幅加分
    if a.episodes and b.episodes and a.episodes == b.episodes:
        score += 0.1

    return max(0.0, min(1.0, score))


def match_candidates(anchor: Candidate, pool: list[Candidate],
                     threshold: float = 0.7) -> Candidate | None:
    """从 pool 中挑出与 anchor 最匹配且超过阈值的一条；都不够则 None。"""
    best: Candidate | None = None
    best_score = 0.0
    for cand in pool:
        if cand.source == anchor.source and cand.source_id == anchor.source_id:
            continue
        s = score_match(anchor, cand)
        if s > best_score:
            best, best_score = cand, s
    return best if best_score >= threshold else None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_identity.py -q`
Expected: PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/identity.py backend/tests/test_identity.py
git commit -m "feat(identity): 番剧身份归并（标题归一化+年份+集数，含误合并防护）"
```

---

## Task 6: 分歧引擎 —— 基础计算

**Files:**
- Create: `backend/app/services/divergence.py`
- Test: `backend/tests/test_divergence.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_divergence.py`：

```python
"""分歧引擎纯函数测试（规格 §6.1–§6.3）。"""
import math

import pytest

from app.services.divergence import (bayesian_shrink, classify_quadrant,
                                     normalize_rating, polarity, weighted_std)


def test_normalize_10_scale_is_identity() -> None:
    assert normalize_rating(8.6, 10) == pytest.approx(8.6)


def test_normalize_100_scale_to_10() -> None:
    assert normalize_rating(86.0, 100) == pytest.approx(8.6)


def test_normalize_rejects_bad_scale() -> None:
    with pytest.raises(ValueError):
        normalize_rating(5.0, 0)


def test_bayesian_shrink_pulls_small_sample_toward_prior() -> None:
    """小样本被拉向 C；大样本几乎不动。"""
    small = bayesian_shrink(9.5, v=10, c=7.0, m=500)
    large = bayesian_shrink(9.5, v=100000, c=7.0, m=500)
    assert small < large
    assert small == pytest.approx((10 * 9.5 + 500 * 7.0) / 510)
    assert large == pytest.approx(9.5, abs=0.02)


def test_bayesian_shrink_zero_count_returns_prior() -> None:
    assert bayesian_shrink(9.9, v=0, c=7.0, m=500) == pytest.approx(7.0)


def test_weighted_std_matches_plain_std_when_weights_equal() -> None:
    vals = [8.0, 9.0, 10.0]
    assert weighted_std(vals, [1, 1, 1]) == pytest.approx(
        statistics_pstdev(vals))


def test_weighted_std_downweights_low_confidence_site() -> None:
    """低权重站点对分歧的贡献更小 —— 权重必须真的起作用。"""
    vals, w_low = [5.0, 9.0], [0.5, 1.0]
    vals2, w_eq = [5.0, 9.0], [1.0, 1.0]
    assert weighted_std(vals, w_low) < weighted_std(vals2, w_eq)


def test_weighted_std_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError):
        weighted_std([8.0], [0.0])


def test_polarity_range() -> None:
    assert polarity(10, 0) == pytest.approx(1.0)
    assert polarity(0, 10) == pytest.approx(-1.0)
    assert polarity(5, 5) == pytest.approx(0.0)
    assert polarity(0, 0) == pytest.approx(0.0)


def test_classify_quadrant_all_four() -> None:
    assert classify_quadrant(0.1, 0.05, 0.5, 0.2) == "consensus"
    assert classify_quadrant(0.1, 0.30, 0.5, 0.2) == "hidden_controversy"
    assert classify_quadrant(0.9, 0.05, 0.5, 0.2) == "scale_bias"
    assert classify_quadrant(0.9, 0.30, 0.5, 0.2) == "full_controversy"


def test_classify_quadrant_boundary_is_inclusive_low() -> None:
    """阈值上等于低位（< 判低）。"""
    assert classify_quadrant(0.5, 0.2, 0.5, 0.2) == "full_controversy"


def statistics_pstdev(vals: list[float]) -> float:
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_divergence.py -q`
Expected: FAIL — `No module named 'app.services.divergence'`

- [ ] **Step 3: 实现基础计算**

创建 `backend/app/services/divergence.py`：

```python
"""跨站口碑分歧引擎（规格 §6）。

分层：本模块前半是纯函数（易测），后半是站点筛选与结果汇总。
"""
import math
from dataclasses import dataclass, field

# 象限取值
CONSENSUS = "consensus"                     # 共识番
HIDDEN_CONTROVERSY = "hidden_controversy"   # 分数掩盖了争议
SCALE_BIAS = "scale_bias"                   # 打分习惯差异
FULL_CONTROVERSY = "full_controversy"       # 全面争议


def normalize_rating(raw: float, scale: float) -> float:
    """把任意分制归一到 10 分制。"""
    if scale <= 0:
        raise ValueError("rating_scale 必须为正数")
    return float(raw) * (10.0 / float(scale))


def bayesian_shrink(r_norm: float, v: int, c: float, m: int = 500) -> float:
    """IMDB 加权：小样本向先验 C 收缩（规格 §6.1）。

    R_weighted = (v·R + m·C) / (v + m)
    """
    if v < 0:
        raise ValueError("评分人数不得为负")
    if m < 0:
        raise ValueError("先验权重不得为负")
    return (v * float(r_norm) + m * float(c)) / (v + m)


def weighted_std(values: list[float], weights: list[float]) -> float:
    """加权标准差 σ_w = sqrt( Σw(x−x̄w)² / Σw )（规格 §6.2）。"""
    if len(values) != len(weights):
        raise ValueError("values 与 weights 长度必须一致")
    total = sum(weights)
    if total <= 0:
        raise ValueError("权重之和必须为正")
    mean = sum(w * x for w, x in zip(weights, values)) / total
    var = sum(w * (x - mean) ** 2 for w, x in zip(weights, values)) / total
    return math.sqrt(var)


def polarity(pos: int, neg: int) -> float:
    """情感极性 ∈ [−1, 1]；无评论返回 0。"""
    n = int(pos) + int(neg)
    if n <= 0:
        return 0.0
    return (int(pos) - int(neg)) / n


def classify_quadrant(d_rating: float, d_sent: float,
                      thr_r: float, thr_s: float) -> str:
    """四象限判定（规格 §6.3）。阈值处取"低位"（< 为低）。"""
    r_low = d_rating < thr_r
    s_low = d_sent < thr_s
    if r_low and s_low:
        return CONSENSUS
    if r_low and not s_low:
        return HIDDEN_CONTROVERSY
    if not r_low and s_low:
        return SCALE_BIAS
    return FULL_CONTROVERSY
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_divergence.py -q`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/divergence.py backend/tests/test_divergence.py
git commit -m "feat(divergence): 分歧引擎基础计算（归一化/贝叶斯收缩/加权标准差/象限）"
```

---

## Task 7: 分歧引擎 —— 门槛与结果汇总

**Files:**
- Modify: `backend/app/services/divergence.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_divergence_compute.py`

- [ ] **Step 1: 加配置项**

在 `backend/app/config.py` 末尾追加：

```python
# —— 动漫跨站分歧（规格 §6.3 / §6.4）——
ANIME_THR_R = float(os.getenv("ANIME_THR_R", "0.5"))     # 评分分歧阈值（10分制标准差）
ANIME_THR_S = float(os.getenv("ANIME_THR_S", "0.2"))     # 情感分歧阈值（极性标准差）
ANIME_BAYES_M = int(os.getenv("ANIME_BAYES_M", "500"))   # 贝叶斯先验权重
ANIME_MIN_RATING_COUNT = int(os.getenv("ANIME_MIN_RATING_COUNT", "100"))  # 低于此降权
ANIME_MIN_REVIEWS = int(os.getenv("ANIME_MIN_REVIEWS", "30"))             # 低于此不参与情感
ANIME_LOW_CONF_WEIGHT = float(os.getenv("ANIME_LOW_CONF_WEIGHT", "0.5"))  # 降权权重
```

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_divergence_compute.py`：

```python
"""分歧引擎站点筛选与汇总测试（规格 §6.2 / §6.4）。"""
import pytest

from app.services.divergence import (CONSENSUS, HIDDEN_CONTROVERSY,
                                     SCALE_BIAS, SourceStat, compute_divergence)


def _cfg() -> dict:
    return dict(thr_r=0.5, thr_s=0.2, m=500, min_rating_count=100,
                min_reviews=30, low_conf_weight=0.5)


def test_two_sources_ok() -> None:
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=90, neg=10, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.status == "ok"
    assert r.d_rating is not None and r.d_rating > 0
    assert r.d_sentiment is not None
    assert r.quadrant in (CONSENSUS, HIDDEN_CONTROVERSY, SCALE_BIAS, "full_controversy")


def test_single_source_is_insufficient() -> None:
    """只有一个可用站点时不出结论（规格 §6.4）。"""
    stats = [SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                        pos=80, neg=20, review_count=100)]
    r = compute_divergence(stats, **_cfg())
    assert r.status == "insufficient_data"
    assert r.d_rating is None
    assert "站点" in r.reason


def test_no_rating_sites_excluded_from_d_rating() -> None:
    """无评分的站点不进 D_rating，但要能出情感分歧。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=20, neg=80, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert set(r.sources_rating) == {"bangumi", "bilibili"}
    assert set(r.sources_sentiment) == {"bangumi", "bilibili"}


def test_few_reviews_excluded_from_sentiment() -> None:
    """评论数不足的站点不参与情感分歧（规格 §6.4）。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.6, rating_count=12000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=98000,
                   pos=20, neg=80, review_count=5),      # 评论太少
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.sources_sentiment == ["bangumi"]
    assert r.d_sentiment is None          # 情感只剩一个站 → 算不出
    assert r.d_rating is not None         # 评分仍可算
    assert r.status == "ok"               # 只要有一个指标算得出就算 ok


def test_low_rating_count_gets_reduced_weight() -> None:
    """评分人数不足的站点权重被降低（规格 §6.4）。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.0, rating_count=50000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=4.0, rating_count=10,
                   pos=80, neg=20, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    weights = {x["source"]: x["weight"] for x in r.ratings}
    assert weights["bilibili"] == pytest.approx(0.5)
    assert weights["bangumi"] == pytest.approx(1.0)


def test_hidden_controversy_detected() -> None:
    """评分接近但情感两极 → 分数掩盖了争议。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=8.5, rating_count=20000,
                   pos=95, neg=5, review_count=100),
        SourceStat(source="bilibili", rating_norm=8.5, rating_count=20000,
                   pos=5, neg=95, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.quadrant == HIDDEN_CONTROVERSY


def test_scale_bias_detected() -> None:
    """评分差距大但情感一致 → 打分习惯差异。"""
    stats = [
        SourceStat(source="bangumi", rating_norm=4.0, rating_count=20000,
                   pos=80, neg=20, review_count=100),
        SourceStat(source="bilibili", rating_norm=9.5, rating_count=20000,
                   pos=80, neg=20, review_count=100),
    ]
    r = compute_divergence(stats, **_cfg())
    assert r.quadrant == SCALE_BIAS
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_divergence_compute.py -q`
Expected: FAIL — `ImportError: cannot import name 'SourceStat'`

- [ ] **Step 4: 实现门槛与汇总**

在 `backend/app/services/divergence.py` 末尾追加：

```python
@dataclass
class SourceStat:
    """单个站点参与计算所需的统计量。"""
    source: str
    rating_norm: float | None = None      # 已归一化到 10 分制
    rating_count: int | None = None
    pos: int | None = None
    neg: int | None = None
    review_count: int | None = None


@dataclass
class DivergenceResult:
    status: str                                  # ok | insufficient_data
    d_rating: float | None = None
    d_sentiment: float | None = None
    quadrant: str | None = None
    sources_rating: list[str] = field(default_factory=list)
    sources_sentiment: list[str] = field(default_factory=list)
    ratings: list[dict] = field(default_factory=list)     # [{source, rating_weighted, weight}]
    sentiment: list[dict] = field(default_factory=list)   # [{source, mean, pos, neg, review_count}]
    reason: str | None = None


def compute_divergence(stats: list[SourceStat], *, thr_r: float, thr_s: float,
                       m: int, min_rating_count: int, min_reviews: int,
                       low_conf_weight: float = 0.5) -> DivergenceResult:
    """按规格 §6.2–§6.4 汇总分歧结果。

    两个指标的参与站点集合可以不同：
      - 无评分的站点不进 D_rating
      - 评论数 < min_reviews 的站点不进 D_sent
    """
    # —— 评分侧 ——
    rated = [s for s in stats if s.rating_norm is not None]
    sources_rating: list[str] = []
    ratings: list[dict] = []
    d_rating: float | None = None

    # 先验 C = 各站 R_norm 的均值（规格 §6.1）
    c = (sum(s.rating_norm for s in rated) / len(rated)) if rated else 0.0
    if len(rated) >= 2:
        vals, weights = [], []
        for s in rated:
            v = int(s.rating_count or 0)
            w = low_conf_weight if v < min_rating_count else 1.0
            rw = bayesian_shrink(s.rating_norm, v, c, m)
            vals.append(rw)
            weights.append(w)
            sources_rating.append(s.source)
            ratings.append({"source": s.source, "rating_weighted": round(rw, 4),
                            "weight": w})
        d_rating = weighted_std(vals, weights)

    # —— 情感侧 ——
    reviewed = [s for s in stats if int(s.review_count or 0) >= min_reviews]
    sources_sentiment: list[str] = []
    sentiment: list[dict] = []
    d_sent: float | None = None
    if len(reviewed) >= 2:
        vals, weights = [], []
        for s in reviewed:
            p = polarity(int(s.pos or 0), int(s.neg or 0))
            w = 1.0
            # 评分人数不足的站点在情感侧同样降权（若其有评分）
            if s.rating_count is not None and int(s.rating_count) < min_rating_count:
                w = low_conf_weight
            vals.append(p)
            weights.append(w)
            sources_sentiment.append(s.source)
            sentiment.append({"source": s.source, "mean": round(p, 4),
                              "pos": int(s.pos or 0), "neg": int(s.neg or 0),
                              "review_count": int(s.review_count or 0)})
        d_sent = weighted_std(vals, weights)

    if d_rating is None and d_sent is None:
        return DivergenceResult(
            status="insufficient_data",
            reason=f"可用站点不足：评分 {len(rated)} 个、情感 {len(reviewed)} 个，均少于 2")

    quadrant = None
    if d_rating is not None and d_sent is not None:
        quadrant = classify_quadrant(d_rating, d_sent, thr_r, thr_s)

    return DivergenceResult(
        status="ok",
        d_rating=round(d_rating, 4) if d_rating is not None else None,
        d_sentiment=round(d_sent, 4) if d_sent is not None else None,
        quadrant=quadrant,
        sources_rating=sources_rating,
        sources_sentiment=sources_sentiment,
        ratings=ratings,
        sentiment=sentiment,
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_divergence_compute.py -q`
Expected: PASS（7 passed）

- [ ] **Step 6: 跑分歧引擎全部测试**

Run: `cd backend && python3 -m pytest tests/test_divergence.py tests/test_divergence_compute.py -q`
Expected: 全部通过

- [ ] **Step 7: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/divergence.py backend/app/config.py \
        backend/tests/test_divergence_compute.py
git commit -m "feat(divergence): 站点参与门槛与结果汇总（评分/情感集合可不同）"
```

---

## Task 8: 分站独有词归因

**Files:**
- Modify: `backend/app/services/nlp.py`
- Test: `backend/tests/test_source_terms.py`

- [ ] **Step 1: 看现有 nlp 接口**

Run: `cd backend && sed -n '1,40p' app/services/nlp.py`
确认 `build_hotspot` 的签名与返回结构，新函数与之保持风格一致。

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_source_terms.py`：

```python
"""分站独有词归因测试（规格 §6.5）。"""
from app.services.nlp import build_source_terms


def test_finds_site_specific_terms() -> None:
    docs = {
        "bangumi": ["作画太棒了 作画 作画 神作", "作画精良 剧情好"],
        "bilibili": ["作画太棒了 打斗 打斗 打斗 燃"],
    }
    out = build_source_terms(docs, top_n=3)
    assert "bangumi" in out and "bilibili" in out
    bangumi_words = [t["word"] for t in out["bangumi"]["top_pos"] + out["bangumi"]["top_neg"]]
    bili_words = [t["word"] for t in out["bilibili"]["top_pos"] + out["bilibili"]["top_neg"]]
    # "打斗" 是 B站独有 → 不应出现在 bangumi 的独有词里
    assert "打斗" not in bangumi_words
    assert "打斗" in bili_words


def test_empty_input_returns_empty() -> None:
    assert build_source_terms({}, top_n=5) == {}


def test_single_source_returns_empty_terms() -> None:
    """只有一个站时没有"独有"可言。"""
    out = build_source_terms({"bangumi": ["好看 好看"]}, top_n=5)
    assert out == {} or out.get("bangumi", {}).get("top_pos") == []
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_source_terms.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_source_terms'`

- [ ] **Step 4: 实现**

在 `backend/app/services/nlp.py` 末尾追加（复用文件内已有的分词与褒贬词工具；若文件中褒贬词表变量名不同，按其实际名称取用）：

```python
def build_source_terms(docs: dict[str, list[str]], top_n: int = 15) -> dict:
    """分站独有高频褒贬词（规格 §6.5）。

    docs: {source: [评论文本, ...]}
    返回: {source: {"top_pos": [{"word","freq","score"}], "top_neg": [...]}}
    只有一个站点时返回 {}（无"独有"可言）。
    """
    if len(docs) < 2:
        return {}

    # 每站的词频
    freq_by_source: dict[str, Counter] = {}
    for src, texts in docs.items():
        c: Counter = Counter()
        for t in texts:
            for w in _tokenize(t):
                if len(w) >= 2:          # 单字噪声大
                    c[w] += 1
        freq_by_source[src] = c

    # 全局词频（用于判断"独有"）
    total: Counter = Counter()
    for c in freq_by_source.values():
        total.update(c)

    out: dict[str, dict] = {}
    for src, c in freq_by_source.items():
        others = Counter()
        for other_src, oc in freq_by_source.items():
            if other_src != src:
                others.update(oc)

        # 独有度 = 本站频次 × 其他站均频次的倒数
        scored: list[tuple[str, float, int]] = []
        for w, n in c.items():
            if n < 2:
                continue
            other_avg = others.get(w, 0) / max(1, len(freq_by_source) - 1)
            if other_avg > 0 and n <= other_avg:
                continue                          # 别的站也这么说 → 不算独有
            distinct = n / (1.0 + other_avg)
            scored.append((w, distinct, n))
        scored.sort(key=lambda x: x[1], reverse=True)

        pos, neg = [], []
        for w, distinct, n in scored[:top_n * 3]:
            item = {"word": w, "freq": n, "score": round(distinct, 3)}
            if w in _NEG_WORDS:
                neg.append(item)
            elif w in _POS_WORDS:
                pos.append(item)
            else:
                pos.append(item)                  # 未登录词默认归入展示位
            if len(pos) >= top_n and len(neg) >= top_n:
                break

        out[src] = {"top_pos": pos[:top_n], "top_neg": neg[:top_n]}
    return out
```

在文件顶部确保有：

```python
from collections import Counter
```

> **注意**：`_tokenize`、`_POS_WORDS`、`_NEG_WORDS` 是本计划假设的内部名。**执行时先读 `app/services/nlp.py`，按文件中实际存在的分词函数与褒贬词表名称替换**；若褒贬词表不存在，则用 `app/services/analytics.py` 中已有的倾向词资源，或在该文件内新建一个最小词表（≥30 个动漫常用褒贬词即可）。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_source_terms.py -q`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/services/nlp.py backend/tests/test_source_terms.py
git commit -m "feat(nlp): 分站独有褒贬词归因 build_source_terms"
```

---

## Task 9: 动漫语料采集与训练集构建

**Files:**
- Create: `backend/scripts/collect_anime_corpus.py`
- Test: 手动运行验证（脚本类，无单测）

- [ ] **Step 1: 实现脚本**

创建 `backend/scripts/collect_anime_corpus.py`：

```python
"""采集两站动漫评论，按评分自动标注，输出训练集 CSV（规格 §9 v1-步骤4）。

用法：
    cd backend
    python scripts/collect_anime_corpus.py --titles 进击的巨人 鬼灭之刃 ... \
        --limit 200 --out data/anime_train.csv
"""
import argparse
import csv
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services.adapters import get_adapter          # noqa: E402
from app.services.identity import normalize_title      # noqa: E402

# 评分 → 标签映射（B站/豆瓣 5 星制）
POS_MIN = 4      # 4-5 星 → positive
NEG_MAX = 2      # 1-2 星 → negative
                 # 3 星丢弃（中性，与二类口径不符）


def label_of(stars: int | None) -> str | None:
    if stars is None:
        return None
    if stars >= POS_MIN:
        return "positive"
    if stars <= NEG_MAX:
        return "negative"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", nargs="+", required=True, help="番剧名列表")
    ap.add_argument("--sources", nargs="+", default=["bangumi", "bilibili"])
    ap.add_argument("--limit", type=int, default=200, help="每部每站抓取条数")
    ap.add_argument("--out", default="data/anime_train.csv")
    args = ap.parse_args()

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    seen: set[str] = set()

    for title in args.titles:
        for src in args.sources:
            adapter = get_adapter(src)
            if adapter is None:
                print(f"[跳过] 未实现站点 {src}")
                continue

            res = adapter.search(title)
            if not res.ok:
                print(f"[失败] {src} 检索《{title}》：{res.error}")
                continue
            if not res.data:
                print(f"[空] {src} 检索《{title}》无结果")
                continue

            cand = res.data[0]
            print(f"[检索] {src} 《{cand.title_cn}》 id={cand.source_id}")

            rr = adapter.fetch_reviews(cand.source_id, args.limit)
            if not rr.ok:
                print(f"[失败] {src} 抓评论：{rr.error}")
                continue
            if rr.status == "degraded":
                print(f"[降级] {src}：{rr.error}")
            for item in rr.data:
                text = (item.text or "").strip()
                if not text or len(text) < 8:      # 过短无信息量
                    continue
                key = normalize_title(text[:40])
                if key in seen:
                    continue
                seen.add(key)
                lab = label_of(item.stars)
                if lab is None:
                    continue
                rows.append({"text": text, "label": lab, "source": src,
                             "stars": item.stars, "movie": cand.title_cn})
            time.sleep(1.0)                        # 低频礼貌

    if not rows:
        print("未采集到任何可用样本 —— 检查 cookie / 网络 / 站点可用性")
        return 1

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["text", "label", "source", "stars", "movie"])
        w.writeheader()
        w.writerows(rows)

    pos = sum(1 for r in rows if r["label"] == "positive")
    print(f"已写入 {out_path}：共 {len(rows)} 条（正 {pos} / 负 {len(rows) - pos}）")
    if min(pos, len(rows) - pos) < 200:
        print("[警告] 某一类样本少于 200，模型可能偏斜 —— 建议再抓几部")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行验证**

Run: `cd backend && python3 scripts/collect_anime_corpus.py --titles 进击的巨人 鬼灭之刃 紫罗兰永恒花园 --limit 100 --out data/anime_train.csv`
Expected: 打印检索/抓取进度，最后写出 CSV 并统计正负样本数。**若 B站因无 cookie 降级为 0 条，只靠 Bangumi 也可，但样本量可能不足——此时增加 `--titles` 数量。**

- [ ] **Step 3: 检查产物**

Run: `cd backend && python3 -c "import csv; rows=list(csv.DictReader(open('data/anime_train.csv',encoding='utf-8'))); print(len(rows)); print(rows[:2])"`
Expected: 打印条数与前两条样本

- [ ] **Step 4: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/scripts/collect_anime_corpus.py
git commit -m "feat(scripts): 动漫语料采集与自动标注（按星级建二类训练集）"
```

---

## Task 10: 动漫领域中文模型训练

**Files:**
- Create: `backend/scripts/train_textcnn_anime.py`
- Modify: `backend/app/config.py`（模型路径可配）

- [ ] **Step 1: 先读现有训练脚本**

Run: `cd backend && sed -n '1,60p' scripts/train_textcnn_zh.py`
确认其 CSV 列名、分词方式、模型结构与导出格式（`models/zh/model_zh.pt`）。**新脚本复用同一模型结构，只换数据与导出路径**，避免推理端不兼容。

- [ ] **Step 2: 实现训练脚本**

复制 `scripts/train_textcnn_zh.py` 为 `scripts/train_textcnn_anime.py`，改动三处：

1. 默认 `--csv` 改为 `data/anime_train.csv`；
2. 默认 `--out` 改为 `models/anime/model_anime.pt`；
3. 文件头 docstring 改为动漫域说明。

其余（分词、TextCNN 结构、留存集划分、准确率断言、导出格式）**保持不变**，确保 `app/services/textcnn_zh.py` 的加载器可直接读取。

- [ ] **Step 3: 训练并验证准确率**

Run: `cd backend && python3 scripts/train_textcnn_anime.py --csv data/anime_train.csv --epochs 8 --max_len 128 --out models/anime/model_anime.pt`
Expected: 训练过程打印 loss/acc，末尾打印留存集准确率。**若 < 85%，增加 Task 9 的抓取量或提升 epochs 后重跑。**

- [ ] **Step 4: 确认产物可被加载**

Run: `cd backend && python3 -c "
import torch
ck = torch.load('models/anime/model_anime.pt', map_location='cpu')
print(sorted(ck.keys()))
print('vocab size:', len(ck.get('vocab', {})))
"`
Expected: 打印 `['config', 'model', 'vocab']`（或与 `model_zh.pt` 相同的键），vocab 非空

- [ ] **Step 5: 加配置项指向新模型**

在 `backend/app/config.py` 追加：

```python
# 动漫域中文情感模型（Task 10 产物）
ANIME_MODEL_PATH = _abs(os.getenv("ANIME_MODEL_PATH",
                                  str(BASE_DIR / "models" / "anime" / "model_anime.pt")))
```

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/scripts/train_textcnn_anime.py backend/app/config.py
git commit -m "feat(model): 动漫领域中文 TextCNN 训练脚本与模型路径配置"
```

> 模型权重 `models/anime/model_anime.pt` 按仓库约定**不入库**（`.gitignore` 已排除 `*.pt`），单独共享给队友。

---

## Task 11: `/anime/search` 接口

**Files:**
- Create: `backend/app/routers/anime.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_anime_api.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_anime_api.py`：

```python
"""动漫接口测试（规格 §7）。"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.adapters.base import Candidate, ok

client = TestClient(app)


def test_search_merges_sources(monkeypatch) -> None:
    from app.routers import anime as anime_router

    class FakeAdapter:
        def __init__(self, source):
            self.source = source
        def search(self, query):
            if self.source == "bangumi":
                return ok("bangumi", [Candidate(source="bangumi", source_id="253",
                                                title_cn="进击的巨人", year=2013)])
            return ok("bilibili", [Candidate(source="bilibili", source_id="4450",
                                             title_cn="进击的巨人", year=2013)])

    monkeypatch.setattr(anime_router, "get_adapter", lambda s: FakeAdapter(s))

    r = client.get("/anime/search", params={"q": "进击的巨人",
                                            "sources": "bangumi,bilibili"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert items[0]["title_cn"] == "进击的巨人"
    assert {s["source"] for s in items[0]["sources"]} == {"bangumi", "bilibili"}


def test_search_reports_source_failure(monkeypatch) -> None:
    """单站失败不应让整个检索 500，而是如实报告。"""
    from app.routers import anime as anime_router
    from app.services.adapters.base import failed

    class FailAdapter:
        source = "bangumi"
        def search(self, query):
            return failed("bangumi", "HTTP 429", http_status=429)

    monkeypatch.setattr(anime_router, "get_adapter", lambda s: FailAdapter())

    r = client.get("/anime/search", params={"q": "任意", "sources": "bangumi"})
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["errors"]
    assert "429" in body["errors"][0]["reason"]


def test_search_rejects_unknown_source(monkeypatch) -> None:
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: None)
    r = client.get("/anime/search", params={"q": "任意", "sources": "mal"})
    assert r.status_code == 200
    assert r.json()["errors"][0]["source"] == "mal"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_anime_api.py -q`
Expected: FAIL — 404（路由不存在）

- [ ] **Step 3: 实现路由**

创建 `backend/app/routers/anime.py`：

```python
"""动漫域路由：跨站检索 / 采集 / 单番各站数据（规格 §7）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..services.adapters import get_adapter
from ..services.identity import match_candidates, score_match

router = APIRouter(prefix="/anime", tags=["anime"])

MATCH_THRESHOLD = 0.7


@router.get("/search")
def search(q: str, sources: str = "bangumi,bilibili",
           db: Session = Depends(get_db)) -> dict:
    """跨站检索并按归并结果聚合候选番剧。"""
    wanted = [s.strip() for s in sources.split(",") if s.strip()]
    per_source: dict[str, list] = {}
    errors: list[dict] = []

    for src in wanted:
        adapter = get_adapter(src)
        if adapter is None:
            errors.append({"source": src, "reason": "v1 未实现该站点"})
            continue
        res = adapter.search(q)
        if not res.ok:
            errors.append({"source": src, "reason": res.error})
            continue
        per_source[src] = list(res.data or [])

    # 以第一个有结果的站点为锚点，其余站点按归并匹配并入
    items: list[dict] = []
    anchor_src = next((s for s in wanted if per_source.get(s)), None)
    if anchor_src:
        for anchor in per_source[anchor_src]:
            group = [{"source": anchor.source, "source_id": anchor.source_id,
                      "title": anchor.title_cn, "year": anchor.year,
                      "url": anchor.url}]
            for other in wanted:
                if other == anchor_src:
                    continue
                match = match_candidates(anchor, per_source.get(other, []),
                                         threshold=MATCH_THRESHOLD)
                if match:
                    group.append({"source": match.source, "source_id": match.source_id,
                                  "title": match.title_cn, "year": match.year,
                                  "url": match.url})
                    per_source[other] = [c for c in per_source[other]
                                         if c.source_id != match.source_id]
            items.append({
                "anime_id": None,           # 尚未入库；ingest 后分配
                "title_cn": anchor.title_cn,
                "title_jp": anchor.title_jp,
                "title_en": anchor.title_en,
                "year": anchor.year,
                "episodes": anchor.episodes,
                "sources": group,
            })

    return {"items": items, "errors": errors}
```

- [ ] **Step 4: 注册路由**

在 `backend/app/main.py` 中，仿照现有 router 的注册方式加入：

```python
from .routers import anime as anime_router
app.include_router(anime_router.router)
```

（**执行时先读 `app/main.py`，按其中已有的 include_router 写法对齐。**）

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_anime_api.py -q`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/routers/anime.py backend/app/main.py backend/tests/test_anime_api.py
git commit -m "feat(api): GET /anime/search 跨站检索与归并聚合"
```

---

## Task 12: `/anime/ingest` 接口

**Files:**
- Modify: `backend/app/routers/anime.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_anime_api.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_anime_api.py` 追加：

```python
def test_ingest_creates_job_and_anime_rows(monkeypatch) -> None:
    """发起采集：应建 Anime/AnimeSource 记录并返回 job_id。"""
    from app.routers import anime as anime_router
    from app.services.adapters.base import Candidate, Meta, Rating, ok

    class FakeAdapter:
        def __init__(self, source):
            self.source = source
        def search(self, query):
            return ok(self.source, [Candidate(source=self.source, source_id=f"{self.source}-1",
                                              title_cn="进击的巨人", year=2013)])
        def fetch_meta(self, sid):
            return ok(self.source, Meta(title_cn="进击的巨人", title_jp="進撃の巨人", year=2013))
        def fetch_rating(self, sid):
            return ok(self.source, Rating(score_raw=8.6, scale=10.0, count=1000))
        def fetch_reviews(self, sid, limit=200):
            return ok(self.source, [])

    monkeypatch.setattr(anime_router, "get_adapter", lambda s: FakeAdapter(s))

    r = client.post("/anime/ingest", json={"title": "进击的巨人",
                                           "sources": ["bangumi", "bilibili"],
                                           "limit": 50})
    assert r.status_code == 201
    body = r.json()
    assert body["job_id"]
    assert body["anime_id"]

    from app import models
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        anime = db.get(models.Anime, body["anime_id"])
        assert anime is not None
        assert anime.title_jp == "進撃の巨人"
        srcs = db.query(models.AnimeSource).filter_by(anime_id=body["anime_id"]).all()
        assert {s.source for s in srcs} == {"bangumi", "bilibili"}
        assert all(s.rating_raw == 8.6 for s in srcs)
    finally:
        db.close()


def test_ingest_without_source_returns_400(monkeypatch) -> None:
    from app.routers import anime as anime_router
    monkeypatch.setattr(anime_router, "get_adapter", lambda s: None)
    r = client.post("/anime/ingest", json={"title": "任意", "sources": ["mal"]})
    assert r.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_anime_api.py -q -k ingest`
Expected: FAIL — 404

- [ ] **Step 3: 实现 ingest**

在 `backend/app/routers/anime.py` 追加（并在文件顶部补 `import uuid`, `from datetime import datetime`, `from fastapi import HTTPException`, `from pydantic import BaseModel, Field`）：

```python
class IngestIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    year: int | None = None
    sources: list[str] = Field(default_factory=lambda: ["bangumi", "bilibili"])
    limit: int = Field(200, ge=1, le=1000)
    refresh: bool = False


ANCHOR_PRIORITY = ["bangumi", "bilibili"]


@router.post("/ingest", status_code=201)
def ingest(body: IngestIn, db: Session = Depends(get_db)) -> dict:
    """跨站采集一部番：建 Anime/AnimeSource，落 CrawlJob 供轮询。"""
    found: list[tuple[str, object]] = []       # (source, Candidate)
    for src in body.sources:
        adapter = get_adapter(src)
        if adapter is None:
            raise HTTPException(400, f"v1 未实现站点：{src}")
        res = adapter.search(body.title)
        if not res.ok:
            raise HTTPException(502, f"{src} 检索失败：{res.error}")
        for cand in (res.data or []):
            if body.year and cand.year and abs(cand.year - body.year) > 1:
                continue
            found.append((src, cand))
            break

    if not found:
        raise HTTPException(404, "各站均未检索到该番剧")

    # 锚点站点决定 anime_id（规格 §5.1）
    found.sort(key=lambda x: ANCHOR_PRIORITY.index(x[0])
               if x[0] in ANCHOR_PRIORITY else 99)
    anchor_src, anchor = found[0]
    anime_id = f"{anchor_src}:{anchor.source_id}"

    anime = db.get(models.Anime, anime_id)
    if anime is None:
        anime = models.Anime(anime_id=anime_id)
        db.add(anime)

    for src, cand in found:
        adapter = get_adapter(src)
        meta_res = adapter.fetch_meta(cand.source_id)
        if meta_res.ok and meta_res.data:
            m = meta_res.data
            anime.title_cn = anime.title_cn or m.title_cn or cand.title_cn
            anime.title_jp = anime.title_jp or m.title_jp
            anime.title_en = anime.title_en or m.title_en
            anime.year = anime.year or m.year
            anime.episodes = anime.episodes or m.episodes
            anime.studio = anime.studio or m.studio
            anime.synopsis = anime.synopsis or m.synopsis
            anime.poster_url = anime.poster_url or m.poster_url

        row = db.query(models.AnimeSource).filter_by(anime_id=anime_id, source=src).first()
        if row is None:
            row = models.AnimeSource(anime_id=anime_id, source=src,
                                     source_id=cand.source_id)
            db.add(row)
        row.url = cand.url
        rr = adapter.fetch_rating(cand.source_id)
        if rr.ok and rr.data:
            row.rating_raw = rr.data.score_raw
            row.rating_scale = rr.data.scale
            row.rating_count = rr.data.count
        row.fetched_at = datetime.utcnow()

    job = models.CrawlJob(job_id=uuid.uuid4().hex, source=anchor_src,
                          query=body.title, limit=body.limit, refresh=body.refresh,
                          status="done", fetched=0,
                          error="基础数据已入库；评论采集由后续任务补充")
    db.add(job)
    db.commit()

    return {"job_id": job.job_id, "anime_id": anime_id,
            "sources": [s for s, _ in found]}
```

> 说明：v1 的 ingest 先完成**元数据与评分的入库**（同步、快），评论正文的批量采集沿用现有 `runner` 异步通道（后续任务接入）。这样 ingest 立刻可用、前端可立即展示分歧所需的评分数据。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_anime_api.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/routers/anime.py backend/tests/test_anime_api.py
git commit -m "feat(api): POST /anime/ingest 跨站采集入库（元数据+评分）"
```

---

## Task 13: `/anime/{id}/sources` 与 `/divergence/{id}` 接口

**Files:**
- Modify: `backend/app/routers/anime.py`
- Create: `backend/app/routers/divergence.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_divergence_api.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_divergence_api.py`：

```python
"""分歧接口测试（规格 §7）。"""
import json

from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app
from app.services.divergence import HIDDEN_CONTROVERSY, SCALE_BIAS

client = TestClient(app)


def _seed(anime_id: str = "bangumi:253", *, r1=8.5, r2=8.5,
          pos1=95, neg1=5, pos2=5, neg2=95) -> None:
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id=anime_id, title_cn="进击的巨人", year=2013))
        db.add(models.AnimeSource(anime_id=anime_id, source="bangumi",
                                  source_id="253", rating_raw=r1, rating_scale=10,
                                  rating_count=20000, review_count=100,
                                  sentiment_pos=pos1, sentiment_neg=neg1,
                                  sentiment_mean=0.9))
        db.add(models.AnimeSource(anime_id=anime_id, source="bilibili",
                                  source_id="4450", rating_raw=r2, rating_scale=10,
                                  rating_count=20000, review_count=100,
                                  sentiment_pos=pos2, sentiment_neg=neg2,
                                  sentiment_mean=-0.9))
        db.commit()
    finally:
        db.close()


def test_anime_sources_endpoint() -> None:
    _seed()
    r = client.get("/anime/bangumi:253/sources")
    assert r.status_code == 200
    body = r.json()
    assert body["anime"]["title_cn"] == "进击的巨人"
    assert {s["source"] for s in body["sources"]} == {"bangumi", "bilibili"}


def test_divergence_hidden_controversy() -> None:
    _seed(r1=8.5, r2=8.5, pos1=95, neg1=5, pos2=5, neg2=95)
    r = client.get("/divergence/bangumi:253")
    assert r.status_code == 200
    body = r.json()
    assert body["quadrant"] == HIDDEN_CONTROVERSY
    assert body["sources_used"]["rating"]
    assert body["sources_used"]["sentiment"]


def test_divergence_scale_bias() -> None:
    _seed(r1=4.0, r2=9.5, pos1=80, neg1=20, pos2=80, neg2=20)
    r = client.get("/divergence/bangumi:253")
    assert r.json()["quadrant"] == SCALE_BIAS


def test_divergence_404_for_unknown_anime() -> None:
    r = client.get("/divergence/bangumi:999999")
    assert r.status_code == 404


def test_divergence_insufficient_data_when_one_source() -> None:
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:1", title_cn="独站番"))
        db.add(models.AnimeSource(anime_id="bangumi:1", source="bangumi",
                                  source_id="1", rating_raw=8.0, rating_scale=10,
                                  rating_count=5000, review_count=50,
                                  sentiment_pos=10, sentiment_neg=5))
        db.commit()
    finally:
        db.close()

    r = client.get("/divergence/bangumi:1")
    assert r.status_code == 200
    assert r.json()["status"] == "insufficient_data"


def test_ranking_filters_by_quadrant() -> None:
    _seed(anime_id="bangumi:253", r1=8.5, r2=8.5, pos1=95, neg1=5, pos2=5, neg2=95)
    _seed(anime_id="bangumi:300", r1=4.0, r2=9.5, pos1=80, neg1=20, pos2=80, neg2=20)

    r = client.get("/ranking/divergence", params={"quadrant": HIDDEN_CONTROVERSY})
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["anime_id"] for i in items] == ["bangumi:253"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_divergence_api.py -q`
Expected: FAIL — 404

- [ ] **Step 3: 实现 `/anime/{id}/sources`**

在 `backend/app/routers/anime.py` 末尾追加：

```python
@router.get("/{anime_id}/sources")
def anime_sources(anime_id: str, db: Session = Depends(get_db)) -> dict:
    """单番各站原始数据（规格 §7）。"""
    anime = db.get(models.Anime, anime_id)
    if anime is None:
        raise HTTPException(404, "番剧不存在")
    rows = db.query(models.AnimeSource).filter_by(anime_id=anime_id).all()
    return {
        "anime": {
            "anime_id": anime.anime_id,
            "title_cn": anime.title_cn, "title_jp": anime.title_jp,
            "title_en": anime.title_en, "year": anime.year,
            "episodes": anime.episodes, "studio": anime.studio,
            "synopsis": anime.synopsis, "poster_url": anime.poster_url,
        },
        "sources": [{
            "source": s.source, "source_id": s.source_id, "url": s.url,
            "rating_raw": s.rating_raw, "rating_scale": s.rating_scale,
            "rating_count": s.rating_count, "rating_weighted": s.rating_weighted,
            "review_count": s.review_count,
            "sentiment": {"pos": s.sentiment_pos, "neg": s.sentiment_neg,
                          "mean": s.sentiment_mean},
            "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
        } for s in rows],
    }
```

- [ ] **Step 4: 实现分歧路由**

创建 `backend/app/routers/divergence.py`：

```python
"""分歧分析与分歧榜路由（规格 §7）。"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models
from ..db import get_db
from ..services.divergence import SourceStat, compute_divergence

router = APIRouter(tags=["divergence"])


def _stats_of(rows: list[models.AnimeSource]) -> list[SourceStat]:
    out: list[SourceStat] = []
    for s in rows:
        norm = None
        if s.rating_raw is not None and s.rating_scale:
            norm = s.rating_raw * (10.0 / s.rating_scale)
        out.append(SourceStat(
            source=s.source, rating_norm=norm, rating_count=s.rating_count,
            pos=s.sentiment_pos, neg=s.sentiment_neg, review_count=s.review_count))
    return out


def _compute(db: Session, anime_id: str):
    anime = db.get(models.Anime, anime_id)
    if anime is None:
        raise HTTPException(404, "番剧不存在")
    rows = db.query(models.AnimeSource).filter_by(anime_id=anime_id).all()
    return anime, rows, compute_divergence(
        _stats_of(rows),
        thr_r=config.ANIME_THR_R, thr_s=config.ANIME_THR_S, m=config.ANIME_BAYES_M,
        min_rating_count=config.ANIME_MIN_RATING_COUNT,
        min_reviews=config.ANIME_MIN_REVIEWS,
        low_conf_weight=config.ANIME_LOW_CONF_WEIGHT)


@router.get("/divergence/{anime_id}")
def divergence(anime_id: str, refresh: bool = False,
               db: Session = Depends(get_db)) -> dict:
    """单番分歧结果；命中缓存直接返回（规格 §11 第 5 条）。"""
    cached = db.get(models.Divergence, anime_id)
    if cached is not None and not refresh:
        payload = json.loads(cached.payload or "{}")
        payload["cached"] = True
        return payload

    anime, rows, result = _compute(db, anime_id)
    missing = [s.source for s in rows]
    payload = {
        "anime_id": anime_id,
        "title_cn": anime.title_cn,
        "status": result.status,
        "reason": result.reason,
        "d_rating": result.d_rating,
        "d_sentiment": result.d_sentiment,
        "quadrant": result.quadrant,
        "sources_used": {"rating": result.sources_rating,
                         "sentiment": result.sources_sentiment},
        "degraded": len(result.sources_rating) < len(missing),
        "ratings": result.ratings,
        "sentiment": result.sentiment,
        "attribution": {"per_source": {}},     # Task 16 接入 build_source_terms
        "computed_at": datetime.utcnow().isoformat(),
        "cached": False,
    }
    if result.status == "ok":
        row = cached or models.Divergence(anime_id=anime_id)
        row.d_rating = result.d_rating
        row.d_sentiment = result.d_sentiment
        row.quadrant = result.quadrant
        row.sources_rating = ",".join(result.sources_rating)
        row.sources_sentiment = ",".join(result.sources_sentiment)
        row.degraded = payload["degraded"]
        row.payload = json.dumps(payload, ensure_ascii=False)
        row.computed_at = datetime.utcnow()
        db.add(row)
        db.commit()
    return payload


@router.get("/ranking/divergence")
def ranking(quadrant: str | None = None, sort: str = "d_sentiment",
            limit: int = 20, offset: int = 0,
            db: Session = Depends(get_db)) -> dict:
    """分歧榜（规格 §7）。按需实时计算未缓存的番剧。"""
    stmt = select(models.Anime).limit(200)
    anime_rows = db.execute(stmt).scalars().all()

    items: list[dict] = []
    for a in anime_rows:
        cached = db.get(models.Divergence, a.anime_id)
        if cached is None:
            try:
                _, _, res = _compute(db, a.anime_id)
            except HTTPException:
                continue
            if res.status != "ok" or res.quadrant is None:
                continue
            cached = models.Divergence(
                anime_id=a.anime_id, d_rating=res.d_rating,
                d_sentiment=res.d_sentiment, quadrant=res.quadrant,
                sources_rating=",".join(res.sources_rating),
                sources_sentiment=",".join(res.sources_sentiment))
            db.add(cached)
            db.commit()
        if cached.quadrant is None:
            continue
        if quadrant and cached.quadrant != quadrant:
            continue
        items.append({
            "anime_id": a.anime_id, "title_cn": a.title_cn, "year": a.year,
            "d_rating": cached.d_rating, "d_sentiment": cached.d_sentiment,
            "quadrant": cached.quadrant,
        })

    key = sort if sort in ("d_rating", "d_sentiment") else "d_sentiment"
    items.sort(key=lambda x: (x[key] is None, -(x[key] or 0)))
    return {"total": len(items), "items": items[offset:offset + limit]}
```

- [ ] **Step 5: 注册路由**

在 `backend/app/main.py` 加入：

```python
from .routers import divergence as divergence_router
app.include_router(divergence_router.router)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_divergence_api.py -q`
Expected: PASS（6 passed）

- [ ] **Step 7: 跑全量测试**

Run: `cd backend && python3 -m pytest -q`
Expected: 全部通过

- [ ] **Step 8: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/routers/anime.py backend/app/routers/divergence.py \
        backend/app/main.py backend/tests/test_divergence_api.py
git commit -m "feat(api): /anime/{id}/sources、/divergence/{id} 与 /ranking/divergence"
```

---

## Task 14: 修复 `_get` 失败信息丢失（规格 §11）

**Files:**
- Modify: `backend/app/crawler/douban.py:202-223`
- Test: `backend/tests/test_douban_failure_logging.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_douban_failure_logging.py`：

```python
"""回归测试：豆瓣爬虫不得把失败伪装成"搜索无结果"（规格 §11 第 2 条）。"""
import logging

from app.crawler.douban import DoubanSource


class _Resp:
    def __init__(self, code):
        self.status_code = code
        self.text = ""


class _Session:
    def __init__(self, code):
        self.code = code
    def get(self, url, headers=None, **kw):
        return _Resp(self.code)


def test_get_logs_http_status_on_failure(monkeypatch, caplog) -> None:
    src = DoubanSource()
    monkeypatch.setattr(src, "_pick",
                        lambda: {"cookie": "", "session": _Session(403)})

    with caplog.at_level(logging.WARNING):
        out = src._get("https://example.invalid", {})

    assert out is None
    assert any("403" in r.message for r in caplog.records), \
        "失败必须记录状态码，否则无法区分『被拦』与『无结果』"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_douban_failure_logging.py -q`
Expected: FAIL — 无 403 日志记录

- [ ] **Step 3: 修改 `_get`**

将 `backend/app/crawler/douban.py` 的 `_get` 改为：

```python
    def _get(self, url: str, headers: dict, retries: int = 3) -> str | None:
        """带身份/代理轮换的 GET；403/429/异常做指数退避并换身份。

        失败必须留下日志：状态码是区分"被限流"与"确实无数据"的唯一线索。
        """
        last_code: int | None = None
        last_err: str | None = None
        for attempt in range(retries):
            ident = self._pick()
            req_headers = dict(headers)
            if ident["cookie"]:
                req_headers["Cookie"] = ident["cookie"]
            kwargs = {"timeout": 12}
            if self._proxies:
                proxy = random.choice(self._proxies)
                kwargs["proxies"] = {"http": proxy, "https": proxy}
            try:
                r = ident["session"].get(url, headers=req_headers, **kwargs)
                if r.status_code == 200:
                    return r.text
                last_code = r.status_code
                if r.status_code in (403, 429):
                    logger.warning(
                        "豆瓣请求被限流 url=%s status=%s 第 %d/%d 次尝试，退避后换身份重试",
                        url, r.status_code, attempt + 1, retries)
                    time.sleep(2 * (attempt + 1) + random.random() * 2)
                    continue
                logger.warning("豆瓣请求返回非 200 url=%s status=%s", url, r.status_code)
                return None
            except requests.RequestException as exc:
                last_err = str(exc)
                logger.warning("豆瓣请求异常 url=%s err=%s 第 %d/%d 次尝试",
                               url, exc, attempt + 1, retries)
                time.sleep(2 * (attempt + 1))

        logger.error("豆瓣请求最终失败 url=%s 最后状态码=%s 最后异常=%s",
                     url, last_code, last_err)
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_douban_failure_logging.py -q`
Expected: PASS

- [ ] **Step 5: 跑全量测试**

Run: `cd backend && python3 -m pytest -q`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/crawler/douban.py backend/tests/test_douban_failure_logging.py
git commit -m "fix(crawler): 豆瓣 _get 失败必须记录状态码，不再伪装成搜索无结果"
```

---

## Task 15: 阈值标定脚本

**Files:**
- Create: `backend/scripts/calibrate_thresholds.py`

- [ ] **Step 1: 实现脚本**

创建 `backend/scripts/calibrate_thresholds.py`：

```python
"""用真实数据分布标定象限阈值（规格 §6.3）。

用法：cd backend && python scripts/calibrate_thresholds.py --quantile 0.6
"""
import argparse
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import config, models                       # noqa: E402
from app.db import SessionLocal                      # noqa: E402
from app.routers.divergence import _compute          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quantile", type=float, default=0.6,
                    help="取分位数作为阈值初值（默认 0.6）")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        ids = [a.anime_id for a in db.query(models.Anime).limit(500).all()]
        if len(ids) < 5:
            print(f"已入库番剧仅 {len(ids)} 部，样本太少，先跑 /anime/ingest 多采几部")
            return 1

        dr, ds = [], []
        for aid in ids:
            try:
                _, _, res = _compute(db, aid)
            except Exception:
                continue
            if res.status == "ok":
                if res.d_rating is not None:
                    dr.append(res.d_rating)
                if res.d_sentiment is not None:
                    ds.append(res.d_sentiment)

        if len(dr) < 5 or len(ds) < 5:
            print(f"可用样本不足：评分分歧 {len(dr)} 条、情感分歧 {len(ds)} 条")
            return 1

        q = args.quantile
        thr_r = statistics.quantiles(dr, n=100)[int(q * 100) - 1]
        thr_s = statistics.quantiles(ds, n=100)[int(q * 100) - 1]

        print(f"样本：评分分歧 {len(dr)} 条（中位数 {statistics.median(dr):.4f}）")
        print(f"      情感分歧 {len(ds)} 条（中位数 {statistics.median(ds):.4f}）")
        print()
        print(f"建议阈值（{q:.0%} 分位）：")
        print(f"  ANIME_THR_R={thr_r:.4f}")
        print(f"  ANIME_THR_S={thr_s:.4f}")
        print()
        print(f"当前 .env 配置：THR_R={config.ANIME_THR_R} THR_S={config.ANIME_THR_S}")

        # 象限分布，检查是否退化（某一格为空）
        from app.services.divergence import classify_quadrant
        buckets: dict[str, int] = {}
        for a, b in zip(dr, ds):
            k = classify_quadrant(a, b, thr_r, thr_s)
            buckets[k] = buckets.get(k, 0) + 1
        print("\n四象限分布（新阈值下）：")
        for k, v in sorted(buckets.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
        empties = {"consensus", "hidden_controversy", "scale_bias",
                   "full_controversy"} - set(buckets)
        if empties:
            print(f"\n[提示] 这些象限暂为空：{sorted(empties)} —— "
                  f"可能是样本量不足，或阈值需要调整")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行验证**

Run: `cd backend && python3 scripts/calibrate_thresholds.py`
Expected: 打印样本量与建议阈值。**若提示样本不足，先执行 Task 12 的 `/anime/ingest` 多采几部番剧。**

- [ ] **Step 3: 按结果调整 .env**

把脚本输出的建议值写入 `backend/.env`（该文件不入库）：

```
ANIME_THR_R=<建议值>
ANIME_THR_S=<建议值>
```

- [ ] **Step 4: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/scripts/calibrate_thresholds.py
git commit -m "feat(scripts): 象限阈值标定脚本（分位数法 + 象限分布检查）"
```

---

## Task 16: 接入归因到分歧接口

**Files:**
- Modify: `backend/app/routers/divergence.py`
- Test: `backend/tests/test_divergence_attribution.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_divergence_attribution.py`：

```python
"""分歧结果含分站褒贬词归因（规格 §6.5）。"""
from fastapi.testclient import TestClient

from app import models
from app.db import SessionLocal
from app.main import app

client = TestClient(app)


def _seed_with_reviews() -> None:
    db = SessionLocal()
    try:
        db.add(models.Anime(anime_id="bangumi:253", title_cn="进击的巨人", year=2013))
        for src, sid in (("bangumi", "253"), ("bilibili", "4450")):
            db.add(models.AnimeSource(anime_id="bangumi:253", source=src, source_id=sid,
                                      rating_raw=8.5, rating_scale=10, rating_count=20000,
                                      review_count=100, sentiment_pos=50, sentiment_neg=10))
        texts_bgm = ["作画精良 作画精良 剧情深刻"] * 20
        texts_bili = ["打斗精彩 打斗精彩 节奏紧凑"] * 20
        for t in texts_bgm:
            db.add(models.Review(anime_id="bangumi:253", source="bangumi_live",
                                 lang="zh", text=t))
        for t in texts_bili:
            db.add(models.Review(anime_id="bangumi:253", source="bilibili_live",
                                 lang="zh", text=t))
        db.commit()
    finally:
        db.close()


def test_divergence_includes_attribution() -> None:
    _seed_with_reviews()
    r = client.get("/divergence/bangumi:253", params={"refresh": "true"})
    assert r.status_code == 200
    per_source = r.json()["attribution"]["per_source"]
    assert "bangumi" in per_source
    assert "bilibili" in per_source
    bgm_words = [x["word"] for x in per_source["bangumi"]["top_pos"]]
    assert any("作画" in w for w in bgm_words)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest tests/test_divergence_attribution.py -q`
Expected: FAIL — `per_source` 为空

- [ ] **Step 3: 实现归因接入**

在 `backend/app/routers/divergence.py` 顶部加入：

```python
from ..services.nlp import build_source_terms
```

在 `divergence()` 中，把 `"attribution": {"per_source": {}},` 一行替换为：

```python
        "attribution": {"per_source": _attribution(db, anime_id)},
```

并在文件末尾追加：

```python
_SOURCE_TO_REVIEW = {"bangumi": "bangumi_live", "bilibili": "bilibili_live"}


def _attribution(db: Session, anime_id: str, per_source_limit: int = 200) -> dict:
    """取各站已入库评论，算分站独有褒贬词（规格 §6.5）。"""
    docs: dict[str, list[str]] = {}
    for row in db.query(models.AnimeSource).filter_by(anime_id=anime_id).all():
        tag = _SOURCE_TO_REVIEW.get(row.source)
        if not tag:
            continue
        texts = [t for (t,) in db.query(models.Review.text).filter(
            models.Review.anime_id == anime_id,
            models.Review.source == tag).limit(per_source_limit).all()]
        if texts:
            docs[row.source] = texts
    return build_source_terms(docs, top_n=15) if len(docs) >= 2 else {}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python3 -m pytest tests/test_divergence_attribution.py -q`
Expected: PASS

- [ ] **Step 5: 跑全量测试**

Run: `cd backend && python3 -m pytest -q`
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/app/routers/divergence.py backend/tests/test_divergence_attribution.py
git commit -m "feat(api): 分歧结果接入分站褒贬词归因"
```

---

## Task 17: 前端 —— 类型与 API 封装

**Files:**
- Modify: `app/mood_reel_GUI/entry/src/main/ets/model/Models.ets`
- Modify: `app/mood_reel_GUI/entry/src/main/ets/services/api.ets`

- [ ] **Step 1: 读现有封装**

Run: `cd /home/asuka/Project/HarmonyOS/MoodReel/app/mood_reel_GUI/entry/src/main/ets && sed -n '1,60p' services/api.ets && echo "=== Models ===" && sed -n '1,60p' model/Models.ets`
按其既有风格（interface 命名、导出方式、请求方法名）撰写新代码。

- [ ] **Step 2: 加类型**

在 `Models.ets` 追加（**命名风格对齐文件内已有 interface**）：

```typescript
export interface AnimeSourceItem {
  source: string;
  source_id: string;
  url: string | null;
  rating_raw: number | null;
  rating_scale: number | null;
  rating_count: number | null;
  review_count: number;
}

export interface DivergenceRating {
  source: string;
  rating_weighted: number;
  weight: number;
}

export interface DivergenceSentiment {
  source: string;
  mean: number;
  pos: number;
  neg: number;
  review_count: number;
}

export interface SourceTerms {
  top_pos: Array<Record<string, Object>>;
  top_neg: Array<Record<string, Object>>;
}

export interface DivergenceResult {
  anime_id: string;
  title_cn: string | null;
  status: string;                 // ok | insufficient_data
  reason: string | null;
  d_rating: number | null;
  d_sentiment: number | null;
  quadrant: string | null;        // consensus | hidden_controversy | scale_bias | full_controversy
  sources_used: Record<string, Array<string>>;
  degraded: boolean;
  ratings: DivergenceRating[];
  sentiment: DivergenceSentiment[];
  attribution: Record<string, Record<string, SourceTerms>>;
  computed_at: string;
}
```

- [ ] **Step 3: 加接口封装**

在 `api.ets` 追加（对齐文件内已有请求函数写法）：

```typescript
export function fetchDivergence(animeId: string): Promise<DivergenceResult> {
  return httpGet(`/divergence/${encodeURIComponent(animeId)}`) as Promise<DivergenceResult>;
}

export function fetchAnimeSources(animeId: string): Promise<Object> {
  return httpGet(`/anime/${encodeURIComponent(animeId)}/sources`);
}

export function searchAnime(q: string, sources: string = 'bangumi,bilibili'): Promise<Object> {
  return httpGet(`/anime/search?q=${encodeURIComponent(q)}&sources=${sources}`);
}

export function fetchDivergenceRanking(quadrant: string, limit: number = 20): Promise<Object> {
  return httpGet(`/ranking/divergence?quadrant=${encodeURIComponent(quadrant)}&limit=${limit}`);
}
```

> **执行时必须先看 `api.ets` 里实际的请求函数名（可能是 `get`/`request`/`getJson`）与 BASE_URL 拼接方式，按实际替换 `httpGet`。**

- [ ] **Step 4: 编译验证**

用 DevEco Studio 打开 `app/mood_reel_GUI`，Build → 确认无编译错误。
Expected: 编译通过（无 TS 类型错误）

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add app/mood_reel_GUI/entry/src/main/ets/model/Models.ets \
        app/mood_reel_GUI/entry/src/main/ets/services/api.ets
git commit -m "feat(app): 动漫域类型定义与分歧接口封装"
```

---

## Task 18: 前端 —— 象限图组件

**Files:**
- Create: `app/mood_reel_GUI/entry/src/main/ets/components/charts/QuadrantChart.ets`

- [ ] **Step 1: 读现有图表组件**

Run: `cd /home/asuka/Project/HarmonyOS/MoodReel/app/mood_reel_GUI/entry/src/main/ets/components/charts && cat BarChart.ets`
**严格按 BarChart 的 Canvas 绘制模式**（onReady 绘制、尺寸获取、颜色常量来源）写象限图，保持风格统一。

- [ ] **Step 2: 实现象限图**

创建 `QuadrantChart.ets`（结构照抄 BarChart，替换绘制逻辑）：

```typescript
/**
 * 分歧象限散点图：x = D_rating，y = D_sentiment，四象限着色。
 * 右上「分数掩盖了争议」是本系统的核心发现，用强调色。
 */
@Component
export struct QuadrantChart {
  @Prop points: Array<Object> = [];       // [{x, y, label}]
  @Prop thrR: number = 0.5;
  @Prop thrS: number = 0.2;
  @Prop width: number = 320;
  @Prop height: number = 320;

  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);

  private readonly AXIS = '#8A8A8E';
  private readonly GRID = '#E5E5EA';
  private readonly HIDDEN = '#FF3B30';    // 分数掩盖了争议 —— 强调
  private readonly CONSENSUS = '#34C759';
  private readonly SCALE_BIAS = '#FF9500';
  private readonly FULL = '#5856D6';

  build() {
    Canvas(this.ctx)
      .width(this.width)
      .height(this.height)
      .onReady(() => this.draw());
  }

  private draw(): void {
    const pad = 36;
    const w = this.width - pad * 2;
    const h = this.height - pad * 2;
    const maxR = Math.max(this.thrR * 2, this.maxOf('x'));
    const maxS = Math.max(this.thrS * 2, this.maxOf('y'));

    this.ctx.clearRect(0, 0, this.width, this.height);

    // 象限底色
    const xT = pad + (this.thrR / maxR) * w;
    const yT = pad + h - (this.thrS / maxS) * h;
    this.ctx.fillStyle = '#FFF5F5';
    this.ctx.fillRect(xT, pad, this.width - pad - xT, yT - pad);        // 右上
    this.ctx.fillStyle = '#F7F7FA';
    this.ctx.fillRect(pad, pad, xT - pad, yT - pad);                    // 左上
    this.ctx.fillRect(xT, yT, this.width - pad - xT, this.height - pad - yT);  // 右下
    this.ctx.fillRect(pad, yT, xT - pad, this.height - pad - yT);       // 左下

    // 阈值分界线
    this.ctx.strokeStyle = this.GRID;
    this.ctx.lineWidth = 1;
    this.ctx.beginPath();
    this.ctx.moveTo(xT, pad);
    this.ctx.lineTo(xT, this.height - pad);
    this.ctx.moveTo(pad, yT);
    this.ctx.lineTo(this.width - pad, yT);
    this.ctx.stroke();

    // 坐标轴
    this.ctx.strokeStyle = this.AXIS;
    this.ctx.beginPath();
    this.ctx.moveTo(pad, pad);
    this.ctx.lineTo(pad, this.height - pad);
    this.ctx.lineTo(this.width - pad, this.height - pad);
    this.ctx.stroke();

    // 散点
    for (const p of this.points) {
      const x = pad + (Number(p['x']) / maxR) * w;
      const y = pad + h - (Number(p['y']) / maxS) * h;
      this.ctx.fillStyle = this.colorOf(Number(p['x']), Number(p['y']));
      this.ctx.beginPath();
      this.ctx.arc(x, y, 6, 0, Math.PI * 2);
      this.ctx.fill();
    }

    // 轴标签
    this.ctx.fillStyle = this.AXIS;
    this.ctx.font = '11vp sans-serif';
    this.ctx.fillText('评分分歧 →', this.width - pad - 66, this.height - pad + 20);
    this.ctx.fillText('情感分歧 ↑', pad - 28, pad - 12);
  }

  private maxOf(axis: string): number {
    let m = 0.0001;
    for (const p of this.points) {
      m = Math.max(m, Number(p[axis]) || 0);
    }
    return m;
  }

  private colorOf(x: number, y: number): string {
    const rLow = x < this.thrR;
    const sLow = y < this.thrS;
    if (rLow && !sLow) return this.HIDDEN;
    if (rLow && sLow) return this.CONSENSUS;
    if (!rLow && sLow) return this.SCALE_BIAS;
    return this.FULL;
  }
}
```

- [ ] **Step 3: 编译验证**

DevEco Studio Build → 无编译错误。若 `RenderingContextSettings` 或 `CanvasRenderingContext2D` 的导入方式与 BarChart 不同，按 BarChart 的实际写法调整。

- [ ] **Step 4: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add app/mood_reel_GUI/entry/src/main/ets/components/charts/QuadrantChart.ets
git commit -m "feat(app): 分歧象限散点图组件（Canvas 自绘，四象限着色）"
```

---

## Task 19: 前端 —— 跨站对比页与 Tab 挂载

**Files:**
- Create: `app/mood_reel_GUI/entry/src/main/ets/views/TabCompare.ets`
- Modify: `app/mood_reel_GUI/entry/src/main/ets/pages/Index.ets`

- [ ] **Step 1: 读现有 Tab 结构**

Run: `cd /home/asuka/Project/HarmonyOS/MoodReel/app/mood_reel_GUI/entry/src/main/ets && sed -n '1,80p' pages/Index.ets && echo "=== TabSettings ===" && sed -n '1,50p' views/TabSettings.ets`
确认 Tab 的声明方式（Tabs/TabContent 结构）与页面组件签名，新页严格照此写。

- [ ] **Step 2: 实现对比页**

创建 `TabCompare.ets`，包含四块：

1. **检索区**：`TextInput` 输入番名 + 「跨站检索」按钮 → 调 `searchAnime`，下拉列出候选
2. **采集区**：选中候选后「采集并分析」→ 调 ingest，随后轮询 `/crawl/{job_id}` 显示进度
3. **分歧结论区**：调 `fetchDivergence`，大字显示象限判定文案：
   - `hidden_controversy` → 「⚠️ 分数掩盖了争议」（强调色）
   - `consensus` → 「共识番」
   - `scale_bias` → 「打分习惯差异（非真实口碑分歧）」
   - `full_controversy` → 「全面争议」
   - `insufficient_data` → 显示 `reason`
4. **图表区**：`QuadrantChart`（该番 + 同象限其他番为背景点）+ 分站评分/情感条形对照
5. **归因区**：分站 `top_pos` / `top_neg` 词条并排展示（国内 vs 国外在意点）

**要求**：所有网络失败必须显示具体错误（复用现有 Toast/提示组件），**不得静默失败**——与后端 §11 的原则一致。

> **与规格的差异（有意为之）**：规格 §8 原本把「象限图」放在 Tab4 可视化、把「分站褒贬词对照」放在 Tab3 热点。本计划将二者**合并进一个新的「对比」Tab**。理由：分歧分析是一条连贯的流程（检索 → 采集 → 分歧 → 归因），拆到两个 Tab 会让用户来回切换、割裂因果。Tab3 原有的词云与 Tab4 原有图表**保持不变**，不删不改。
> 若答辩需要严格贴合规格 §8，把 `QuadrantChart` 挂到 Tab4、把归因区挂到 Tab3 即可，组件本身可直接复用。

- [ ] **Step 3: 挂载 Tab**

在 `pages/Index.ets` 的 Tabs 中新增一项，`TabContent` 内放 `TabCompare()`，标签名「对比」。

- [ ] **Step 4: 编译并实机验证**

1. DevEco Studio Build → 无错误
2. 启动后端：`cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. 模拟器/真机运行 App，设置页填后端局域网 IP，点「测试连接」
4. 对比 Tab：检索「进击的巨人」→ 采集 → 查看象限图与归因

Expected: 检索有结果、采集成功后象限图出现散点、归因区显示两站词条。**截图留档用于答辩。**

- [ ] **Step 5: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add app/mood_reel_GUI/entry/src/main/ets/views/TabCompare.ets \
        app/mood_reel_GUI/entry/src/main/ets/pages/Index.ets
git commit -m "feat(app): 跨站对比页（检索/采集/象限图/分站归因）"
```

---

## Task 20: 文档同步与验收

**Files:**
- Modify: `docs/3_接口契约文档.md`
- Modify: `docs/2_数据库设计.md`
- Modify: `docs/4_日志与运行说明.md`
- Modify: `docs/系统运行配置与AI提示词说明.md`

- [ ] **Step 1: 更新接口契约**

在 `docs/3_接口契约文档.md` 追加 §7 的五个新接口（`/anime/search`、`/anime/ingest`、`/anime/{id}/sources`、`/divergence/{id}`、`/ranking/divergence`），含请求参数、响应示例、`insufficient_data` 的说明。

- [ ] **Step 2: 更新数据库设计**

在 `docs/2_数据库设计.md` 追加 `anime` / `anime_source` / `divergence` 三表与 `reviews.anime_id` 扩展说明。

- [ ] **Step 3: 更新运行说明**

在 `docs/4_日志与运行说明.md` 追加：动漫语料采集、模型训练、阈值标定的三条命令；以及「失败必须带状态码」的日志约定。

- [ ] **Step 4: 更新 AI 提示词说明**

在 `docs/系统运行配置与AI提示词说明.md` §六 按既有体例补录本次动漫版迭代的提示词（沿用「使用理念 → 分阶段脉络 → 提示词 → 产物」的写法）。

- [ ] **Step 5: 逐条核对验收标准**

对照规格 §16 勾选：

- [ ] 两站全流程可演示
- [ ] `/divergence/{id}` 返回分歧指数、象限、分站褒贬词
- [ ] 四象限能在真实数据中筛出实例（若某格为空需说明数据原因）
- [ ] 准确率 ≥85%（Task 10）、归并准确率 ≥95%（Task 21）、吞吐 ≥200 条/秒（Task 21）均有离线测定记录
- [ ] 失败日志能区分"被限流"与"确实无数据"
- [ ] `pytest -q` 全绿
- [ ] 文档同步更新

- [ ] **Step 6: 最终提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add docs/
git commit -m "docs: 同步动漫版接口契约、数据库设计、运行说明与 AI 提示词记录"
```

---

## Task 21: 指标离线测定（归并准确率与吞吐）

**Files:**
- Create: `backend/scripts/measure_identity_accuracy.py`
- Create: `backend/data/identity_benchmark.csv`（人工标注基准集）
- Modify: `docs/4_日志与运行说明.md`（记录测定结果）

规格 §10 要求「番剧归并准确率 ≥95%」与「吞吐 ≥200 条/秒」有**离线测定记录**，本任务补齐。吞吐沿用现有 `scripts/benchmark.py`。

- [ ] **Step 1: 构建归并基准集**

创建 `backend/data/identity_benchmark.csv`，人工标注 **100 对**跨站条目。格式（`same=1` 表示同一部番）：

```csv
anchor_source,anchor_id,anchor_title,anchor_year,cand_source,cand_id,cand_title,cand_year,same
bangumi,253,进击的巨人,2013,bilibili,4450,进击的巨人,2013,1
bangumi,253,进击的巨人,2013,bilibili,9999,进击的巨人 第二季,2017,0
bangumi,302,死亡笔记,2006,bilibili,1234,死亡笔记,2006,1
```

构造方法：先跑 `/anime/search` 收集真实候选对，再把**易错对**（不同季、同名不同作、剧场版 vs TV）刻意纳入——基准集的价值在于覆盖边界，而不是全填正例。**正负样本各约 50 对。**

- [ ] **Step 2: 实现测定脚本**

创建 `backend/scripts/measure_identity_accuracy.py`：

```python
"""归并准确率离线测定（规格 §10）。

用法：cd backend && python scripts/measure_identity_accuracy.py
"""
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.services.adapters.base import Candidate        # noqa: E402
from app.services.identity import score_match            # noqa: E402

THRESHOLD = 0.7
BENCH = pathlib.Path(__file__).resolve().parent.parent / "data" / "identity_benchmark.csv"


def main() -> int:
    if not BENCH.exists():
        print(f"缺少基准集 {BENCH} —— 先按 Task 21 步骤 1 构建")
        return 1

    rows = list(csv.DictReader(BENCH.open(encoding="utf-8")))
    if not rows:
        print("基准集为空")
        return 1

    tp = fp = tn = fn = 0
    for r in rows:
        a = Candidate(source=r["anchor_source"], source_id=r["anchor_id"],
                      title_cn=r["anchor_title"],
                      year=int(r["anchor_year"]) if r["anchor_year"] else None)
        b = Candidate(source=r["cand_source"], source_id=r["cand_id"],
                      title_cn=r["cand_title"],
                      year=int(r["cand_year"]) if r["cand_year"] else None)
        pred = score_match(a, b) >= THRESHOLD
        truth = r["same"] == "1"
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and truth:
            fn += 1
        else:
            tn += 1

    total = len(rows)
    acc = (tp + tn) / total
    print(f"基准集 {total} 对：TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"归并准确率 = {acc:.2%}（目标 ≥95%）")
    if fp:
        print(f"[警告] 有 {fp} 对误合并 —— 这是最危险的错误（把两部番并成一部）")
    if fn:
        print(f"[提示] 有 {fn} 对漏合并 —— 会导致跨站对比缺站")
    if acc < 0.95:
        print("[未达标] 调整 identity.py 的阈值或打分权重后重测")
        return 1
    print("[达标] 归并准确率 ≥95%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 运行归并测定**

Run: `cd backend && python3 scripts/measure_identity_accuracy.py`
Expected: 打印混淆矩阵与准确率。**若 <95%，调 `identity.py` 的 `score_match` 权重（年份惩罚、季度强判负）后重测，直到达标。**

- [ ] **Step 4: 运行吞吐测定**

Run: `cd backend && python3 scripts/benchmark.py`
Expected: 打印批量推理吞吐。若 <200 条/秒，增大批大小或换 CPU 线程数后重测。

- [ ] **Step 5: 运行降级率统计**

Run: `cd backend && python3 -c "
from app.db import SessionLocal
from app import models
db = SessionLocal()
try:
    rows = db.query(models.CrawlJob).all()
    if not rows:
        print('暂无采集任务记录'); raise SystemExit
    bad = sum(1 for r in rows if r.status in ('failed', 'degraded'))
    print(f'任务总数 {len(rows)}，失败/降级 {bad}，降级率 {bad/len(rows):.1%}（目标 <10%）')
finally:
    db.close()
"
```
Expected: 打印降级率

- [ ] **Step 6: 记录结果**

把三项测定结果（归并准确率、吞吐、降级率，含测定日期与硬件）写入 `docs/4_日志与运行说明.md` 的「指标测定」小节。

- [ ] **Step 7: 提交**

```bash
cd /home/asuka/Project/HarmonyOS/MoodReel
git add backend/scripts/measure_identity_accuracy.py backend/data/identity_benchmark.csv \
        docs/4_日志与运行说明.md
git commit -m "test(metrics): 归并准确率基准集与离线测定，补记吞吐/降级率"
```

---

## 完成标准

全部 Task 完成后应满足：

1. `cd backend && python3 -m pytest -q` 全绿
2. `python3 scripts/collect_anime_corpus.py` + `train_textcnn_anime.py` 跑通，留存集准确率 ≥85%
3. `python3 scripts/calibrate_thresholds.py` 输出合理阈值，四象限不全为空
4. `python3 scripts/measure_identity_accuracy.py` 归并准确率 ≥95%（Task 21）
5. `python3 scripts/benchmark.py` 吞吐 ≥200 条/秒；采集降级率 <10%（Task 21）
6. App 对比 Tab 能完成「检索 → 采集 → 分歧 → 归因」全流程，并有截图留档
7. 文档四处同步更新完毕

## 风险提示

- **Task 3/4 的 fixture 录制**依赖外网与目标站点可用性。若录制时被限流，换关键词/换时段重试；**不要手写假 fixture**——那会让适配器测试失去意义。
- **Task 8 的 `nlp.py` 内部名**（`_tokenize` / `_POS_WORDS` / `_NEG_WORDS`）是本计划的假设，执行时必须先读文件按实际命名替换。
- **Task 9 的语料量**决定 Task 10 的模型质量。若准确率不达 85%，优先增加 `--titles`（更多番剧）而非堆 epochs。
- **Task 18/19 的 ArkTS 代码**基于对现有组件的结构假设，执行时必须先读 `BarChart.ets` 与 `Index.ets` 对齐实际写法。
