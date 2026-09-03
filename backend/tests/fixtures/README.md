# 爬虫测试夹具（fixtures）

- `douban_interests.json` —— （可选，不入库）豆瓣 rexxar 接口返回的真实短评 JSON。
  在能打开豆瓣的机器上运行以下命令生成：
  ```bash
  python scripts/dump_douban_json.py --sid 1292052
  ```
  存在该文件时，`tests/test_douban.py::test_parse_real_interests` 自动启用。

> 说明：豆瓣网页版短评是 JS 渲染，直接 GET 拿不到内容；真实评论走移动端
> `rexxar` JSON 接口（`app/crawler/douban.py` 已实现）。此夹具仅用于单测与留档。
