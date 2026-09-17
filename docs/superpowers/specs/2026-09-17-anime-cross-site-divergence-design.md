# 动漫评论跨站口碑分歧分析系统 · 设计规格

> 本文档是 **MoodReel（电影评论情感分析系统）** 向**动漫域**迭代的设计规格。
> 迭代的核心不是"换个爬取目标"，而是把系统定位从**单站情感分析**升级为**跨站口碑分歧分析**。
> 关联文档：`2026-09-02-movie-review-sentiment-analysis-design.md`（原系统设计）、`docs/3_接口契约文档.md`、`docs/2_数据库设计.md`

- 日期：2026-09-17
- 团队：3 人（沿用 成员A 采集/后端、成员B 模型/服务、成员C 鸿蒙 UI 的分工）
- 迭代方式：**在现有仓库上迭代**，不新建仓库

---

## 1. 背景与目标

### 1.1 缘起

原系统（MoodReel）实现了电影评论的采集、情感极性分析、热点挖掘与可视化。课程反馈指出**创新性不足**——症结在于：单站、单域的情感分析属于常规实现，缺少"非它不可"的技术主张。

本次迭代同时解决两个问题：

1. **域迁移**：电影 → 动漫，数据源换成国内外权威动漫评分站；
2. **定位升级**：单站情感分析 → **跨站口碑分歧分析**，用多源数据回答单站数据回答不了的问题。

### 1.2 目标

- 对同一部番剧，聚合国内外多个评分站的评分与评论文本；
- 输出**分歧指数**，量化各站口碑差异；
- 输出**成因归因**，用各站独有褒贬词解释"为什么分歧"；
- 输出**错位检测**，识别"评分接近但评论两极分化"这类单看评分发现不了的作品。

### 1.3 可复用资产

| 资产 | 复用方式 |
|---|---|
| FastAPI 后端骨架（routers/services/schemas） | 直接沿用，新增路由与服务 |
| 采集基建（身份池、代理池、去重、并发、限流退避、CrawlJob 异步任务） | 保留为**网页兜底通道** |
| 中英双情感通道（TextCNN + 本地中文模型） | 复用架构，**中文模型换为动漫领域重训权重** |
| 热点挖掘（TF-IDF / 高低频词 / 褒贬倾向词） | 直接复用为**成因归因**引擎 |
| ArkTS 五 Tab + Canvas 自绘图表 | 保留，增改而非重构 |
| SQLite（Movie / Review / CrawlJob） | 扩展，向后兼容 |

---

## 2. 核心定位：跨站口碑分歧分析

分三个层次递进，构成系统的完整技术主张：

### 2.1 分歧度量

各站评分尺度不一、评分人数悬殊。先归一化到 10 分制，再用贝叶斯加权消除样本量偏差，最后以各站加权分的标准差作为**评分分歧指数**；以各站评论情感极性的标准差作为**情感分歧指数**。

### 2.2 成因归因

复用热点挖掘能力，提取**各站独有的高频褒贬词**，直接呈现"国内观众在意什么、国外观众在意什么"，把"分歧多大"推进到"为什么分歧"。

### 2.3 错位检测（核心创新）

将「评分分歧」与「情感分歧」交叉成四象限：

| | 情感一致（D_sent 低） | 情感分裂（D_sent 高） |
|---|---|---|
| **评分接近**（D_rating 低） | 共识番 | **分数掩盖了争议** |
| **评分悬殊**（D_rating 高） | **打分习惯差异** | 全面争议 |

- **「分数掩盖了争议」**（右上）：评分高度一致、评论却两极分化。这是本系统最有价值的产出——**只看评分完全无法发现**。
- **「打分习惯差异」**（左下）：评分差异大但情感一致，说明分歧来自平台打分尺度而非真实口碑。这一格具备**方法论自纠价值**，防止把"某站给分普遍偏高"误读为"口碑分歧"。

---

## 3. 数据源与采集策略

### 3.1 数据源

