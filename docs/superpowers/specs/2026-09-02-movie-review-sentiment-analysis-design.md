# 基于情感分析的电影评论分析系统 — 设计文档（鸿蒙 App）

> 选题：软件开发实践 2 · 题目 12「基于情感分析的电影评论分析系统设计与实现」
> 团队：3 人 ｜ 前端语言：ArkTS（鸿蒙 App）｜ 后端：Python（FastAPI 服务中枢）
> 日期：2026-09-02 ｜ 状态：已确认

---

## 1. 背景与目标

课程《软件开发实践 2》小组作品题。交付形态为一个 **HarmonyOS App**（前端）+ **Python 后端服务中枢**（承载模型与分析）的两端系统，覆盖题目规定的四个模块：

1. 电影评论数据采集模块
2. 情感极性分析模块
3. 评论热点挖掘模块
4. 可视化展示模块

**题目硬性要求：**
- 使用 IMDB 50k 影评数据集（lakshmi25npathi 版）
- 基于 TextCNN 模型 + 腾讯 AI 开放平台情感分析 API
- 情感分类准确率 ≥ 85%
- 系统支持每秒处理 200 条评论
- 编程语言采用 ArkTS（已确认，不用仓颉）

**课程交付物（每小组）：** 源码 + 附件压缩包（含《系统运行配置与 AI 提示词说明》）、演示视频/现场验收、实践文档（参照《软件开发实践文档案例.docx》）、每人两张华为开发者认证证书、每人一份课程思政文档。作品上传华为开发者社区并过审可评满绩（加分项，非必需）。

---

## 2. 需求分析与关键决策记录

### 2.1 关键约束的识别与化解

| # | 题目/现实的矛盾 | 化解方案 |
|---|---|---|
| 1 | IMDB 50k 是英文，腾讯情感 API 主打中文 | **双通道**：英文→本地 TextCNN；中文→腾讯 API |
| 2 | IMDB 50k（lakshmi25npathi 版）只有 `review+sentiment` 两列，无片名/分片字段 | 训练集与动态采集集分离：逐片分析走"动态采集集"（实时抓取带片名入库） |
| 3 | TextCNN 需深度学习框架，ArkTS 无法承载 | **私有云端后端**承载训练好的 TextCNN，App 经 HTTP 调用（架构上模型推理在服务端，业务工程在 ArkTS） |
| 4 | "每秒 200 条 + 准确率 85%"无法在真机 UI 上稳定复现 | 由配套 Python 脚本在**训练/服务端离线测定**，写进报告；App 批量分析返回条数/耗时作为现场佐证 |
| 5 | 实时爬虫脆弱（反爬/断网） | 爬虫放后端 Python；内置**离线样本包**兜底，实时失败自动降级并标注来源 |

### 2.2 已确认决策（小组问答结果）

- 推理位置：私有云端后端（Python 服务承载 TextCNN + 转发腾讯 API）
- 前端语言：ArkTS（课程认证/样例/图表生态最成熟）
- 语料/交互：双通道 —— 英文 IMDB 语料可浏览可分析；中文可输入走腾讯
- 演示环境：DevEco 模拟器为主，后端地址 App 内可配置，兼容真机局域网
- 腾讯 API：已开通/可开通，做成**可开关 + 优雅降级**
- 实时采集来源：**双源可切换**（IMDB 英文 / 豆瓣中文）
- 后端形态：**服务中枢**（A 方案）——业务分析逻辑几乎全在 Python，ArkTS 只做 HTTP+状态+UI
- 团队分工：3 人（采集/爬虫、模型/情感/热点、鸿蒙 UI）

---

## 3. 总体架构

