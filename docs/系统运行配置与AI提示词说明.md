# 系统运行配置与 AI 提示词说明

> 课程交付物配套文档（小组提交"系统源代码及相关附件"时附上，随代码打包）。
> 对应小组：MoodReel 电影评论情感分析系统 · 软件开发实践 2 · 题目 12
> 本文档与 `backend/README.md`、`app/README.md`、根 `README.md` 配合使用。

---

## 一、环境要求

| 组件 | 要求 |
|---|---|
| 操作系统 | Windows / macOS / Linux 均可（本小组以 Windows + DevEco 为主） |
| Python | 3.10+ |
| DevEco Studio | 5.0 及以上，可用的 HarmonyOS NEXT SDK（API ≥ 10） |
| 模型训练 | 建议 8GB+ 内存；CPU 即可（torch CPU 版），有 NVIDIA GPU 可选 |
| 网络 | 后端机需外网（调用 DeepSeek、抓取豆瓣/IMDB）；App 与后端同一局域网 |

## 二、代码获取与分支

```bash
git clone git@github.com:Asul1n/MoodReel.git
cd MoodReel
git config user.name  "你的名字"
git config user.email "你的 GitHub 邮箱"
git fetch origin
git checkout dev          # 日常开发在 dev（测试分支）；main 为上线分支，只收 dev 合并
```

分支约定见根 `README.md` §6：`main`（上线）/ `dev`（测试联调）/ `feature/{crawler,model,ui,docs}`（各自开发）。

## 三、后端安装与运行

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate ；Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 模型训练成员（成员B）额外：
#   pip install -r requirements-train.txt
#   或 CPU 版： pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 3.1 环境变量（.env）

```bash
cp .env.example .env
```

| 变量 | 说明 |
|---|---|
| MOODREEL_DB | SQLite 路径（默认 `./data/moodreel.db`） |
| MOODREEL_MODEL_DIR | 模型目录（默认 `./models`） |
| DEEPSEEK_API_KEY / DEEPSEEK_ENABLED | **中文情感唯一通道**（DeepSeek，二类+置信度）。`platform.deepseek.com` 申请 Key |
| DOUBAN_COOKIES | 豆瓣登录 **Cookie 完整头**（`bid=…; dbcl2=…; …`），一行一个 |
| DOUBAN_COOKIES_2 / _3 / _4 / _5 | 第 2~5 个豆瓣账号 Cookie（多账号轮换，提高单片抓取量） |
| DOUBAN_PROXIES | 代理池，每行一个 `http://user:pass@ip:port`（可选） |
| DOUBAN_WORKERS | 抓取并发数（默认 `1`，低调；改大前评估被封风险） |
| HOST / PORT | 监听地址，联调用 `0.0.0.0:8000` |

> 情感口径为**统一二类 positive/negative + 置信度**（无 neutral 档）；中文/英文一致。

### 3.2 模型与语料

```bash
# 本地英文 TextCNN：把成员B训练的 model.pt 放到 backend/models/（不入 git）
cp <交付包>/textcnn_sentiment/model.pt backend/models/model.pt

# IMDB 50k 静态语料（可选，做英文整库分析）
# 方式1：Kaggle CSV(review,sentiment) 放 data/IMDB_Dataset.csv 后：
python scripts/download_imdb.py && python scripts/seed_db.py
# 方式2：成员B 的 aclImdb 目录：
python scripts/seed_acl_imdb.py --root /path/to/aclImdb
```

> 词云使用 `wordcloud` 库渲染（`requirements.txt` 已含；装：`pip install -r requirements.txt`）。