| 站点 | 归属 | 评分 | 评论文本 | 采集方式 |
|---|---|---|---|---|
| **Bangumi 番组计划** | 国内 | ✅ | ✅ 吐槽/评论 | 公开 REST API（需设 User-Agent） |
| **哔哩哔哩番剧** | 国内 | ✅ | ✅ 短评 | API + wbi 签名；网页兜底 |
| **AniList** | 国外 | ✅（100 分制） | ✅ | 公开 GraphQL API，免费免密钥 |
| **MyAnimeList** | 国外 | ✅ | ❌ 官方不提供正文 | 评分走官方 API；评论走网页 |

### 3.2 采集策略：API 优先 + 网页兜底

**这是本迭代相对原系统的关键策略调整。** 原系统为纯网页爬取，反爬成本高、演示稳定性差（豆瓣 IP 级限流即为实例）。新策略：

1. **优先官方 API**：AniList、Bangumi、MAL 评分均走 API——稳定、合规、无需身份轮换；
2. **仅对 API 不提供的正文做网页采集**：MAL 评论正文、B站短评；
3. **身份池/代理池降级为兜底通道**：仅在网页采集路径启用，不再承担主链路。

**合规约束**：仅采集公开数据、低频只读、遵守目标站 robots 与 ToS、标注数据来源、不绕过付费/登录墙（B站仅在公开可见范围内采集）。采集频率默认低于原系统。

### 3.3 阶段划分

- **v1**：Bangumi + B站（国内两站先跑通完整分歧分析）
- **v2**：AniList + MAL（补齐国内外对比）

v1 先做国内两站的理由：中文域模型可直接用两站语料训练；国内站网络可达性最好；能最早产出可演示成果。

---

## 4. 总体架构

```
App (ArkTS)  ── 新增「跨站对比」Tab（分歧象限图 + 分歧雷达 + 分站褒贬词对照）
     │ HTTP/JSON
FastAPI ── 新增路由
     │      /anime/search           跨站检索番剧
     │      /anime/ingest           发起跨站采集（异步任务）
     │      /anime/{id}/sources     单番各站原始数据
     │      /divergence/{id}        分歧分析结果
     │      /ranking/divergence     分歧榜（象限筛选 + 排序）
     │
     ├─ services/adapters/        ← 四站适配器（统一接口）
     │     base.py                 SourceResult 契约
     │     bangumi.py  / bilibili.py  / anilist.py  / mal.py
     ├─ services/identity.py      ← 番剧身份归并（跨站对齐）
     ├─ services/divergence.py    ← 分歧引擎（归一化/收缩/指数/错位/归因）
     │
     └─ 复用 sentiment（自训动漫模型）/ hotspot(nlp) / viz / crawler（兜底通道）
     │
   SQLite ── 复用 Review / CrawlJob；新增 Anime / AnimeSource / Divergence
```

### 4.1 番剧身份归并（最关键新增组件）

同一部番在四站的 ID 完全不同，**归并错了则整个跨站对比全盘皆错**，因此独立成模块并单独测试。两级策略：

1. **优先站间官方映射**
   - AniList `idMal` 字段直接给出 MAL ID；
   - Bangumi 条目外链含 MAL / AniList 站点链接；
   - B站番剧页含 Bangumi / MAL 外链。
2. **兜底模糊匹配**：中日英三语标题归一化（去副标题、统一全半角、罗马字转写）+ 年份 + 集数，加权打分取最优候选。
3. **人工校正表**：对归并结果不确定或冲突的条目，落一张可覆盖的映射表（`AnimeSource.is_manual`），保证可修正。

### 4.2 适配器统一契约

所有适配器实现同一接口，隔离各站差异：

```python
class SourceAdapter(Protocol):
    source: str                                  # bangumi | bilibili | anilist | mal
    def search(self, query: str) -> list[Candidate]: ...
    def fetch_meta(self, source_id: str) -> Meta: ...
    def fetch_ratings(self, source_id: str) -> Rating | None: ...
    def fetch_reviews(self, source_id: str, limit: int) -> list[ReviewItem]: ...
    def health(self) -> SourceHealth: ...
```

**强制要求**：任何失败必须返回带 `status` 与 `reason` 的结果，**禁止以空列表掩盖失败**（详见 §11）。

---