```
DevEco 模拟器 / 真机                    宿主机（后端机，需外网）
┌────────────────────────┐          ┌──────────────────────────────────────┐
│  HarmonyOS App (ArkTS)  │  HTTP/JSON│  FastAPI 服务中枢 (Python)            │
│                        │◄─────────►│  ├ dataset   语料:浏览/筛选/新增/统计     │
│  Tab1 采集  爬虫任务/语料 │          │  ├ crawl     双源爬虫(IMDB/豆瓣)+job进度   │
│  Tab2 情感  单条/批量     │          │  ├ sentiment TextCNN(英文)+腾讯(中文/对照) │
│  Tab3 热点  词云/褒贬词   │          │  ├ hotspot   TF-IDF/高频词/褒贬倾向词      │
│  Tab4 可视化 图表         │          │  ├ viz       图表聚合                     │
│  Tab5 设置  后端地址/开关 │          │  └ health/测速                          │
└────────────────────────┘          └───────────┬──────────┬───────────────┘
                                                │          │ (requests, 节流)
                                        SQLite(语料/结果)    IMDB/豆瓣网页
```

- **职责切分**：ArkTS 仅负责 HTTP 调用、状态管理、列表与图表渲染；所有分析逻辑（TextCNN 推理、jieba/TF-IDF、褒贬倾向词）在 Python 侧，吃生态成熟度，利于三人按模块分工。
- **双通道**：英文文本→TextCNN；中文文本→腾讯情感 API；英文文本可开"对照"再走一次腾讯。
- **两种分析上下文**：`whole`（IMDB 静态整库）与 `movie:{movie_id}`（某部动态采集影片），情感/热点/可视化均跟随所选上下文。

### 3.1 代码仓库布局

```
HarmonyOS/
├─ docs/superpowers/specs/…-design.md   # 本文档
├─ backend/                             # 独立 Python 工程（A+B 共同维护）
│  ├─ app/
│  │  ├─ main.py            # FastAPI 入口
│  │  ├─ config.py          # 配置(env)：DB、模型路径、腾讯密钥
│  │  ├─ routers/           # dataset / crawl / sentiment / hotspot / viz / health
│  │  ├─ services/          # textcnn.py、tencent.py、nlp.py（热点）
│  │  └─ crawler/           # base.py、imdb.py、douban.py、sample_pack/
│  ├─ scripts/              # train_textcnn.py、benchmark.py、seed_db.py
│  ├─ models/               # vocab.json + textcnn.npz（运行时从仓库外/生成）
│  ├─ requirements.txt
│  └─ README.md             # 运行配置（也作为《系统运行配置说明》底稿）
└─ app/                     # DevEco Studio ArkTS 工程（C 负责）
   └─ entry/src/main/ets/   # pages、services/http、components/charts
```

---

## 4. 数据模型（SQLite）

三张表（同时为报告"数据库设计"一节提供真实素材）：

**movies**（动态采集影片索引）
| 字段 | 类型 | 说明 |
|---|---|---|
| movie_id | TEXT PK | 规范 id，如 `imdb:tt0111161` / `douban:1292052` |
| title | TEXT | 片名 |
| year | INT | 年份（可空） |
| source | TEXT | imdb / douban |
| source_url | TEXT | 抓取来源页 |
| created_at | DATETIME | |

**reviews**（语料与预测结果，主表）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK AUTOINCR | |
| movie_id | TEXT NULL | 为空表示 IMDB 静态整库样本 |
| source | TEXT | imdb_static / imdb_live / douban_live / manual |
| lang | TEXT | en / zh |
| text | TEXT | 评论原文 |
| stars | INT NULL | 豆瓣星级 1–5（可空） |
| ground_truth | TEXT NULL | IMDB 静态集正/负标签；豆瓣可星标映射 |
| pred_label | TEXT | 系统预测 positive/negative |
| pred_prob | REAL | 置信度 0–1 |
| model | TEXT | textcnn / tencent |
| created_at | DATETIME | 入库时间（可视化"趋势线"依据） |

**crawl_jobs**（抓取任务进度）
| 字段 | 类型 | 说明 |
|---|---|---|
| job_id | TEXT PK | uuid |
| source / query / movie_id | | 目标 |
| status | TEXT | pending / running / done / failed / degraded |
| fetched | INT | 已抓取条数 |
| total / limit | INT | |
| error | TEXT NULL | |
| created_at | DATETIME | |

可选缓存表 `hotspot_cache`（按上下文 key 缓存热点结果，key = context+topN+hash，避免重复计算）。