### 3.3 启动与自检

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
# 期望：{"ok": true, "model_ready": true, "model": {"ready": true, "msg": ""}, "version": "0.1.0"}
# model_ready=true 表示本地 TextCNN 已加载（需 torch + models/model.pt）
```

常用接口冒烟：`GET /dataset/stats`、`POST /analyze/en`（示例 body `{"texts":["A great movie!"]}`）。

### 3.4 测试

```bash
cd backend && pytest -q        # 期望 26 个用例通过
```

## 四、App（HarmonyOS）运行配置

1. 用 DevEco Studio 按 `app/README.md` 在 `app/` 目录创建 **Empty Ability（ArkTS）** 工程，打开运行。
2. **网络权限**：`entry/src/main/module.json5` 的 `requestPermissions` 增加：
   ```json
   { "name": "ohos.permission.INTERNET" }
   ```
3. **本地明文 http**：开发期访问 `http://<host-ip>:8000` 需允许明文，按 SDK 版本在应用配置里放开调试用 http（上线 HAP 前改回并建议走 https/关闭明文）。
4. **后端地址**：App「设置」页填后端 base URL 并点「测试连接」。
   - 真机：手机与后端机同一 Wi-Fi，填后端机局域网 IP，如 `http://192.168.1.10:8000`；
   - 模拟器：优先宿主机局域网 IP；个别环境用回环别名（以 DevEco 模拟器网络说明为准，可参照 `http://10.0.2.2:8000`）。
5. 演示主流程：Tab1 选片/输入片名 → 发起采集 → Tab2/3/4 查看情感、热点与可视化。

## 五、常见问题排查

| 现象 | 处理 |
|---|---|
| `curl /health` 不通 | 后端是否启动、HOST 是否为 0.0.0.0、端口占用 |
| App 提示后端不通 | 设置页换地址/点测试连接；检查同一网络与防火墙放行 8000 |
| `/analyze/zh`、`/backfill` 返回 503 | `.env` 未配 `DEEPSEEK_API_KEY` 或 `DEEPSEEK_ENABLED` 非 true |
| `/analyze/en` 返回 503 | 缺 torch 或 `models/model.pt`（`model_ready=false`，看 `model.msg`） |
| 单片只能抓 ~100 | `.env` 配豆瓣完整 Cookie（`DOUBAN_COOKIES` 等）→ 自动 HTML 深翻到窗口尽头（实测单片可达 ~400） |
| 词云图打不开 | 是否已重启到含 wordcloud 库的版本；URL 拼对 BASE_URL；INTERNET+明文权限 |
| `pytest` 报连接/表错误 | 数据库文件损坏时删除 `data/*.db` 重新 `seed_db.py` |

## 六、AI 提示词说明（AI 辅助开发记录）

### 6.1 使用理念与总体脉络

本小组在课程开发全流程中借助 AI 编程助手（Claude Code）辅助实现。协作原则一句话概括：**关键决策由人、展开落地靠 AI、产出必复核**——技术选型、方案取舍、指标口径由成员确定；AI 负责把决策展开为可运行的代码与文档；AI 的每段产出都经成员阅读、并在真实环境验证后才合入主线。

基于这一原则，本组的提示词并非零散提问，而是沿一条清晰的工程脉络层层递进：

> **先让系统"能跑"（最小闭环）→ 接入真实数据源（真爬虫）→ 扩大样本、增强抗反爬能力（提量提稳）→ 统一情感口径、沉淀自有模型（提质）→ 完善可视化与联调 → 把过程固化为文档。**

### 6.2 分阶段记录：每个阶段「当时的工程问题 → 核心提示词 → 产物」

**阶段一 · 需求理解与方案设计**
- 思路：先把"题目 12（电影评论情感分析系统）"转成可执行设计，避免一上来就写代码。
- 核心提示词：
  - "先不写实现：就数据采集、情感分析、热点挖掘、可视化四个模块，给出候选技术路线与 3 人分工，并明确准确率、吞吐等指标如何测定。"
  - "先厘清数据定位：题目给的 IMDB 语料用于训练模型，而系统的价值在于能对任意真实影片自动采集评论并给出分析。"
- 产物：`docs/superpowers/specs/2026-09-02-movie-review-sentiment-analysis-design.md`（分工见规格 §10）。

**阶段二 · 工程骨架与协作规范**
- 思路：多人并行，先把仓库结构与协作纪律立起来，从源头减少冲突。
- 核心提示词：
  - "搭建 backend（FastAPI）与 app（ArkTS）骨架及 scripts/tests 占位，并按三位成员的分工落位。"
  - "建立 main/dev/feature 分支模型；把队友接入方式、每次开工先 pull、新建分支、测试/上线分支如何切换写清楚进 README，另单独放一份系统运行配置文档。"
- 产物：仓库骨架；根 `README.md` §6；本文档前五节。

