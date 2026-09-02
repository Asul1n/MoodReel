# 爬虫解析测试夹具（fixtures）

- `douban_comments_sample.html` —— **开发用模拟页**，保证解析器在无网络时也能单测。
- `douban_comments.html` —— **真实豆瓣短评页**（可选，不入库）。

## 用真实页面校准豆瓣爬虫

在本机能正常打开豆瓣的机器上运行：

```bash
cd backend
python scripts/save_douban_page.py --sid 1292052
```

脚本会抓该片短评第一页存到 `tests/fixtures/douban_comments.html` 并打印解析出的条数。
存在该文件时，`tests/test_douban_parser.py::test_parse_real_douban_page` 会自动启用；
若豆瓣改版解析不到，把该文件给我（成员A），我按新结构改 `douban.py` 的选择器。

> `douban_comments.html` 建议不入 git（页面可能较大、含公开评论文本）。已 gitignore `backend/dumps/`。
