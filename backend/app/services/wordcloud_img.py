"""把热点词列表渲染成词云 PNG 图片（供前端 Image 直接展示 / 导出）。

用 PIL 自绘（螺旋放置、字号按权重、随机配色），避免引入 wordcloud 依赖；
PIL / 中文字体在多数系统可用。依赖中文字体，找不到时报错会给出提示。
"""
import math
from io import BytesIO

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Ubuntu/Debian
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",                        # macOS
    "C:/Windows/Fonts/msyh.ttc",                                 # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",
]
_COLORS = ["#1E5A9E", "#2E7D32", "#C62828", "#6A1B9A",
           "#E65100", "#37474F", "#00796B", "#1565C0"]


def _pick_font_path() -> str:
    import os
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到中文字体，请安装 Noto CJK 或把路径加进 _FONT_CANDIDATES")


def build(words: list[dict], width: int = 900, height: int = 560,
          max_size: int = 110, min_size: int = 16) -> bytes:
    """words: [{word, weight}, ...] -> PNG bytes。"""
    from PIL import Image, ImageDraw, ImageFont

    ws = [w for w in (words or []) if (w.get("word") or "").strip()]
    if not ws:
        ws = [{"word": "暂无热词", "weight": 1}]
    maxw = max((float(w.get("weight") or 1.0)) for w in ws)
    if maxw <= 0:
        maxw = 1.0
    font_path = _pick_font_path()

    items = []
    for w in ws:
        size = int(min_size + (max_size - min_size)
                   * math.sqrt(float(w.get("weight") or 1.0) / maxw))
        items.append((str(w["word"]).strip(), size))
    items.sort(key=lambda x: x[1], reverse=True)

    img = Image.new("RGBA", (width, height), (250, 250, 252, 255))
    draw = ImageDraw.Draw(img)
    placed: list[tuple] = []
    cx, cy = width / 2, height / 2

    for idx, (word, size) in enumerate(items):
        font = ImageFont.truetype(font_path, size)
        l, t, r, b = font.getbbox(word)
        tw, th = r - l, b - t
        box = None
        for step in range(1, 3000):          # 阿基米德螺旋找空位
            a = 0.25 * step
            rad = 2.3 * math.sqrt(step)
            x = max(2.0, min(width - tw - 2, cx + rad * math.cos(a) - tw / 2))
            y = max(2.0, min(height - th - 2, cy + rad * math.sin(a) - th / 2))
            cand = (int(x), int(y), int(x + tw), int(y + th))
            if not _collides(cand, placed):
                box = cand
                break
        if box is None:
            continue
        placed.append(box)
        draw.text((box[0], box[1]), word, font=font, fill=_COLORS[idx % len(_COLORS)])

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _collides(box: tuple, boxes: list[tuple], pad: int = 6) -> bool:
    x0, y0, x1, y1 = box
    for a0, b0, a1, b1 in boxes:
        if not (x1 + pad < a0 or a1 + pad < x0 or y1 + pad < b0 or b1 + pad < y0):
            return True
    return False