**阶段三 · 数据采集（爬虫）**
- 思路：按"先离线闭环 → 再真实抓取 → 再提量提稳"三步推进。
- 核心提示词：
  1. "先实现离线样本包与 runner 的最小闭环：在线源未就绪时自动降级，确保采集链路先整体能跑通。"
  2. "架构别停在抽象层：先做豆瓣真实抓取，IMDB 在线抓取成本高则用公开数据集兜底；爬虫要分层（base/imdb/douban），职责清晰。"
  3. "样本量决定结论可信度：把 Cookie 池、代理池、多排序并集去重、并发数、单片上限制成可配置项，默认保持低调礼貌；被限流时先退避、再换身份重试，目标是把单片评论量从 120 提到数百乃至上千。"
  4. "抓片时顺带落库简介、海报、评分等元数据供前端展示；海报本地化伺服以规避防盗链；同一影片避免重复抓取，增加缓存与幂等。"
- 产物：`backend/app/crawler/`；灌入 `backend/data/moodreel.db`。

**阶段四 · 情感分析口径与多通道接入**
- 思路：先接队友的英文模型打通链路，再解决中文通道的成本与可用性，最后统一对外口径。
- 核心提示词：
  - "队友训练好的 TextCNN 以 model.pt 交付，如何在服务端按同结构加载做进程内推理？"
  - "百度情感 API 按量计费成本偏高：先压测本地英文模型；中文影评通道改接 DeepSeek，做成可开关、可回退的本地/云端路由。"
  - "对外统一为 positive/negative 二分类 + 置信度，移除 neutral 档，用置信度表达情感偏向的强度，中英文口径一致。"
- 产物：`backend/app/services/`（textcnn / deepseek / analytics）。

**阶段五 · 沉淀自有中文能力**
- 思路：云端通道逐条计费且依赖外网，改用真实采集数据自训中文模型，形成自主可控的分析能力。
- 核心提示词：
  - "想自训一个中文情感模型：抓十几部影片的真实评论、按星级自动建训练集，jieba 分词 + TextCNN 训练，输出与英文一致的二分类 + 置信度。"
  - "训练完成后如何回答验收指标？能否达到 200 条/秒的分析吞吐？请写 benchmark 离线测定。"
- 产物：`scripts/train_textcnn_zh.py`、`backend/models/zh/model_zh.pt`、`scripts/benchmark.py`。

**阶段六 · 可视化与前后端联调**
- 思路：让图表贴近真实产品观感，并尽早用队友前端验证契约。
- 核心提示词：
  - "情感趋势图按自然月聚合、横轴标'年-月'，不要按天打点；词云用成熟库生成真实排版，而不是两三个词占位。"
  - "海报与词云图应当是'后端本地生成、以 URL 交给前端拉取'，还是直接传文件？请把契约在接口文档里写死。"
  - "拉取队友新写的 App 实测是否满足其需求；队友新合入的代码如有需要我们配合调整之处，请指出来。"
- 产物：可视化相关接口、`backend/static/`、`docs/3_接口契约文档.md`。

**阶段七 · 联调、运行与文档沉淀**
- 思路：让任何一位队友拿到仓库都能独立跑起来，并能从日志直观看出系统在做什么。
- 核心提示词：
  - "后端如何启动/停止、局域网内队友如何访问、是否需要内网穿透——整理成可直接照做的运行步骤。"
  - "日志要能回答'系统正在干什么'：正在爬哪部影片、元数据摘要、抓取进度、词云生成、DeepSeek 调用进度都应有提示。"
  - "把接口由 MOCK 切换真实 HTTP 的说明，连同上述运行与日志约定一起补进文档并随代码入库。"
- 产物：`docs/4_日志与运行说明.md`、`环境配置指南.md`、接口契约文档。

### 6.3 小结与成员补录

> 以上阶段记录呈现的是一条从"可用"到"好用"的工程链路：AI 在其中承担展开与落地，方向与质量始终由人把关。本表由组长（成员A）补录；为满足课程"真实可核查"的要求，成员 B / C 请参照同一写法，在自己负责的模块处补录实际使用 AI 时的关键提示词：

