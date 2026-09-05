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

## 六、AI 提示词说明（记录本小组使用 AI 辅助开发的情况）

| 阶段 | 用途 | 使用的 AI 工具 | 关键提示词（要点） | 产物/文件 |
|---|---|---|---|---|
| 需求与设计 | 把题目12转成可执行设计（架构/数据/接口） | Claude Code（/brainstorming） | 题干 + "鸿蒙 app 如何实现"，要求给候选方案、量化指标测定方式 | `docs/superpowers/specs/2026-09-02-…-design.md` |
| 工程骨架 | 生成仓库结构与契约占位 | Claude Code | 按设计 §3.1 建 backend/scripts/tests 与 app 占位 | `backend/`、`app/` |
| Git 规范 | 编写协作分支流程与配置文档 | Claude Code | 输出分支模型/main-dev/feature 及 pull/merge 命令 | 根 `README.md` §6、本文档 |
| （成员A 补）爬虫 | 双源采集实现 | — | 记录你给 AI 的关键提示词 | `backend/app/crawler/` |
| （成员B 补）模型 | TextCNN 训练与腾讯 adapter | — | 同上 | `scripts/train_textcnn.py` 等 |
| （成员C 补）UI | ArkTS 页面与图表 | — | 同上 | `app/` |

> 说明：以上"关键提示词"请各成员在真正用 AI 辅助实现时补录真实内容（保留一两条最典型即可），作为课程要求的 AI 使用记录，做到真实可核查。