## 5. 数据模型

### 5.1 新增表

**`anime` —— 番剧主表**

| 字段 | 说明 |
|---|---|
| `anime_id` | 内部主键 |
| `title_cn` / `title_jp` / `title_en` | 三语标题（归并匹配与跨语言归因依据） |
| `year` / `season` | 年份 / 放送季度 |
| `episodes` | 集数 |
| `studio` / `staff` | 制作公司 / 主要声优（JSON） |
| `synopsis` | 简介 |
| `poster_url` | 海报（本地化伺服，沿用原系统规避防盗链的做法） |
| `created_at` / `updated_at` | 时间戳 |

**`anime_source` —— 跨站映射与原始数据**

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `anime_id` | 外键 → `anime` |
| `source` | `bangumi` / `bilibili` / `anilist` / `mal` |
| `source_id` | 该站 ID |
| `url` | 该站条目链接 |
| `rating_raw` / `rating_scale` | 原始评分与分值上限（如 AniList 为 100） |
| `rating_count` | 评分人数 |
| `rating_weighted` | 贝叶斯收缩后归一到 10 分制（计算列，落库便于排序） |
| `review_count` | 已采集评论数 |
| `sentiment_pos` / `sentiment_neg` / `sentiment_mean` | 该站情感统计 |
| `is_manual` | 是否人工校正过的映射 |
| `fetched_at` | 采集时间 |

唯一约束：`(source, source_id)`、`(anime_id, source)`。

**`divergence` —— 分歧结果缓存**

| 字段 | 说明 |
|---|---|
| `anime_id` | 主键 / 外键 → `anime` |
| `d_rating` | 评分分歧指数 |
| `d_sentiment` | 情感分歧指数 |
| `quadrant` | `consensus` / `hidden_controversy` / `scale_bias` / `full_controversy` |
| `payload` | 完整结果 JSON（各站明细 + 归因词表） |
| `sources_used` | 参与计算的站点 |
| `degraded` | 是否有站点降级 |
| `computed_at` | 计算时间 |

### 5.2 复用与扩展

| 表 | 处理 |
|---|---|
| `review` | **扩展**：新增可空 `anime_id` 外键；`source` 取值扩展为 `bangumi_live` / `bilibili_live` 等。旧电影数据不受影响 |
| `crawl_job` | **复用**：采集任务、进度、降级状态逻辑不变 |
| `movie` | **保留不动**，避免破坏现有功能与已灌语料 |

---

## 6. 核心算法

### 6.1 评分归一化与贝叶斯收缩

各站尺度不一（AniList 为 100 分制，其余 10 分制），先归一到 10 分制，再消除评分人数偏差：

```
R_norm = rating_raw × (10 / rating_scale)

R_weighted = (v·R_norm + m·C) / (v + m)

  v = 该站评分人数
  m = 先验权重（默认 500）
  C = 该番各站 R_norm 的均值
```

**理由**：B站 10 万人打 9.2 与 AniList 5 千人打 8.1 直接比较不成立；收缩后样本量小的站向均值回归，避免小样本极端值主导分歧指数。

### 6.2 分歧指数

```
p_i      = (pos_i − neg_i) / (pos_i + neg_i)     # 各站情感极性均值 ∈ [−1, 1]

D_rating = σ_w(各站 R_weighted)                  # 评分分歧（加权标准差，权重 w_i 见 §6.4）
D_sent   = σ_w(各站 p_i)                          # 情感分歧（同上）
```

加权标准差定义：

```
σ_w = sqrt( Σ w_i·(x_i − x̄_w)² / Σ w_i )
x̄_w = Σ w_i·x_i / Σ w_i
```

其中 `x_i` 为站点 `i` 的 `R_weighted`（或 `p_i`），`w_i` 为该站权重（默认 1.0，评分人数不足时 0.5，见 §6.4）。

**站点筛选规则**：
- 无评分的站点**不参与** `D_rating` 计算，也不计入 §6.1 中 `C` 的均值；
- 评论数不足的站点**不参与** `D_sent` 计算（见 §6.4）；
- 因此 `D_rating` 与 `D_sent` 的参与站点集合可以不同，需在响应中通过 `sources_used` 分别标明。