---

## 5. 模块设计

### 5.1 模块一：数据采集

**静态训练集（IMDB 50k）**
- 随 `backend/` 提供放置说明/下载脚本；首次启动 `seed_db.py` 灌入 SQLite（source=imdb_static，含 ground_truth）。仅用于训练/评测/整库浏览分析，不参与"逐片抓取"。

**动态采集（双源可插拔爬虫）**
- `crawler/base.py` 定义 `CrawlSource.search(query)` 与 `fetch(movie_ref, limit)`；
- `imdb.py`：英文影评；`douban.py`：中文短评（解析 1–5 星）；
- 选片交互 = **预置热门影片列表 + 自由输入片名**（后端解析候选）；
- 抓取做成 **job + 轮询**：`POST /crawl` 起任务，App 轮询 `GET /crawl/{job}` 显示"抓取中…已获取 N 条"；
- **礼仪与稳定**：随机 UA、请求间隔、超时+指数退避重试；单任务默认上限约 60–100 条；
- **离线兜底**：预置 5 部知名影片 × 上百条样本（`crawler/sample_pack/`）。实时抓取失败/断网时，若该片有样本则降级为该片离线样本（status=degraded，UI 标注"离线样本"）；实时成功则刷新并入库。

**入库与浏览**
- 新抓取/新增评论经语言路由自动打情感标签后落库；
- `GET /dataset/reviews` 支持分页与筛选（sentiment/source/lang/movie_id/关键词 q）；
- App 采集页也可手动"新增一条评论"（走 `POST /dataset/ingest`，可选立即分析）。

> 说明：不做网页爬虫之外的"全站采集"，报告口径写为"受控采集（指定影片 + 人工新增/导入）"，规避反爬与合规风险；对目标站点保持低频率、公开只读数据，注明仅供教学分析。

### 5.2 模块二：情感极性分析

**TextCNN（英文，本地）**
- 结构：Embedding(100d, vocab 15k, padding 256) → conv 核宽 [3,4,5] × 128 filters → 1-max pooling → concat → dropout(0.5) → Linear → softmax(2)。
- **Token 统一**：小写、去 HTML 标签/噪声、空白切分；训练脚本与线上服务共用同一份 `tokenizer.py + vocab.json`，杜绝"训练对不上线上"。
- 训练/评测在 `scripts/train_textcnn.py`（CPU 即可）：
  - 留存测试集准确率 ≥ 85%（TextCNN on IMDB 通常 88–90%，有余量）；
  - 吞吐：`scripts/benchmark.py` 在服务端对 200/400/1000 条批量推理计时，输出条/秒（目标 ≥200），记录环境与方法 → 报告用。
- 权重导出 `models/vocab.json + models/textcnn.npz`，FastAPI 启动时加载一次，推理放线程池。

**腾讯情感 API（中文，在线）**
- `services/tencent.py` adapter：AppID/SecretKey 走环境变量；具体平台（ai.qq.com 开放平台 / 腾讯云 NLP）签名差异封装在 adapter 内，以实际开通平台文档为准，README 注明接入步骤与配额。
- **可开关 + 优雅降级**：未配置/超时/配额尽 → 返回明确中文错误码，App 提示"中文情感分析需联网并启用腾讯 API"，主链路不阻塞。

**接口**
- `POST /analyze`（自动按语言路由）；`POST /analyze/en`（TextCNN，批量）；`POST /analyze/zh`（腾讯，单/批量）；`POST /analyze/compare`（英文同文 TextCNN vs 腾讯对照）。
- 返回统一：`{lang, model, label, prob, ms}`，批量多一条 `{count, elapsed_ms, throughput}`。

**三方对照（加分演示）**：豆瓣影评带用户星级 → 星标映射（4–5 正、1–2 负、3 弃）作真实新数据的"弱标签"，与系统预测对比给准确率，现场验证系统对新数据有效。

### 5.3 模块三：评论热点挖掘

