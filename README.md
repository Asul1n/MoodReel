# MoodReel · 电影评论情感分析系统（HarmonyOS App + Python 后端）

《软件开发实践 2》题目 12「基于情感分析的电影评论分析系统设计与实现」小组作品。

一个 **HarmonyOS App（ArkTS）+ Python 服务中枢（FastAPI）** 两端系统，覆盖题目四大模块：

1. **电影评论数据采集** —— IMDB 静态语料 + 按真实影片双源（IMDB / 豆瓣）实时采集，内置离线样本兜底
2. **情感极性分析** —— 本地 TextCNN（英文，基于 IMDB 50k 训练）+ 腾讯 AI 情感分析 API（中文）双通道
3. **评论热点挖掘** —— TF-IDF/高频热点词、褒贬倾向词（"夸什么 / 骂什么"）、加权词云
4. **可视化展示** —— ArkUI Canvas 自绘图表（分布环形图 / 热点条形图 / 词云 / 趋势）

**量化指标**：情感分类准确率 ≥ 85%；系统吞吐 ≥ 200 条/秒（均由配套 Python 脚本离线测定，见 `backend/scripts/benchmark.py`）。

## 技术栈

| 端 | 技术 |
|---|---|
| App | ArkTS（ArkUI 声明式）、DevEco Studio、Canvas 图表 |
| 后端 | Python 3.10+、FastAPI、SQLAlchemy(SQLite)、BeautifulSoup(爬虫)、jieba |
| 模型 | TextCNN（PyTorch 训练 → 导出权重，服务端 numpy/同模型前向推理） |

## 仓库结构

```
├─ backend/    # Python 服务中枢（采集/情感/热点/可视化 后端接口 + 训练评测脚本）
├─ app/        # HarmonyOS ArkTS 工程（DevEco Studio 中创建后放在这里）
└─ docs/       # 设计文档等
```

详细目录与开发说明见 [`backend/README.md`](backend/README.md) 与 [`app/README.md`](app/README.md)。

## 团队分工

| 成员 | 主线 | 主要模块 |
|---|---|---|
| A | 采集/爬虫 + 后端骨架 | 双源爬虫、语料/抓取接口、SQLite 建模灌库、离线样本、运行配置 |
| B | 模型/情感/热点 | TextCNN 训练评测、腾讯 adapter、情感接口、热点挖掘 |
| C | 鸿蒙 UI | 全部 ArkTS 页面、HTTP 封装、Canvas 图表、词云排版、演示视频 |

## 快速开始

后端：`cd backend && cp .env.example .env`，安装依赖后 `uvicorn app.main:app --host 0.0.0.0 --port 8000`，详见 [`backend/README.md`](backend/README.md)。

App：用 DevEco Studio 按 [`app/README.md`](app/README.md) 操作。

## 文档

- 系统设计规格：[`docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md`](docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md)
