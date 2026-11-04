"""方面体系（Aspect Inventory）—— 标注规范与 ABSA 抽取器的唯一定义源。

为什么要有这个模块：方面级情感分析（ABSA）里最容易出错的地方不是模型，
而是「什么叫演技」这件事在不同环节的口径不一致——标注同学按自己的理解标，
抽取器按另一套关键词抽，最后 P/R/F1 就没法解释。因此把方面定义收在
一处，标注文档、抽样脚本、抽取器、评估脚本全部 import 这里。

本系统限定为**封闭式方面集（closed inventory）**：只标这 6 个方面，
评论里提到但不在集合内的内容记入 other 备注列而不计入指标。封闭集
换来的是可直接计算的一致性指标与可比的 P/R/F1；开放式抽取（open IE）
虽然覆盖面更宽，但无法定义「漏抽」的边界，也就无法报召回率。

方面选取参考了电影评论 ABSA 的常见划分（story / acting / visual /
pace / music / theme），并针对豆瓣影评的实际措辞做过调整：豆瓣用户
高频提「三观」「立意」「看完哭了」，若只留 story 会把这些全归错类，
故单列 theme。
"""
from __future__ import annotations

from dataclasses import dataclass

# 极性的三档编码。用单字符而不是 1/0/-1，是为了在 Excel 里手填时
# 只需按一个键，且不会被表格软件自动转成数字格式。
POLARITY_POS = "+"
POLARITY_NEU = "0"
POLARITY_NEG = "-"
# 未提及（该方面在这条评论里没有出现）。空单元格与「标了但漏填」在 CSV 里
# 无法区分，因此显式用 NA 表示「确认未提及」。
POLARITY_NA = "NA"

VALID_POLARITIES = (POLARITY_POS, POLARITY_NEU, POLARITY_NEG, POLARITY_NA)

# 数值映射：NA 不参与极性均值的计算，因此单独给 None。
POLARITY_VALUE = {
    POLARITY_POS: 1,
    POLARITY_NEU: 0,
    POLARITY_NEG: -1,
    POLARITY_NA: None,
}


@dataclass(frozen=True)
class Aspect:
    """单个方面的定义。cues 只作为标注时的理解辅助与抽取器的弱信号，
    不作为判定依据——「提到了剧情」最终仍由标注者判断。"""

    key: str
    name_zh: str
    name_en: str
    definition: str
    cues: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name_zh": self.name_zh,
            "name_en": self.name_en,
            "definition": self.definition,
            "cues": list(self.cues),
        }


# 顺序即标注表的列顺序，也即论文表格的行顺序。调整顺序会改变
# 导出 CSV 的列序，破坏已有标注文件的对应关系，因此不建议改动。
ASPECTS: tuple[Aspect, ...] = (
    Aspect(
        key="plot",
        name_zh="剧情",
        name_en="story",
        definition=(
            "故事本身：剧本结构、情节合理性、叙事手法、改编忠实度、逻辑漏洞。"
            "评价「讲了个什么故事、讲得通不通」归此类。"
        ),
        cues=("剧情", "故事", "剧本", "情节", "叙事", "改编", "逻辑", "设定",
              "结尾", "结局", "桥段", "套路", "转折", "伏笔"),
    ),
    Aspect(
        key="act",
        name_zh="表演",
        name_en="acting",
        definition=(
            "演员的演技与角色塑造：表情、台词功底、情绪传递、选角是否贴脸。"
            "评价「谁演得好不好」归此类。"
        ),
        cues=("演技", "表演", "演员", "主演", "演得", "角色", "塑造", "选角",
              "面瘫", "台词", "表情", "入戏", "出戏", "演技派", "影帝"),
    ),
    Aspect(
        key="vis",
        name_zh="视听",
        name_en="visual",
        definition=(
            "画面与影像呈现：摄影、构图、色调、特效、服化道、美术、镜头语言。"
            "评价「看起来好不好看、特效真不真」归此类。"
        ),
        cues=("画面", "镜头", "摄影", "特效", "视觉", "色调", "构图", "美术",
              "服化道", "服装", "场景", "CG", "3D", "IMAX", "质感"),
    ),
    Aspect(
        key="pace",
        name_zh="节奏",
        name_en="pacing",
        definition=(
            "叙事节奏与剪辑：是否拖沓、是否仓促、时长是否合适、剪辑是否跳。"
            "评价「看着累不累、闷不闷」归此类。"
        ),
        cues=("节奏", "拖沓", "冗长", "仓促", "剪辑", "闷", "无聊", "犯困",
              "节奏慢", "节奏快", "注水", "时长", "看不下去"),
    ),
    Aspect(
        key="music",
        name_zh="配乐",
        name_en="music",
        definition=(
            "配乐与音效：主题曲、插曲、背景音乐、声音设计。"
            "评价「音乐好不好听、声音震不震撼」归此类。"
        ),
        cues=("配乐", "音乐", "主题曲", "插曲", "BGM", "音效", "声音", "原声",
              "片尾曲", "听觉"),
    ),
    Aspect(
        key="theme",
        name_zh="主题",
        name_en="theme",
        definition=(
            "主题立意与情感共鸣：想表达什么、价值观、思想深度、是否打动人。"
            "评价「看完想到什么、有没有被触动、三观正不正」归此类。"
        ),
        cues=("主题", "立意", "内涵", "深度", "意义", "价值观", "三观", "感动",
              "哭了", "共鸣", "触动", "治愈", "温暖", "讽刺", "隐喻", "哲理"),
    ),
)