对所选上下文产出三类可解释结果（报告写明口径公式）：
1. **Top 热点词**：停用词过滤 + TF-IDF / 高频词（英文用英文停用词表，中文用 jieba 分词 + 中文停用词）；
2. **词云数据**：加权词表 `{word, weight}` 返回 App 渲染；
3. **褒贬倾向词**：统计词在正/负评中的分布差异（正例占比 lift 或正负 TF-IDF 差）→ 输出"观众夸什么 / 骂什么"两列（`polarity_pos / polarity_neg`）。

说明：按"可解释路线"实现，不做 LDA 主题模型；词频热度+褒贬倾向已足以支撑"评论热点挖掘"且答辩好讲。

### 5.4 模块四：可视化展示

- 图表用 **ArkUI Canvas 自绘小工具库**（环形/条形/柱状），不依赖第三方图表 SDK，避免版本坑；
- 词云用**按权重缩放字号的加权标签排版**（稳定省事），真·螺旋词云列入 stretch 不做承诺；
- 提供图表：总体正负环形占比、所选上下文情感分布、Top 热点词条形、褒贬倾向词对比、新增评论时间趋势（依据 created_at）；
- 数据来自聚合接口 `GET /viz/summary?context=`（后端一次算好返回，App 只渲染）。

---

## 6. 接口契约（REST 一览）

| 方法 路径 | 作用 | 关键入参 | 出参要点 |
|---|---|---|---|
| GET /health | 探活+模型就绪 | — | `{ok, model_ready, version}` |
| GET /movies | 影片列表（动态+预置） | source? | `[movie…]` |
| POST /crawl | 发起抓取 | source, query/movie_id, limit | `{job_id}` |
| GET /crawl/{job_id} | 任务进度 | — | `{status, fetched, limit, error, degraded}` |
| GET /dataset/stats | 语料统计 | context? | 总数/正负/来源占比 |
| GET /dataset/reviews | 浏览/筛选 | limit, offset, sentiment, source, lang, movie_id, q | 分页列表 |
| POST /dataset/ingest | 新增/导入评论 | text / texts, source?, analyze? | `{id} / {ids}` |
| POST /analyze/en | TextCNN 批量 | texts[] | `{results[], count, elapsed_ms, throughput}` |
| POST /analyze/zh | 腾讯（中文） | texts[] | `{results[]}` |
| POST /analyze | 语言自动路由 | texts[] | `{results[]}` |
| POST /analyze/compare | 英文双引擎对照 | text | `{textcnn, tencent}` |
| GET /hotspot | 热点词/褒贬词/词云 | context, topN | `{keywords[], polarity_pos[], polarity_neg[], cloud[]}` |
| GET /viz/summary | 可视化聚合 | context | `{dist, top_words, polarity, trend, …}` |

错误统一：`{code, message(中文可读)}` + 合适的 HTTP 状态码。

---

## 7. 性能与指标达标策略

| 指标 | 测定方式 | 归属 |
|---|---|---|
| 准确率 ≥85% | `scripts/train_textcnn.py` 留存集评测，脚本内置断言 | 成员B |
| 吞吐 ≥200 条/秒 | `scripts/benchmark.py` 服务端批量推理计时（记录硬件/批大小/方法），批量分析接口同步返回 throughput 供 App 展示 | 成员B |

以上数字在**离线/服务端**测定并写入报告（业界对此类课题的通法），App 端批量分析展示"处理 N 条 / 用时 X"作为现场佐证。

---

## 8. 连通性、权限与错误处理

- **权限**：`module.json5` 声明 `ohos.permission.INTERNET`；本地明文 http 按调试放开（开发期 `http://10.0.2.2`/局域网 IP）。
- **后端地址**：App 设置页可配置 base URL + "测试连接"按钮（调 /health 显示延迟），答辩换环境一分钟搞定；默认值 = 宿主机局域网 IP。
- **错误处理**：后端不通→顶部横幅+重试；腾讯不可用→中文降级提示；输入空/超长→400 中文错误；模型文件缺失→/health 报 `model_ready:false` 并清晰日志。
- **超时/重试**：HTTP 客户端设超时；crawl 任务失败可重试、可查询原因。

---

## 9. 测试策略

