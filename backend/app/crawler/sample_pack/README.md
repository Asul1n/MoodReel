# 离线样本包（成员A维护）

**作用**：现场断网 / 目标站反爬拦截时，保证"采集→分析→可视化"演示不断链的兜底数据。
任务执行器会**先尝试在线抓取，未实现或失败时自动降级到本样本包**（job.status = degraded）。

## 目录约定

```
sample_pack/
├─ manifest.json            # 影片目录：movie_id/title/year/source/key/note
├─ imdb/{key}.csv           # 列：text,sentiment（sentiment 可选 positive/negative）
└─ douban/{key}.csv         # 列：text,stars（1-5）
```

添加一部离线影片的步骤：
1. 把样本 csv 放进 `imdb/` 或 `douban/`（文件名 = key）；
2. 在 `manifest.json` 里登记影片（movie_id 形如 `imdb:tt0111161` / `douban:1292052`）。

## ⚠️ 重要

当前 csv 内是**开发用示例占位文本**（便于离线跑通全链路），**不是真实用户评论**。
正式演示/提交前，请成员A用真实抓取（或公开样本）替换并更新 manifest 的 note。
数据仅供本项目教学分析：公开只读、低频率抓取、不涉及账号数据。
