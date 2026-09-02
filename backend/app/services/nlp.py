"""评论热点挖掘（成员B）。

对所选上下文产出三类可解释结果：
1. top_keywords —— 停用词过滤 + TF-IDF/高频
2. polarity_pos / polarity_neg —— 词在正/负评中的分布差异（口径公式写入报告）
3. cloud —— 加权词表供 App 渲染

中文语料先 jieba 分词；英文用英文停用词表。
"""
from sqlalchemy.orm import Session


def build_hotspot(
    db: Session,
    context: str,  # "whole" 或 "movie:{movie_id}"
    top_n: int = 30,
) -> dict:
    raise NotImplementedError("成员B实现：热点词 / 褒贬倾向词 / 词云数据")