- **Python 侧（pytest）**：dataset 端点、crawl 解析器（用本地 fixture HTML，不依赖外网）、analyze/en 确定性断言、tencent adapter 用 mock、hotspot 稳定性、`train_textcnn.py` 自动断言 accuracy≥0.85。
- **模型脚本**：训练后自动跑评测与吞吐，输出指标 JSON 到 `docs/`。
- **App 侧**：HTTP 客户端封装为单一模块便于替换；按验收清单人工过一遍四模块主流程 + 录屏视频；Canvas 图表用固定数据冒烟。
- **联调**：接口契约先行（本文档第 6 节为契约基线），A/B/C 各自对着跑。

---

## 10. 团队分工（3 人）

| 成员 | 主线 | 职责 | 兼 |
|---|---|---|---|
| 成员A | 采集/爬虫 + 后端骨架 | 双源爬虫、crawl/dataset 接口、SQLite 建模灌库、离线样本包、FastAPI 骨架与运行配置文档 | 组长统筹、后端整合联调、实践文档统稿 |
| 成员B | 模型/情感/热点 | TextCNN 训练/评测/吞吐、tokenizer+权重导出、analyze 接口、腾讯 adapter、热点挖掘 | 模型/情感/热点报告章节 |
| 成员C | 鸿蒙 UI | 全部 ArkTS 页面、HTTP 封装、Canvas 图表、加权词云、前端联调 | UI/可视化报告章节、演示视频 |

每人独立交付：两张华为开发者认证证书、一份课程思政文档。答辩材料三人分头备。

---

## 11. 交付物清单（对照课程要求）

1. 源码压缩包（backend/ + app/），命名 `组长学号-姓名-项目名-代码.zip`
2. 《系统运行配置与 AI 提示词说明》——以 `backend/README.md` + AI 使用提示词记录为基础成文
3. 实践文档（参照模板）——按第 12 节映射表填写
4. 演示视频（模拟器录屏主流程）
5. 每人：基础+高级认证证书 jpg、课程思政 docx
6. （加分）上传华为开发者社区过审

---

## 12. 附：如何填写《软件开发实践文档》模板（对照清单）

模板骨架为"可行性研究→需求分析→总体设计→详细设计"，以下给出素材对应位置，据此填写即可：

| 模板小节 | 素材来源 |
|---|---|
| 成员与分工 | 第 10 节 |
| 可行性研究 · 分层 DFD | 第 3 节架构图演化；第 6 节接口即各加工步骤数据流 |
| 数据字典 | 第 4 节表字段 + 第 6 节出参可写成数据流字典 |
| 需求分析 · 功能/数据/行为模型 | 第 2 节用例 + 四模块功能点 + 上下文切换 |
| 总体设计 · 软件结构 | 第 3、5 节模块划分；按模块补 IPO |
| 数据库设计 | 第 4 节三张表（含字段/主键/说明） |
| 详细设计 · 算法 | TextCNN 前向、TF-IDF/褒贬词公式、爬虫伪代码、jieba 流程、腾讯签名 |
| 性能/测试结论 | 第 7、9 节（准确率、吞吐脚本输出贴图） |

---

## 13. 里程碑建议（顺序）

1. M1 契约与骨架：FastAPI 骨架 + SQLite 建模 + seed（A）；TextCNN 训练达 85%（B）；App 工程建起 + /health 联通（C）
2. M2 各模块闭环：爬虫抓一部真实片入库（A）；analyze/en+zh+对照 接口（B）；Tab1 采集页可用（C）
3. M3 热点+可视化：热点接口与词云（B）；热点页+可视化页图表（C）
4. M4 整合打磨：离线兜底、错误降级、批量吞吐展示、录屏视频
5. M5 文档：实践文档/运行配置/思政/答辩材料，各自并行

---

## 14. Stretch（有余力再做，不影响主线验收）

- 真·螺旋布局词云（Canvas）
- 豆瓣星级 vs 预测的"真实新数据准确率"对照页
- 上传华为开发者社区的 HAP 版本（清掉硬编码密钥）
- 每部影片累计新增评论的时间趋势线