参与计算的站点少于 2 个时不出分歧结果，返回 `insufficient_data`。

### 6.3 错位检测

按阈值切分四象限：

```
quadrant =
  D_rating <  THR_R and D_sent <  THR_S  → consensus          共识番
  D_rating <  THR_R and D_sent >= THR_S  → hidden_controversy 分数掩盖了争议
  D_rating >= THR_R and D_sent <  THR_S  → scale_bias         打分习惯差异
  D_rating >= THR_R and D_sent >= THR_S  → full_controversy   全面争议
```

默认阈值（**可配置，需用真实数据标定**）：`THR_R = 0.5`（10 分制下的评分标准差）、`THR_S = 0.2`（极性标准差）。

标定方法：用已采集数据画出 `(D_rating, D_sent)` 散点分布，取分位数（如 60% 分位）作为初值，再人工检视象限归属是否合理。

### 6.4 站点参与门槛

| 条件 | 处理 |
|---|---|
| 评分人数 `v < 100` | 标记"参考性低"，**降权**参与（权重 0.5） |
| 单站评论数 `< 30` | 该站**不参与**情感分歧计算 |
| 有效站点 `< 2` | 不出分歧结果，返回 `insufficient_data` |

门槛参数全部可配置，便于调参与答辩演示。

### 6.5 成因归因

复用 `services/nlp.py`：

1. 对每个站点的评论文本分别计算 TF-IDF 与词频；
2. 取该站相对其他站的**独有高频词**（互信息或 TF-IDF 差值）；
3. 用褒贬倾向词表为独有词打极性，拆成 `top_pos` / `top_neg`；
4. v2 增加**跨语言对齐**：中文侧与英文侧分别出词表，通过预置的中英动漫术语对照表（作画/art、分镜/storyboard、声优/voice acting、崩坏/quality drop 等）给出跨语言可比结论。

> v1 仅做中文两站，跨语言对齐留到 v2；v1 保留接口字段 `attribution.per_source`，结构上已为 v2 预留。

---

## 7. 接口契约

```
GET  /anime/search?q=<关键词>&sources=bangumi,bilibili
     → [{anime_id, title_cn, title_jp, title_en, year, episodes,
         sources: [{source, source_id, url, rating_norm, rating_count}]}]
     说明：跨站归并后的候选；未入库的番剧返回临时合并结果，供用户确认后 ingest

POST /anime/ingest
     body: {anime_id | (title + year), sources: [...], limit: 200, refresh: false}
     → {job_id}
     说明：复用 CrawlJob 异步任务；用 GET /crawl/{job_id} 轮询进度（现有接口）

GET  /anime/{anime_id}/sources
     → {anime: {...},
        sources: [{source, source_id, url, rating_raw, rating_scale, rating_count,
                   rating_weighted, sentiment: {pos, neg, mean}, review_count,
                   weight, fetched_at, status}]}

GET  /divergence/{anime_id}
     → {anime_id, d_rating, d_sentiment, quadrant, verdict,
        sources_used: {rating: [...], sentiment: [...]},   # 两个指标参与站点可不同
        degraded: bool,
        ratings:   [{source, rating_weighted, weight}],
        sentiment: [{source, mean, pos, neg, review_count}],
        attribution: {per_source: {<source>: {top_pos: [], top_neg: []}}},
        computed_at}
     说明：有效站点不足时返回 200 + {status: "insufficient_data", reason}

GET  /ranking/divergence?quadrant=<象限>&sort=d_sentiment&limit=20&offset=0
     → {total, items: [{anime_id, title_cn, year, d_rating, d_sentiment, quadrant}]}
```

**复用不变**：`/health`、`/crawl/{job_id}`、`/analyze/*`、`/hotspot/*`、`/dataset/*`、`/viz/*`。

**Schema 变更**：所有新增响应模型加入 `schemas.py`，沿用现有 pydantic 风格；`docs/3_接口契约文档.md` 同步更新。

---

## 8. 前端改造（ArkTS）

保留五 Tab 结构，增改而非重构：

