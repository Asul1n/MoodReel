"""把热点词列表渲染成"真实网页风格"词云 PNG（多词、错落、带旋转）。

用 PIL 自绘：词按权重从大到小，沿螺旋找空位、部分随机旋转 ±30°；
放不下就自动缩小再试，最终尽量让所有词都落上去。不依赖外部 wordcloud 库。
"""
import math
import random
from io import BytesIO

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Ubuntu/Debian
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",                        # macOS
    "C:/Windows/Fonts/msyh.ttc",                                 # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",
]
_COLORS = ["#1E5A9E", "#2E7D32", "#C62828", "#6A1B9A",
           "#E65100", "#37474F", "#00796B", "#1565C0",
           "#8E24AA", "#00897B", "#5D4037", "#455A64"]


def _pick_font_path() -> str:
    import os
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到中文字体，请安装 Noto CJK 或把路径加进 _FONT_CANDIDATES")


def _collides(box: tuple, boxes: list[tuple], pad: int = 6) -> bool:
    x0, y0, x1, y1 = box
    for a0, b0, a1, b1 in boxes:
        if not (x1 + pad < a0 or a1 + pad < x0 or y1 + pad < b0 or b1 + pad < y0):
            return True
    return False


def build(words: list[dict], width: int = 1000, height: int = 620,
          max_size: int = 80, min_size: int = 12) -> bytes:
    """words: [{word, weight}, ...] -> PNG bytes。"""
    from PIL import Image, ImageDraw, ImageFont

    ws = [w for w in (words or []) if (w.get("word") or "").strip()]
    if not ws:
        ws = [{"word": "暂无热词", "weight": 1}]
    maxw = max((float(w.get("weight") or 1.0)) for w in ws)
    if maxw <= 0:
        maxw = 1.0
    font_path = _pick_font_path()

    # 权重 -> 字号：亚线性，避免少数大词霸屏
    items = []
    for w in ws:
        ratio = float(w.get("weight") or 1.0) / maxw
        size = int(min_size + (max_size - min_size) * (ratio ** 0.6))
        items.append((str(w["word"]).strip(), size))
    items.sort(key=lambda x: x[1], reverse=True)

    img = Image.new("RGBA", (width, height), (250, 250, 252, 255))
    cx, cy = width / 2, height / 2
    placed: list[tuple] = []

    for idx, (word, size0) in enumerate(items):
        color = _COLORS[idx % len(_COLORS)]
        size = size0
        ok = False
        for _ in range(10):                      # 放不下则缩小重试
            font = ImageFont.truetype(font_path, size)
            l, t, r, b = font.getbbox(word)
            tw, th = r - l, b - t
            pad = 24
            layer = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            d.text((pad, pad), word, font=font, fill=color)
            angle = 0.0
            if size0 > min_size + 6 and random.random() < 0.45:
                angle = float(random.choice((-30, -20, -12, 12, 20, 30)))
            if angle:
                layer = layer.rotate(angle, expand=True,
                                     resample=Image.Resampling.BICUBIC)
            ww, hh = layer.size
            box = None
            for s in range(1, 6000):             # 阿基米德螺旋找空位
                a = 0.12 * s
                rad = 1.9 * math.sqrt(s)
                x = int(cx + rad * math.cos(a) - ww / 2)
                y = int(cy + rad * math.sin(a) - hh / 2)
                x = max(2, min(width - ww - 2, x))
                y = max(2, min(height - hh - 2, y))
                cand = (x, y, x + ww, y + hh)
                if not _collides(cand, placed, pad=6):
                    box = cand
                    break
            if box is not None:
                img.alpha_composite(layer, (box[0], box[1]))
                placed.append(box)
                ok = True
                break
            size = int(size * 0.8)
            if size < min_size:
                break
        if not ok:      # 极少数实在放不下，跳过（不影响整体）
            continue

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
