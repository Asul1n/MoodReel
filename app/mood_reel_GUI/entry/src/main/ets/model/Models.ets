// 数据模型与模拟数据（字段对齐后端 schemas.py，后端就绪后替换 MOCK_*）

export interface Movie {
  movieId: string;
  title: string;
  year: number;
  source: string; // douban / imdb
}

// 情感分布（二分类）
export interface SentimentDist {
  positive: number;
  negative: number;
}

// 评论（已带情感标签）
export interface Review {
  id: number;
  text: string;
  lang: string;   // en / zh
  model: string;  // textcnn / tencent
  label: string;  // positive / negative
  prob: number;   // 0~1
}

// 热点词（词云 / Top 热点词共用）
export interface KeywordItem {
  keyword: string;
  weight: number; // 0~1
}

// 褒贬倾向词
export interface PolarityItem {
  word: string;
  score: number; // 0~1
}

export interface PolarityData {
  pos: PolarityItem[];
  neg: PolarityItem[];
}

// 趋势点（累计评论数）
export interface TrendItem {
  label: string;
  count: number;
}

// 搜索历史
export interface HistoryItem {
  keyword: string;
  source: string;
}

// ===== 模拟数据 =====

export const MOCK_DIST: SentimentDist = { positive: 68, negative: 32 };

export const MOCK_REVIEWS: Review[] = [
  { id: 1, text: 'Absolutely brilliant, a must-watch classic.', lang: 'en', model: 'textcnn', label: 'positive', prob: 0.96 },
  { id: 2, text: '剧情拖沓，后半段不知所云。', lang: 'zh', model: 'tencent', label: 'negative', prob: 0.82 },
  { id: 3, text: '画面精美，演技在线，强烈推荐。', lang: 'zh', model: 'tencent', label: 'positive', prob: 0.88 },
  { id: 4, text: '节奏太慢，中途差点睡着。', lang: 'zh', model: 'tencent', label: 'negative', prob: 0.71 },
];

export const MOCK_KEYWORDS: KeywordItem[] = [
  { keyword: '特效', weight: 0.95 },
  { keyword: '剧情', weight: 0.88 },
  { keyword: '演员', weight: 0.80 },
  { keyword: '画面', weight: 0.72 },
  { keyword: '节奏', weight: 0.60 },
  { keyword: '配乐', weight: 0.55 },
  { keyword: '台词', weight: 0.48 },
  { keyword: '结局', weight: 0.40 },
  { keyword: '导演', weight: 0.33 },
  { keyword: '彩蛋', weight: 0.25 },
  { keyword: '字幕', weight: 0.18 },
  { keyword: '票价', weight: 0.12 },
];

export const MOCK_POLARITY: PolarityData = {
  pos: [
    { word: '特效', score: 0.90 },
    { word: '演技', score: 0.82 },
    { word: '剧情', score: 0.70 },
    { word: '画面', score: 0.60 },
  ],
  neg: [
    { word: '节奏', score: 0.78 },
    { word: '结局', score: 0.62 },
    { word: '配音', score: 0.50 },
    { word: '时长', score: 0.35 },
  ],
};

export const MOCK_TREND: TrendItem[] = [
  { label: '周一', count: 12 },
  { label: '周二', count: 28 },
  { label: '周三', count: 45 },
  { label: '周四', count: 58 },
  { label: '周五', count: 76 },
  { label: '周六', count: 90 },
  { label: '周日', count: 100 },
];
