# MoodReel · App（HarmonyOS ArkTS）

成员C 负责。本目录存放 **DevEco Studio 的 HarmonyOS 工程**（AppScope / entry 等）。

> ⚠️ DevEco 工程文件（module.json5、resources、构建配置等）由 DevEco Studio 生成，
> 不要手写，避免与本地 SDK/API 版本不匹配。建议按下面步骤创建后放到本目录。

## 创建工程（一次）

1. DevEco Studio → File → New → Create Project → **Empty Ability**
2. 工程名：`MoodReel`；语言 **ArkTS**；Compatible SDK 选你本机可用的 NEXT API（≥ API 10）
3. 把生成的全部内容拷贝到本 `app/` 目录（保持 AppScope、entry、oh-package.json5 等在 app/ 下）

> 也支持官方 AI 辅助工具链创建：`@deveco/deveco-cli` / `@deveco/deveco-code`（见课内《鸿蒙AI工具》文档）。

## 关键配置

- **网络权限**：`entry/src/main/module.json5` 的 requestPermissions 加
  `ohos.permission.INTERNET`；本地明文 http 需在调试期放开（联调 `http://<host-ip>:8000`）。
- **后端地址**：在 App「设置」页可配置 base URL（经 `PersistentStorage` 持久化，运行时统一走 `getBaseUrl()`），默认填宿主机局域网 IP。
- **模拟器 → 宿主机**：优先宿主局域网 IP；个别环境用回环别名（以 DevEco 文档为准）。

## 页面规划（实际落地为 2 个页签 + 登录注册页，对应后端接口，契约见 `docs/...-design.md` §6）

| 页面 | 功能 | 主要后端接口 |
|---|---|---|
| Tab1 主页 | 「为你推荐」横滑卡片（个性化/热点，点卡片直达分析）→输入片名→发起抓取→轮询进度→影片信息（简介/海报/评分）→情感分布（环形图）→评论列表（分页/展开）→Top 热点词（条形图）→褒贬倾向词→词云（PNG）→评论趋势（双柱图） | `GET /recommend` `POST /crawl` `GET /crawl/{id}` `GET /crawl/movies` `GET /crawl/movie/{id}` `POST /analyze/backfill` `GET /dataset/stats` `GET /dataset/reviews` `GET /hotspot` `GET /viz/summary` `GET /viz/wordcloud` |
| Tab2 设置 | 用户卡片（去登录/退出登录）、后端地址、测试连接(`/health`)、夜间模式、采集源选择 | `GET /health` |
| 登录/注册页（AuthPage） | 开屏后未登录自动进入；登录/注册切换、表单校验、注册成功自动登录、底部「游客进入」（游客可用全部主流程） | `POST /auth/register` `POST /auth/login` |

## 建议模块划分（entry/src/main/ets/）

```
pages/         # SplashPage（开屏动画）+ Index（Tabs 容器，2 个页签）+ AuthPage（登录/注册）
views/         # TabHome（主页：搜索→抓取→分析→图表全流程）、TabSettings（设置）
services/
  http.ets     # @ohos.net.http 封装（超时/错误码/JSON）
  api.ets      # 上述接口类型化封装（改后端契约只动这里）
components/
  charts/      # Canvas 自绘：环形 RingChart / 条形 BarChart / 趋势双柱 TrendChart / 褒贬对比 PolarityCompare
  RevealCard.ets  # 结果卡片入场动画容器（词云为后端 PNG，前端 Image 直接加载，无端侧排版）
model/         # ArkTS 数据类型（与后端 schemas 对齐）
common/        # 常量（默认后端地址）、状态管理
```

HTTP 客户端封装成单一模块（`services/http.ts`）便于联调替换与统一报错。
