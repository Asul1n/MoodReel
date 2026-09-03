// 常量

// 后端服务地址（联调时改为宿主机局域网 IP 或模拟器 10.0.2.2）
export const BASE_URL: string = 'http://127.0.0.1:8000';

// 采集源选项（设置页选择，主页搜索时读取）
export interface SourceOption {
  value: string;
  name: string;
}

export const SOURCE_OPTIONS: SourceOption[] = [
  { value: 'douban', name: '豆瓣' },
  { value: 'imdb', name: 'IMDB' },
];

// 情感标签元信息（二分类：positive / negative）
export interface SentimentMeta {
  name: string;
  color: string;
  bg: string;
}

export interface SentimentMetaMap {
  positive: SentimentMeta;
  negative: SentimentMeta;
  unknown: SentimentMeta;
}

export const SENTIMENT_META: SentimentMetaMap = {
  positive: { name: '正向', color: '#2E7D32', bg: '#E8F5E9' },
  negative: { name: '负向', color: '#C62828', bg: '#FFEBEE' },
  unknown: { name: '未标注', color: '#9E9E9E', bg: '#F5F5F5' },
};

export function sentimentMeta(label: string): SentimentMeta {
  if (label === 'positive') {
    return SENTIMENT_META.positive;
  }
  if (label === 'negative') {
    return SENTIMENT_META.negative;
  }
  return SENTIMENT_META.unknown;
}