| Tab | 改动 |
|---|---|
| Tab1 采集 | 改为「番剧检索 + 跨站采集」。复用现有采集页骨架与进度轮询逻辑 |
| Tab2 情感 | 保留单条/批量分析；新增**分站情感对比**视图 |
| Tab3 热点 | 保留词云与褒贬词；新增**分站褒贬词对照**（国内 vs 国外在意点） |
| Tab4 可视化 | 保留原图表；新增**分歧象限图**（散点：x=D_rating，y=D_sent，四象限着色）与**分歧雷达图** |
| Tab5 设置 | 不变（后端地址、开关） |

**实现约束**：象限图与雷达图用现有 Canvas 自绘基建实现，**不引入第三方图表库**，保持当前零依赖风格。新增页面的网络层复用现有 HTTP 封装与错误提示。

---

## 9. 分阶段实施路径

### v1 · 国内两站跑通（先产出可演示成果）

1. **数据层**：新增 `Anime` / `AnimeSource` / `Divergence` 三表与迁移脚本（保留旧数据）
2. **归并**：`identity.py` + 归并测试集（人工标注 100 部作为基准）
3. **适配器**：`bangumi.py`（API）、`bilibili.py`（API + 签名，网页兜底）
4. **语料与模型**：采集动漫评论语料 → 按星级/评分自动建集 → jieba + TextCNN 重训中文动漫领域模型（复用现有 `train_textcnn_zh.py` 流水线）→ 留存集评测
5. **分歧引擎**：归一化 → 贝叶斯收缩 → 分歧指数 → 象限判定；阈值标定
6. **归因**：接入 `nlp.py` 输出分站褒贬词
7. **接口**：§7 全部路由 + schemas + 接口文档更新
8. **前端**：Tab1 改造 + Tab4 象限图 + Tab3 分站褒贬词
9. **验收**：两站全流程演示（检索 → 采集 → 分析 → 分歧）

### v2 · 扩至四站

10. `anilist.py`（GraphQL）、`mal.py`（评分 API + 评论网页）
11. 跨语言归因（中英动漫术语对照表）
12. 分歧榜 + 象限筛选与排序
13. 更新演示视频、实践文档与 AI 提示词说明

---

## 10. 量化指标

| 指标 | 口径 | 目标 |
|---|---|---|
| 中文动漫情感准确率 | 自训模型留存集评测（`train_textcnn_zh.py` 内置断言） | ≥ 85% |
| **番剧归并准确率** | 人工标注 100 部基准集 | **≥ 95%** |
| 分歧指数覆盖率 | 能算出分歧结果的番剧 / 已采集番剧 | ≥ 90% |
| 分析吞吐 | `benchmark.py` 离线测定（记录硬件/批大小/方法） | ≥ 200 条/秒 |
| 数据源降级率 | `degraded` 任务 / 总采集任务 | < 10% |

前四项沿用原系统的测定方式，**番剧归并准确率与数据源降级率为本迭代新增**。

---

## 11. 错误处理与降级

本节的第 2 条直接来自原系统的一次真实故障：豆瓣 `subject_suggest` 请求被限流返回 `None`，而 `_get()` 吞掉了状态码，调用方把 `None` 当作"无结果"，日志只记"搜索无结果"，导致排障只能靠现网复测。**新适配器层从设计上不允许该类信息丢失。**

1. **统一结果契约**：适配器一律返回 `SourceResult(status: ok | degraded | failed, reason, data)`；
2. **强制区分"请求失败"与"确实无数据"**：失败路径必须记录 HTTP 状态码与异常类型，日志文案区分二者，禁止用空列表代表失败；
3. **单站失败不阻断**：其余站点可用即照常出分歧结果，响应标注 `degraded=true` 并列出缺失站点；
4. **评分人数不足降权**：见 §6.4；
5. **结果缓存**：`Divergence` 落库，重复查询直接命中；`refresh=true` 强制重算；
6. **采集幂等**：沿用现有逻辑——同一影片已有在线评论且 `refresh=false` 时复用跳过；
7. **限流退避**：网页兜底通道保留现有指数退避与身份/代理轮换，但不再作为主链路。

