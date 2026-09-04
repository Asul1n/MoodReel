# MoodReel · Backend（Python 服务中枢）

FastAPI + SQLAlchemy(SQLite)。承载四块能力，均通过 REST 暴露给 HarmonyOS App：

| 模块 | 说明 | 主要文件 |
|---|---|---|
| dataset | IMDB 静态语料浏览/筛选/统计、手动新增 | `app/routers/dataset.py` |
| crawl | 双源爬虫（IMDB/豆瓣）+ 任务进度 + 离线兜底 | `app/routers/crawl.py`、`app/crawler/` |
| sentiment | TextCNN(英文) / 腾讯(中文) / 双引擎对照 | `app/routers/sentiment.py`、`app/services/textcnn.py`、`app/services/tencent.py` |
| hotspot | 热点词 / 褒贬倾向词 / 词云数据 | `app/routers/hotspot.py`、`app/services/nlp.py` |
| viz | 可视化聚合数据 | `app/routers/viz.py` |

## 运行配置（本地开发）

需要 **Python 3.10+**：

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# 模型推理（/analyze/en 前置）需 torch + model.pt：
pip install -r requirements-train.txt   # 或 CPU 版 pip install torch --index-url https://download.pytorch.org/whl/cpu
cp <队友交付包>/textcnn_sentiment/model.pt models/model.pt   # 细节见 models/README.md（*.pt 不入 git）

cp .env.example .env        # 按需填写（腾讯密钥等）

# 数据准备（一次）
python scripts/download_imdb.py     # 下载/放置 IMDB 50k CSV 到 data/
python scripts/seed_db.py           # 建库 + 灌入 IMDB 静态语料 + 预置影片/离线样本

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动后可先 `curl http://127.0.0.1:8000/health`，应返回 `{"ok": true, "model_ready": true|false, "model": {...}, "version": "0.1.0"}`（`model_ready` 需 torch + `models/model.pt`；缺任一则为 false，且 `model.msg` 会说明原因）。

## 环境变量（见 `.env.example`）

| 变量 | 默认 | 说明 |
|---|---|---|
| MOODREEL_DB | `./data/moodreel.db` | SQLite 路径 |
| MOODREEL_MODEL_DIR | `./models` | 训练产物目录 |
| DEEPSEEK_API_KEY / DEEPSEEK_ENABLED | 空 | DeepSeek 大模型情感分析（唯一中文通道，正/负二类+置信度；`/analyze/zh`、`/analyze/backfill`） |
| HOST / PORT | 0.0.0.0 / 8000 | 监听地址 |

## 与 App 联调

- App 设置页填写后端地址。**模拟器**访问宿主机：优先用宿主局域网 IP（如 `http://192.168.x.x:8000`）；个别环境用模拟器回环别名（如 `http://10.0.2.2:8000`，以 DevEco 模拟器文档为准）。
- 后端监听 `0.0.0.0`，保证同一网络/模拟器可访问。
- 首次联调用 App 设置页的「测试连接」调 `/health` 校验。

## 测试

```bash
cd backend && pytest -q
```

## 接口契约

以规格文档第 6 节为契约基线：
`docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md`
