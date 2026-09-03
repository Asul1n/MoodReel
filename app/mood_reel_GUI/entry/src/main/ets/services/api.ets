// 后端接口封装（模板版：返回模拟数据，TODO 标注真实 HTTP 调用位置）
import {
  SentimentDist,
  Review,
  KeywordItem,
  PolarityData,
  TrendItem,
  MOCK_DIST,
  MOCK_REVIEWS,
  MOCK_KEYWORDS,
  MOCK_POLARITY,
  MOCK_TREND
} from '../model/Models';

// POST /crawl {source, query, limit} → {job_id}
export function crawlMovie(query: string, source: string): string {
  // TODO: 真实实现 http POST `${BASE_URL}/crawl`，body 为 { source, query, limit }
  return `mock-job-${source}-${query}`;
}

// GET /viz/summary?context=movie:{id} → 情感分布等聚合数据
export function fetchSentimentDist(): SentimentDist {
  // TODO: 真实实现 GET `${BASE_URL}/viz/summary?context=movie:{id}`
  return MOCK_DIST;
}

// GET /dataset/reviews?movie_id=... → 评论分页列表
export function fetchReviews(): Review[] {
  // TODO: 真实实现 GET `${BASE_URL}/dataset/reviews?movie_id=...`
  return MOCK_REVIEWS;
}

// GET /hotspot?context=... → 热点词
export function fetchKeywords(): KeywordItem[] {
  // TODO: 真实实现 GET `${BASE_URL}/hotspot?context=movie:{id}`
  return MOCK_KEYWORDS;
}

// 褒贬倾向词（规格 §5.3 polarity_pos/polarity_neg）
export function fetchPolarity(): PolarityData {
  // TODO: 真实实现 GET `${BASE_URL}/hotspot?context=movie:{id}` 取 polarity_pos/neg
  return MOCK_POLARITY;
}

// 新增评论时间趋势（规格 §5.4 trend，依据 created_at）
export function fetchTrend(): TrendItem[] {
  // TODO: 真实实现 GET `${BASE_URL}/viz/summary?context=...` 取 trend
  return MOCK_TREND;
}