---

## 12. 测试策略

| 层 | 测试内容 |
|---|---|
| `identity` | 同番跨站 ID 对齐；跨语言标题匹配；**误合并防护**（两部不同的番不得并成一部）——以人工标注 100 部为基准集 |
| `divergence` | 纯函数单测：归一化（含 100 分制）、贝叶斯收缩边界（v=0 / v 极大 / m 变化）、四象限判定边界、有效站点不足时返回 `insufficient_data` |
| `adapters` | 用 fixture 录制的真实响应做离线测试（沿用现有 `tests/fixtures/` 模式）；失败路径必须断言 `status` 与 `reason` 正确 |
| 端到端 | 两站采集 → 情感分析 → 分歧输出 冒烟；`pytest -q` 全绿为合入前提 |

---

## 13. 与"自主可控"的呼应

本条不靠额外话术包装，而是从技术选择中自然成立：

- **数据源自主**：以国内 Bangumi / B站为一等公民（v1 即国内两站），而非只做境外平台；
- **模型自主**：情感分析使用**自训自持**的动漫领域模型，不依赖境外云端 API；
- **平台自主**：全栈运行在国产 HarmonyOS 生态上。

---

## 14. 复用边界（对现有代码的改动清单）

| 模块 | 动作 |
|---|---|
| `app/models.py` | 新增 `Anime` / `AnimeSource` / `Divergence`；`Review` 加可空 `anime_id` |
| `app/schemas.py` | 新增 §7 响应模型 |
| `app/routers/` | 新增 `anime.py` / `divergence.py` |
| `app/services/adapters/` | **全新** |
| `app/services/identity.py` | **全新** |
| `app/services/divergence.py` | **全新** |
| `app/services/textcnn_zh.py` | 换用动漫领域重训权重（接口不变） |
| `app/services/nlp.py` | 复用，新增"分站独有词"计算 |
| `app/services/analytics.py` / `viz.py` | 复用，新增分歧聚合 |
| `app/crawler/` | 保留为网页兜底通道；修复 `_get` 的失败信息丢失问题 |
| `backend/scripts/` | 新增 `train_textcnn_anime.py`（或复用 `train_textcnn_zh.py` 加域参数）、`calibrate_thresholds.py` |
| `app/`（ArkTS） | Tab1 改造、Tab3/Tab4 新增视图 |
| `docs/` | 接口契约、数据库设计、运行说明同步更新 |

---

## 15. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 网页兜底通道被反爬（豆瓣限流为前车之鉴） | 采集失败、演示中断 | 主链路走 API；网页通道低频 + 身份/代理轮换；离线 fixture 兜底演示 |
| 番剧归并错误 | 跨站对比结论全盘错误 | 独立模块 + 官方 ID 映射优先 + 人工校正表 + 100 部基准集测准确率 ≥95% |
| B站短评过短（如"好看"） | 情感分析信息量不足 | 优先取长评/番剧长评区；过短文本单独统计并标注；必要时降低该站情感权重 |
| 部分冷门番评论量不足 | 算不出情感分歧 | §6.4 门槛；不足时返回 `insufficient_data` 而非给错误结论 |
| 阈值凭经验设定不合理 | 象限归属失真 | 阈值可配置 + 用真实数据分位数标定 + 提供标定脚本 |
| 采集合规争议 | 影响交付 | 仅公开数据、低频只读、遵守 robots/ToS、标注来源、不绕登录墙 |

---

## 16. 验收标准

- [ ] 两站全流程可演示：检索 → 采集 → 情感分析 → 分歧结果 → 前端展示
- [ ] `GET /divergence/{id}` 对已采集番剧能返回分歧指数、象限归属与分站褒贬词
- [ ] 四个象限均能在真实数据中筛出实例（若某象限为空，需说明数据原因）
- [ ] 情感准确率 ≥85%、归并准确率 ≥95%、吞吐 ≥200 条/秒 有离线测定记录
- [ ] 失败路径日志能区分"被限流/请求失败"与"确实无数据"
- [ ] `pytest -q` 全绿
- [ ] 接口契约、数据库设计、运行说明文档同步更新
