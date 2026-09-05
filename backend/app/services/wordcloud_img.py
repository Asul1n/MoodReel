"""词云 PNG：直接调用 Python wordcloud 库（真实网页风格：碰撞检测+随机旋转+渐变配色）。

依赖：wordcloud（会自动带上 Pillow / numpy / matplotlib）。中文字体自动探测。
"""
from io import BytesIO

from wordcloud import WordCloud

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Ubuntu/Debian
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",                        # macOS
    "C:/Windows/Fonts/msyh.ttc",                                 # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",
]

_last_placed = 0   # 最近一次 build 实际画出的词数（诊断/日志用）


def _pick_font_path() -> str:
    import os
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到中文字体，请安装 Noto CJK 或把路径加进 _FONT_CANDIDATES")


def build(words: list[dict], width: int = 1000, height: int = 620,
          max_words: int = 200) -> bytes:
    """words: [{word, weight}, ...] -> PNG bytes（wordcloud 库渲染）。"""
    global _last_placed
    freqs: dict[str, float] = {}
    for w in words or []:
        word = (w.get("word") or "").strip()
        if word:
            freqs[word] = max(float(w.get("weight") or 1.0), 0.1)
    if not freqs:
        freqs = {"暂无热词": 1.0}

    wc = WordCloud(
        font_path=_pick_font_path(),
        width=width, height=height,
        background_color="#FAFAFC",
        margin=2,
        prefer_horizontal=0.75,          # 部分词旋转，更像真实词云
        min_font_size=12,
        max_font_size=100,
        max_words=max_words,
        random_state=42,                 # 固定随机种子：每次生成稳定
        colormap="tab10",
    )
    wc.generate_from_frequencies(freqs)
    _last_placed = len(wc.words_)

    img = wc.to_image()
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
