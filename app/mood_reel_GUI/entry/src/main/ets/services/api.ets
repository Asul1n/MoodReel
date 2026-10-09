// 后端接口封装（真实 HTTP，对齐契约 §2/§7）
import { getText, postText } from './http';
import { Movie, SentimentDist, Review, KeywordItem, PolarityData, TrendDay } from '../model/Models';

// GET /health 响应（设置页「测试连接」用）
export interface HealthOut {
  ok: boolean;
  model_ready: boolean;
  version: string;
}

export async function checkHealth(): Promise<HealthOut> {
  const text = await getText('/health');
  return JSON.parse(text) as HealthOut;
}

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

// ===== 用户认证（契约见 docs/3_接口契约文档.md「用户认证」）=====

// 认证用户（登录返回的 user）
export interface AuthUser {
  user_id: number;
  username: string;
}

// POST /auth/register 响应（201）
interface RegisterOut {
  user_id: number;
  username: string;
  created_at: string;
}

// POST /auth/login 响应
interface LoginOut {
  token: string;
  user: AuthUser;
}

// 注册（用户名 3~20 字符、密码 6~20 位，校验在页面侧做；用户名重复后端报 409）
export async function registerAuth(username: string, password: string): Promise<RegisterOut> {
  const body = JSON.stringify({ username: username, password: password });
  const text = await postText('/auth/register', body);
  return JSON.parse(text) as RegisterOut;
}

// 登录（成功返回 token，http.ets 会在后续请求自动附带 Authorization）
export async function loginAuth(username: string, password: string): Promise<LoginOut> {
  const body = JSON.stringify({ username: username, password: password });
  const text = await postText('/auth/login', body);
  return JSON.parse(text) as LoginOut;
}

// ===== 为你推荐（契约见 docs/3_接口契约文档.md「推荐约定」）=====

// 推荐条目（reason：个性化模式为命中标签如"科幻 ×2 · 冒险 ×1"，hot 模式为"近期热门"或空串）
export interface RecommendItem {
  movie_id: string;
  title: string;
  poster: string;
  rating: number;
  genres: string;
  reason: string;
}

// GET /recommend 响应（mode: personalized / hot）
export interface RecommendOut {
  mode: string;
  items: RecommendItem[];
}

// 获取推荐：登录→个性化标签推荐；游客/冷启动→热点兜底
// token 由 http.ets 自动附带，后端对无效 token 自动降级 hot（不报 401）
export async function fetchRecommend(limit: number): Promise<RecommendOut> {
  const text = await getText(`/recommend?limit=${limit}`);
  return JSON.parse(text) as RecommendOut;
}
