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

- **端侧 vs 服务端**：ArkTS 只做 HTTP 调用、状态管理与图表渲染；所有分析逻辑（TextCNN 推理、jieba/TF-IDF、褒贬倾向词）在 Python 侧，利于三人按模块并行。
- **双通道化解中英错位**：英文影评 → 本地 TextCNN；中文 → 腾讯情感 API；同一条英文可开"对照"再走腾讯。IMDB 50k 只做**训练 + 整库分析**，逐部影片分析走**实时采集集**。
- **两种分析上下文**：`whole`（IMDB 整库）与 `movie:{id}`（某部采集影片）。

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
└─ docs/       # 设计规格 + 系统运行配置与AI提示词说明
```

> **不入库**（.gitignore）：`*.docx`、`.env`、`*.db`、`backend/models/*.npz`、本地缓存。
> 课程 docx 放在本仓库**外层**的课程文件夹里，不提交进代码仓库。

## 4. 技术栈

| 端 | 技术 |
|---|---|
| App | ArkTS（ArkUI 声明式）、DevEco Studio、Canvas 图表 |
| 后端 | Python 3.10+、FastAPI、SQLAlchemy(SQLite)、BeautifulSoup(爬虫)、jieba |
| 模型 | TextCNN（PyTorch 训练 → 导出权重，服务端同结构前向推理） |

## 5. 队友接入（每人必做一次）

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
```

- 成员B（训练模型）再装：`pip install -r requirements-train.txt`（或 CPU 版 torch，见文件注释）。
- App 端按 [`app/README.md`](app/README.md) 用 DevEco Studio 建工程。
- 完整安装/运行/排障详见 [`docs/系统运行配置与AI提示词说明.md`](docs/系统运行配置与AI提示词说明.md)。

## 6. Git 协作流程（队友必读）

### 6.1 分支模型

```
main ───────────●──────────────────  上线/交付分支：稳定，只接受 dev 合入 + 打 tag
               ╱
dev ─────●────●──────────●────────  测试/联调分支：日常集成，功能先合到这里测
        ╱   ╱            ╱
feature/crawler   feature/model   feature/ui   每人自己的干活分支
```

| 分支 | 用途 | 谁能动 |
|---|---|---|
| `main` | 上线/答辩演示版（稳定） | 仅在里程碑由 `dev` 合入 |
| `dev` | 测试/联调分支 | 每人把功能合进来，在这里联调 |
| `feature/xxx` | 日常开发 | 各成员自己的分支 |

分支命名约定：`feature/crawler`（成员A）、`feature/model`（成员B）、`feature/ui`（成员C）、`feature/docs`、`fix/xxx`。

### 6.2 开工：先 pull，再开分支

```bash
git checkout dev                 # 切到测试分支
git pull origin dev              # ★ 每次开工/合并前先同步最新 dev
git checkout -b feature/model    # 从最新 dev 拉出你自己的分支（示例）
# ……写代码……
```
> 一定从**最新 dev** 开分支；不要从 main 或过期的旧分支上开。

### 6.3 收工：提交并推送

```bash
git add -A
git commit -m "feat: 接入 TextCNN 批量推理"   # 前缀建议 feat:/fix:/docs:/chore:
git push -u origin feature/model
```

### 6.4 合并到 dev（"该 merge 时怎么 merge"）

方式一（推荐）：GitHub 上为 `feature/model → dev` 提 **Pull Request**，队友 review 后 Merge。

方式二（本地直接合）：

```bash
git checkout dev
git pull origin dev              # 先拉最新 dev，避免冲突
git merge feature/model          # 有冲突时：解决后 git add . 再 git commit
git push origin dev
```

### 6.5 同步/更新别人的代码

```bash
git fetch origin                 # 拉取远端最新状态
git merge origin/dev             # 把你当前分支与最新 dev 合并
```
最常用：在 `dev` 上直接 `git pull origin dev`。

### 6.6 测试分支 / 上线分支怎么切换

```bash
git branch -a                     # 查看所有（本地+远端）分支
git checkout dev && git pull origin dev   # → 测试分支：联调/跑 pytest/跑 App
git checkout main                 # → 上线分支：看稳定版 / 准备答辩
git checkout feature/ui           # → 切回自己的分支
```

### 6.7 上线（里程碑 / 答辩前，组长执行）

```bash
git checkout main && git pull origin main
git merge dev                     # 测试通过的 dev 合入 main
git tag -a v0.1.0 -m "里程碑：第一版联调完成"
git push origin main --tags
```

### 6.8 铁律（避免踩坑）

1. **开工 / 合并 / 提交前都先 `git pull`**，尽量少冲突。
2. 别直接往 `main` 写代码；`main` 只收 `dev` 的合并。
3. 大文件不入库：`textcnn.npz`、`*.db`、`.env`、IMDB csv——按 §5 及配置文档单独共享。
4. 提交信息加前缀，一次提交一件事。
5. 绝不 `git push --force`；有冲突先问队友。

## 7. 快速开始（后端一键顺序）

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python scripts/download_imdb.py          # 下载/放置 IMDB_Dataset.csv 到 data/
python scripts/seed_db.py --sample 5000  # 建库灌库（联调用抽样）
python scripts/train_textcnn.py          # 成员B：训练导出模型（否则 model_ready=false）
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
# 期望：{"ok": true, "model_ready": false, "version": "0.1.0"}
```

## 8. 文档

- 系统设计规格：`docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md`
- **系统运行配置与 AI 提示词说明**：`docs/系统运行配置与AI提示词说明.md`
- 后端运行/联调细节：`backend/README.md`
- App 建工程与页面规划：`app/README.md`
