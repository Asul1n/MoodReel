// 后端接口封装（真实 HTTP，对齐契约 §2/§7）
import { getText, postText } from './http';
import { Movie, SentimentDist, Review, KeywordItem, PolarityData, TrendDay } from '../model/Models';

// 响应包装结构
interface CrawlOut { job_id: string; }
interface StatsOut { dist: SentimentDist; }
interface ReviewsOut { items: Review[]; }
interface HotspotOut { keywords: KeywordItem[]; polarity: PolarityData; }
interface VizOut { trend: TrendDay[]; }

// 抓取任务状态（GET /crawl/{job_id}）
export interface CrawlStatus {
  status: string;    // pending/running/done/failed/degraded
  fetched: number;
  limit: number;
  error: string;
  degraded: boolean;
  movie_id: string;  // done 后才有
}

// POST /crawl {source, query, limit} → {job_id}
export async function crawlMovie(query: string, source: string): Promise<string> {
  const body = JSON.stringify({ source: source, query: query, limit: 200 });
  const text = await postText('/crawl', body);
  const out = JSON.parse(text) as CrawlOut;
  return out.job_id;
}

// GET /crawl/{job_id} → 任务进度
export async function getCrawlStatus(jobId: string): Promise<CrawlStatus> {
  const text = await getText(`/crawl/${jobId}`);
  return JSON.parse(text) as CrawlStatus;
}

// GET /crawl/movie/{movie_id} → MovieMeta（含 intro/poster/rating/genres）
export async function fetchMovie(movieId: string): Promise<Movie> {
  const text = await getText(`/crawl/movie/${movieId}`);
  return JSON.parse(text) as Movie;
}

// 影片列表项（用于按片名找 movie_id）
interface MovieListOut { movie_id: string; title: string; }

// GET /crawl/movies → 影片列表（抓取完成后按片名匹配 movie_id）
export async function fetchMovies(): Promise<MovieListOut[]> {
  const text = await getText('/crawl/movies');
  return JSON.parse(text) as MovieListOut[];
}

// GET /dataset/stats?context=... → dist
export async function fetchSentimentDist(context: string): Promise<SentimentDist> {
  const text = await getText(`/dataset/stats?context=${context}`);
  const out = JSON.parse(text) as StatsOut;
  return out.dist;
}

// GET /dataset/reviews?movie_id=... → items
export async function fetchReviews(movieId: string): Promise<Review[]> {
  const text = await getText(`/dataset/reviews?movie_id=${movieId}&limit=50`);
  const out = JSON.parse(text) as ReviewsOut;
  return out.items;
}

// GET /hotspot?context=... → keywords
export async function fetchKeywords(context: string): Promise<KeywordItem[]> {
  const text = await getText(`/hotspot?context=${context}&top_n=20`);
  const out = JSON.parse(text) as HotspotOut;
  return out.keywords;
}

// GET /hotspot?context=... → polarity（夸什么/骂什么）
export async function fetchPolarity(context: string): Promise<PolarityData> {
  const text = await getText(`/hotspot?context=${context}&top_n=20`);
  const out = JSON.parse(text) as HotspotOut;
  return out.polarity;
}

// GET /viz/summary?context=... → trend（每日正/负评数）
export async function fetchTrend(context: string): Promise<TrendDay[]> {
  const text = await getText(`/viz/summary?context=${context}`);
  const out = JSON.parse(text) as VizOut;
  return out.trend;
}

// POST /analyze/backfill 响应
interface BackfillOut { updated: number; }

// POST /analyze/backfill → 给整片评论批量打情感标签（全流程第二步，耗时较长）
export async function backfill(context: string): Promise<BackfillOut> {
  const body = JSON.stringify({ context: context, lang: 'zh', force: false, limit: 300 });
  const text = await postText('/analyze/backfill', body);
  return JSON.parse(text) as BackfillOut;
}
