# MoodReel · 电影评论情感分析系统

《软件开发实践 2》题目 12「基于情感分析的电影评论分析系统设计与实现」小组作品。
一个 **HarmonyOS App（ArkTS）+ Python 服务中枢（FastAPI）** 的两端系统。

**量化指标**：情感分类准确率 ≥ 85%；系统吞吐 ≥ 200 条/秒（均由配套 Python 脚本离线测定，见 `backend/scripts/benchmark.py`）。

---

## 1. 功能简介（四大模块）

1. **电影评论数据采集** —— IMDB 50k 静态语料 + 针对真实影片双源（IMDB / 豆瓣）实时采集，内置离线样本兜底
2. **情感极性分析** —— 本地 TextCNN（英文，基于 IMDB 训练）+ 腾讯 AI 情感分析 API（中文）双通道
3. **评论热点挖掘** —— TF-IDF/高频热点词、褒贬倾向词（"夸什么 / 骂什么"）、加权词云
4. **可视化展示** —— ArkUI Canvas 自绘图表（分布环形图 / 热点条形图 / 词云 / 趋势）

## 2. 架构

```
DevEco 模拟器 / 真机                    宿主机（后端机，需外网）
┌────────────────────────┐          ┌──────────────────────────────────────┐
│  HarmonyOS App (ArkTS)  │  HTTP/JSON│  FastAPI 服务中枢 (Python)            │
│                        │◄─────────►│  ├ dataset  语料:浏览/筛选/新增/统计      │
│  Tab1 采集  抓取/语料     │          │  ├ crawl    双源爬虫(IMDB/豆瓣)+job进度   │
│  Tab2 情感  单条/批量     │          │  ├ sentiment TextCNN(英文)+腾讯(中文/对照) │
│  Tab3 热点  词云/褒贬词   │          │  ├ hotspot  TF-IDF/高频词/褒贬倾向词       │
│  Tab4 可视化 图表         │          │  ├ viz      可视化聚合                    │
│  Tab5 设置  后端地址/开关  │          │  └ health/ 探活与模型就绪                │
└────────────────────────┘          └───────────┬──────────┬───────────────┘
                                                │          │ (requests, 节流)
                                        SQLite(语料/结果)    IMDB / 豆瓣网页
```

- **端侧 vs 服务端**：ArkTS 只做 HTTP 调用、状态管理与图表渲染；所有分析逻辑（TextCNN 推理、jieba/TF-IDF、褒贬倾向词）在 Python 侧，吃生态成熟度，利于三人按模块并行。
- **双通道化解中英错位**：英文影评 → 本地 TextCNN；中文 → 腾讯情感 API；同一条英文可开"对照"再走腾讯。IMDB 50k 只做**训练 + 整库分析**，逐部影片分析走**实时采集集**。
- **两种分析上下文**：`whole`（IMDB 整库）与 `movie:{id}`（某部采集影片），情感/热点/可视化都跟随所选上下文。

## 3. 仓库结构

```
├─ backend/   # Python 服务中枢
│  ├─ app/
│  │  ├─ main.py           # FastAPI 入口 + /health
│  │  ├─ config.py db.py models.py schemas.py
│  │  ├─ routers/          # dataset·crawl·sentiment·hotspot·viz（REST）
│  │  ├─ services/         # textcnn(英文) · tencent(中文) · nlp(热点)     ← 成员B
│  │  └─ crawler/          # base·imdb·douban + sample_pack 离线样本       ← 成员A
│  ├─ scripts/             # download_imdb / seed_db / train_textcnn / benchmark
│  ├─ tests/               # pytest（装依赖后可跑）
│  ├─ README.md .env.example requirements*.txt
├─ app/        # HarmonyOS ArkTS 工程（DevEco Studio 生成后放这里）        ← 成员C
│  └─ README.md            # DevEco 建工程步骤 + 页面/模块规划
└─ docs/       # 设计规格：docs/superpowers/specs/…-design.md
```

> **不入库**（.gitignore）：`*.docx`（课程材料）、`.env`、`*.db`、`backend/models/*.npz`、本地缓存。
> 课程材料如需共享给队友，请走聊天工具/邮箱，不要提交进代码仓库。

## 4. 技术栈

| 端 | 技术 |
|---|---|
| App | ArkTS（ArkUI 声明式）、DevEco Studio、Canvas 图表 |
| 后端 | Python 3.10+、FastAPI、SQLAlchemy(SQLite)、BeautifulSoup(爬虫)、jieba |
| 模型 | TextCNN（PyTorch 训练 → 导出权重，服务端同结构前向推理） |

## 5. 队友接入方式（每人必做一次）

```bash
# 1. 克隆（你已是 contributor）
git clone git@github.com:Asul1n/MoodReel.git && cd MoodReel

# 2. 设置你自己的提交身份（用 GitHub 账号邮箱，否则提交不显示头像）
git config user.name  "你的名字"
git config user.email "你的 GitHub 邮箱"

# 3. 后端环境
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 4. 冒烟测试：应通过 2 个用例
pytest -q

# 5. 启动后端并自检
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
# 期望：{"ok": true, "model_ready": false, "version": "0.1.0"}
```

- 成员B（训练模型）再装：`pip install -r requirements-train.txt`（或 CPU 版 torch，见文件注释）。
- App 端请按 [`app/README.md`](app/README.md) 用 DevEco Studio 建工程。

## 6. 团队分工与协作约定

| 成员 | 主线 | 主要文件 | 兼 |
|---|---|---|---|
| A | 采集/爬虫 + 后端骨架 | `app/crawler/`、`app/routers/crawl.py·dataset.py`、`scripts/seed_db.py`、`sample_pack/` | 组长统筹、后端整合联调 |
| B | 模型/情感/热点 | `app/services/textcnn.py·tencent.py·nlp.py`、`routers/sentiment.py·hotspot.py`、`scripts/train_textcnn.py·benchmark.py` | — |
| C | 鸿蒙 UI | `app/`（DevEco 工程）、Canvas 图表、HTTP 封装 | 演示视频 |

**协作约定**
- **契约先行**：接口以 `docs/superpowers/specs/…-design.md` §6 与后端 `schemas.py` 为准；改契约先同步队友再动手。
- **工作流**：日常直接 `main` 即可，开工前先 `git pull`；提交小而原子；有冲突风险的大改先开分支（`git checkout -b feature/xxx`）。
- **不入库的文件怎么共享**：`.env` 各自按 `.env.example` 填；模型 `textcnn.npz`/`vocab.json` 与 IMDB 数据集训练后互相拷或走网盘，别塞 git。
- **跑数据**：灌库 `python scripts/seed_db.py --sample 5000`（联调用抽样，全量 50k 去掉 `--sample`）。
- 每人还要单独交的课程要求：两张华为开发者认证证书、一份课程思政文档（与分工无关）。

## 7. 快速开始（后端一键顺序）

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python scripts/download_imdb.py          # 下载/放置 IMDB_Dataset.csv 到 data/
python scripts/seed_db.py --sample 5000  # 建库灌库（联调用抽样）
python scripts/train_textcnn.py          # 成员B：训练导出模型（否则 model_ready=false）
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 8. 文档

- 系统设计规格：`docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md`
- 后端运行/联调细节：[`backend/README.md`](backend/README.md)
- App 建工程与页面规划：[`app/README.md`](app/README.md)
