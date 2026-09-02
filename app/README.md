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
- **后端地址**：在 App「设置」页可配置 base URL（存 Preferences），默认填宿主机局域网 IP。
- **模拟器 → 宿主机**：优先宿主局域网 IP；个别环境用回环别名（以 DevEco 文档为准）。

## 页面规划（对应后端接口，契约见 `docs/...-design.md` §6）

| 页签 | 功能 | 主要后端接口 |
|---|---|---|
| Tab1 采集 | 选片/输入片名→发起抓取→轮询进度→新增评论 | `POST /crawl` `GET /crawl/{id}` `GET /crawl/movies` `POST /dataset/ingest` |
| Tab2 情感 | 批量分析(计数/吞吐)、单条中/英文输入、双引擎对照 | `POST /analyze` `/analyze/en` `/analyze/zh` `/compare` |
| Tab3 热点 | 词云(加权标签排版)、Top 词、褒贬倾向词 | `GET /hotspot` |
| Tab4 可视化 | 环形/条形/趋势图（Canvas 自绘） | `GET /viz/summary` |
| Tab5 设置 | 后端地址、测试连接(`/health`)、腾讯开关 | `GET /health` |

## 建议模块划分（entry/src/main/ets/）

```
pages/         # 5 个页签 + 详情
services/
  http.ts      # @ohos.net.http 封装（超时/错误码/JSON）
  api.ts       # 上述接口类型化封装（改后端契约只动这里）
components/
  charts/      # Canvas 自绘：环形/条形/柱状
  wordcloud/   # 加权标签词云排版
model/         # ArkTS 数据类型（与后端 schemas 对齐）
common/        # 常量（默认后端地址）、状态管理
```

HTTP 客户端封装成单一模块（`services/http.ts`）便于联调替换与统一报错。
