# 离线样本包（成员A收集）

**作用**：现场断网 / 目标站反爬拦截时，保证"采集→分析→可视化"演示不断链的兜底数据。
**内容**：预置约 5 部知名影片（英文 IMDB、中文豆瓣各覆盖），每部约 100+ 条影评。

目录约定：

```
sample_pack/
├─ imdb/{movie_id}.csv      # 列：text[,sentiment]   （movie_id 形如 imdb:tt0111161）
└─ douban/{movie_id}.csv    # 列：text[,stars]        （movie_id 形如 douban:1292052）
```

文件头部注释标注：影片、年份、来源页 URL、收集日期、是否人工标注情感。
数据仅供本项目教学分析，公开只读、不涉及账号数据。