| 补录成员 | 模块 | 需补内容 |
|---|---|---|
| 成员B | 英文 TextCNN 训练 / 评测 / 腾讯 adapter | 你实际给 AI 的关键提示词与对应产物 |
| 成员C | ArkTS UI / Canvas 图表 / 前端联调 | 同上 |

### 6.4 成员C 补录（前端 ArkTS UI / Canvas 图表 / 前端联调）

**阶段一 · 前端工程与页面骨架**
- 思路：先把鸿蒙工程立起来，用「主页 + 设置」两个 Tab 搭出可运行骨架，再逐步填充功能，避免一上来就堆细节。
- 核心提示词：
  - "用 DevEco 创建鸿蒙工程，先做一个简单的初步模型，底部设计两个栏目：主页、设置。"
  - "主页放搜索框和「搜索影视相关评价」按钮，点击后向后端发送含电影名和采集源的 JSON；设置页放夜间模式、采集源选择（豆瓣/IMDB）。"
  - "主页结果区依次展示：影片信息、情感分布、评论列表、Top 热点词、褒贬倾向词、评论趋势、词云。"
- 产物：`app/mood_reel_GUI/` 工程骨架（`pages/Index.ets`、`views/TabHome.ets`、`views/TabSettings.ets`）。

**阶段二 · 可视化图表（Canvas 自绘）**
- 思路：不依赖第三方图表库，用 ArkUI Canvas 自绘图表，满足情感分布、热点、趋势三类展示需求。
- 核心提示词：
  - "环形图用 Canvas 画正负情感占比，红色部分从 0 增长到指定比例做进场动画。"
  - "Top 热点词做横向条形图，柱子从 0 拉升；评论趋势做 Steam 风格的每日双柱图，横轴为连续日期。"
  - "褒贬倾向词分「夸什么 / 骂什么」两列，词云按权重缩放字号（后改为后端渲染 PNG）。"
- 产物：`components/charts/`（RingChart / BarChart / TrendChart / PolarityCompare）。

**阶段三 · UI 美化与动画**
- 思路：参考豆瓣 / IMDb 的极简风格，统一品牌色与卡片化设计，并加入开屏、登场等动画提升观感。
- 核心提示词：
  - "美化 UI，参考豆瓣/IMDb 风格，主色调深灰+白+品牌蓝；品牌色 #1A2C3E（深蓝黑）、#1890FF（亮蓝），背景 #F5F7FA，卡片纯白圆角带阴影。"
  - "增加开屏动画：Logo 由小变大+淡入、标题上滑、加载指示器，深蓝黑渐变背景，动画后跳转主页且返回键不回退。"
  - "增加卡片登场动画（滚入视口淡入上滑）、按钮按下缩放动画、夜间/白天主题切换。"
- 产物：`components/RevealCard.ets`、`pages/SplashPage.ets`、资源化颜色 `color.json`（base/dark）。

**阶段四 · 接口对接（真实 HTTP）**
- 思路：把 mock 数据切换为真实后端请求，严格对齐接口契约，打通「抓取 → 情感分析 → 展示」全流程。
- 核心提示词：
  - "把前端 mock 换成真实 HTTP（@ohos.net.http），严格按接口契约的 JSON 格式实现（字段 snake_case 对齐后端）。"
  - "补上「整片全流程」的情感分析步骤（POST /analyze/backfill），否则评论无标签、图表全 0。"
  - "抓取是异步任务：POST /crawl 后轮询 GET /crawl/{job_id} 直到完成。"
- 产物：`services/http.ets`、`services/api.ets`。

**阶段五 · 调试与体验优化**
- 思路：针对 ArkTS 编译报错、接口对接问题、长等待逐一修复，并优化加载与交互体验。
- 核心提示词：
  - "修复 ArkTS 编译错误（对象字面量需对应声明类型、.ets 后缀、import 路径、as 强转、内联对象不能当类型等）。"
  - "修复 HTTP 201 未当成功处理、Top 热点词 weight 是频次而非 0~1 比值的问题。"
  - "评论分页（初始 5 条 + 更多/收起）、单条评论展开收起、评论间分隔线。"
  - "边等待后端返回数据边渲染已完成的数据（增量渲染，先出影片信息再出图表）。"
- 产物：前端全部 `.ets` 源码；Git 提交（dev → main 上线）。
