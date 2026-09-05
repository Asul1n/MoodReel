// 数据模型（字段对齐契约 §3/§4 的 JSON，snake_case 与后端一致）

// 影片元数据（MovieMeta）
export interface Movie {
  movie_id: string;
  title: string;
  year: number;
  source: string;
  source_url: string;
  intro: string;
  poster: string;
  rating: number;
  genres: string;
  review_count: number;
}

// 情感分布（二分类）
export interface SentimentDist {
  positive: number;
  negative: number;
}

// 评论（ReviewOut）
export interface Review {
  id: number;
  text: string;
  lang: string;
  source: string;
  movie_id: string;
  pred_label: string;   // positive / negative（可能为空）
  pred_prob: number;    // 置信度（可能为 null）
}

// 热点词 / 褒贬词（契约 {word, weight}）
export interface KeywordItem {
  word: string;
  weight: number;
}

export interface PolarityItem {
  word: string;
  weight: number;
}

export interface PolarityData {
  pos: PolarityItem[];
  neg: PolarityItem[];
}

// 每日评论趋势
export interface TrendDay {
  date: string;
  positive: number;
  negative: number;
}

// 搜索历史（本地）
export interface HistoryItem {
  keyword: string;
  source: string;
}

// ===== 以下 MOCK 数据仅供后端未就绪时调试，真实联调走 services/api.ets =====

export const MOCK_MOVIE: Movie = {
  movie_id: 'douban:1889243',
  title: '星际穿越',
  year: 2014,
  source: 'douban',
  source_url: 'https://movie.douban.com/subject/1889243/',
  intro: '近未来的地球黄沙遍野，人类面临灭绝危机。前 NASA 宇航员库珀带领团队穿越虫洞，前往未知星系寻找人类的新家园。',
  poster: '/static/posters/douban_1889243.jpg',
  rating: 9.4,
  genres: '剧情 / 科幻 / 冒险',
  review_count: 60,
};

export const MOCK_DIST: SentimentDist = { positive: 68, negative: 32 };

export const MOCK_REVIEWS: Review[] = [
  { id: 1, text: 'Absolutely brilliant, a must-watch classic.', lang: 'en', source: 'imdb_live', movie_id: 'imdb:tt0111161', pred_label: 'positive', pred_prob: 0.96 },
  { id: 2, text: '剧情拖沓，后半段不知所云。', lang: 'zh', source: 'douban_live', movie_id: 'douban:1889243', pred_label: 'negative', pred_prob: 0.82 },
  { id: 3, text: '画面精美，演技在线，强烈推荐。', lang: 'zh', source: 'douban_live', movie_id: 'douban:1889243', pred_label: 'positive', pred_prob: 0.88 },
  { id: 4, text: '节奏太慢，中途差点睡着。', lang: 'zh', source: 'douban_live', movie_id: 'douban:1889243', pred_label: 'negative', pred_prob: 0.71 },
];

export const MOCK_KEYWORDS: KeywordItem[] = [
  { word: '特效', weight: 88 },
  { word: '剧情', weight: 76 },
  { word: '演员', weight: 64 },
  { word: '画面', weight: 58 },
  { word: '节奏', weight: 47 },
  { word: '配乐', weight: 42 },
  { word: '台词', weight: 36 },
  { word: '结局', weight: 30 },
  { word: '导演', weight: 24 },
  { word: '彩蛋', weight: 18 },
  { word: '字幕', weight: 12 },
  { word: '票价', weight: 8 },
];

export const MOCK_POLARITY: PolarityData = {
  pos: [
    { word: '特效', weight: 90 },
    { word: '演技', weight: 82 },
    { word: '剧情', weight: 70 },
    { word: '画面', weight: 60 },
  ],
  neg: [
    { word: '节奏', weight: 78 },
    { word: '结局', weight: 62 },
    { word: '配音', weight: 50 },
    { word: '时长', weight: 35 },
  ],
};

export const MOCK_TREND: TrendDay[] = [
  { date: '2024-01', positive: 12, negative: 4 },
  { date: '2024-02', positive: 18, negative: 6 },
  { date: '2024-03', positive: 0, negative: 0 },
  { date: '2024-04', positive: 25, negative: 9 },
  { date: '2024-05', positive: 30, negative: 12 },
  { date: '2024-06', positive: 22, negative: 8 },
  { date: '2024-07', positive: 0, negative: 0 },
  { date: '2024-08', positive: 28, negative: 10 },
  { date: '2024-09', positive: 35, negative: 14 },
  { date: '2024-10', positive: 40, negative: 16 },
  { date: '2024-11', positive: 0, negative: 0 },
  { date: '2024-12', positive: 33, negative: 11 },
];