ASPECT_KEYS: tuple[str, ...] = tuple(a.key for a in ASPECTS)
ASPECT_BY_KEY: dict[str, Aspect] = {a.key: a for a in ASPECTS}


def get_aspect(key: str) -> Aspect:
    """按 key 取方面定义，未知 key 直接报错——静默返回 None 会让
    抽取器把拼错的方面名当成「未提及」，错误被藏起来。"""
    try:
        return ASPECT_BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"未知方面 {key!r}，可选值：{', '.join(ASPECT_KEYS)}") from None


def normalize_polarity(raw: str | None) -> str:
    """把人工填写的各种写法归一成四档编码。

    容忍的写法是为了减少标注返工：Excel 里 `+1` 会被存成 `1`，
    中文输入法可能打出全角 `＋`，有些人习惯写 `pos` / `neg`。
    无法识别的内容一律报错而不是猜——标注数据出错必须立刻发现。
    """
    if raw is None:
        return POLARITY_NA
    text = str(raw).strip()
    if text == "" or text.upper() in ("NA", "N/A") or text in ("无", "未提及"):
        return POLARITY_NA

    # 全角转半角
    text = text.replace("＋", "+").replace("－", "-")
    lowered = text.lower()

    if lowered in ("+", "+1", "1", "pos", "positive", "正", "好评", "正面"):
        return POLARITY_POS
    if lowered in ("0", "neu", "neutral", "中", "中性", "混合", "mixed"):
        return POLARITY_NEU
    if lowered in ("-", "-1", "neg", "negative", "负", "差评", "负面"):
        return POLARITY_NEG
    raise ValueError(f"无法识别的极性取值 {raw!r}，允许：+ / 0 / - / NA")


def polarity_to_value(polarity: str) -> int | None:
    """极性编码转数值（NA → None）。"""
    return POLARITY_VALUE[normalize_polarity(polarity)]


# ======================= 证据片段（evidence span）=======================


def format_evidence(spans: dict[str, str]) -> str:
    """把 {方面: 原文片段} 编码成单元格字符串，形如 `act:演得真好;plot:剧情稀碎`。

    用分号分隔、冒号定位，是为了在 Excel 单格里可读可改；片段本身若含
    分号会破坏结构，因此写入前把分号替换成全角，并保证片段内不含冒号。
    """
    parts = []
    for key, span in spans.items():
        get_aspect(key)                      # 校验方面名，拼错立刻报错
        cleaned = str(span).replace(";", "；").replace(":", "：").strip()
        if cleaned:
            parts.append(f"{key}:{cleaned}")
    return ";".join(parts)


def parse_evidence(raw: str | None) -> dict[str, str]:
    """解析证据片段单元格，返回 {方面: 片段}。

    容错策略：无法解析的条目跳过而不是整体失败——标注文件里出现一个
    格式小错不该让整批数据作废，跳过项由调用方统计并提示。
    """
    if not raw or not str(raw).strip():
        return {}
    spans: dict[str, str] = {}
    for chunk in str(raw).split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        key, _, span = chunk.partition(":")
        key = key.strip()
        span = span.strip()
        if key in ASPECT_BY_KEY and span:
            spans[key] = span
    return spans


def aspects_of(row: dict) -> dict[str, str]:
    """从一行标注数据里取出各方面的极性，仅保留非 NA 的方面。

    列名约定为 `asp_<key>`，与 sample_annotation.py 导出的表头一致。
    """
    out: dict[str, str] = {}
    for key in ASPECT_KEYS:
        polarity = normalize_polarity(row.get(f"asp_{key}"))
        if polarity != POLARITY_NA:
            out[key] = polarity
    return out
