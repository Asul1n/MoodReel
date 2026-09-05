// 主页：搜索电影名 → 触发抓取 → 展示情感分析结果
import { Movie, Review, KeywordItem, SentimentDist, PolarityData, TrendDay, HistoryItem } from '../model/Models';
import { sentimentMeta, BASE_URL } from '../common/Constants';
import {
  crawlMovie,
  getCrawlStatus,
  CrawlStatus,
  fetchMovie,
  fetchMovies,
  fetchSentimentDist,
  fetchReviews,
  fetchKeywords,
  fetchPolarity,
  fetchTrend,
  backfill
} from '../services/api';
import { RingChart } from '../components/charts/RingChart';
import { BarChart } from '../components/charts/BarChart';
import { TrendChart } from '../components/charts/TrendChart';
import { PolarityCompare } from '../components/charts/PolarityCompare';
import { RevealCard } from '../components/RevealCard';

@Component
export struct TabHome {
  @State keyword: string = '';
  @StorageLink('crawlSource') crawlSource: string = 'douban';
  @StorageLink('searchHistory') searchHistory: HistoryItem[] = [];

  @State searching: boolean = false;
  @State hasResult: boolean = false;
  @State btnScale: number = 1;
  @State errorMsg: string = '';
  @State crawlProgressMsg: string = '';
  @State introExpanded: boolean = false;
  @State reviewCount: number = 5;
  @State expandedReviewId: number = 0;

  @State movie: Movie = { movie_id: '', title: '', year: 0, source: '', source_url: '', intro: '', poster: '', rating: 0, genres: '', review_count: 0 };
  @State dist: SentimentDist = { positive: 0, negative: 0 };
  @State reviews: Review[] = [];
  @State keywords: KeywordItem[] = [];
  @State polarity: PolarityData = { pos: [], neg: [] };
  @State trend: TrendDay[] = [];

  private addHistory(keyword: string, source: string): void {
    const filtered = this.searchHistory.filter((h: HistoryItem) => h.keyword !== keyword);
    const item: HistoryItem = { keyword, source };
    this.searchHistory = [item].concat(filtered).slice(0, 10);
  }

  private async onSearch(): Promise<void> {
    const kw = this.keyword.trim();
    if (kw.length === 0) {
      return;
    }
    this.searching = true;
    this.hasResult = false;
    this.errorMsg = '';
    this.crawlProgressMsg = '正在发起抓取…';
    this.addHistory(kw, this.crawlSource);

    try {
      // 1. 发起抓取（POST /crawl）
      const jobId = await crawlMovie(kw, this.crawlSource);
      // 2. 轮询进度直到 done
      await this.pollUntilDone(jobId);
      // 3. 从影片列表找 movie_id（按片名匹配，找不到取最新一条）
      const movies = await fetchMovies();
      let movieId = '';
      for (const m of movies) {
        if (m.title === kw) {
          movieId = m.movie_id;
          break;
        }
      }
      if (movieId === '' && movies.length > 0) {
        movieId = movies[0].movie_id;
      }
      if (movieId === '') {
        throw new Error('未找到影片');
      }
      const context = `movie:${movieId}`;

      // 4. 先拉影片信息，立即展示（不等情感分析）
      this.movie = await fetchMovie(movieId);
      this.hasResult = true;
      this.searching = false;
      this.crawlProgressMsg = '正在情感分析…';

      // 5. 批量情感分析（慢，期间只显示影片信息 + 进度）
      await backfill(context);

      // 6. 拉取其余结果
      this.dist = await fetchSentimentDist(context);
      this.reviews = await fetchReviews(movieId);
      this.keywords = await fetchKeywords(context);
      this.polarity = await fetchPolarity(context);
      this.trend = await fetchTrend(context);
      this.crawlProgressMsg = '';
    } catch (err) {
      const e = err as Error;
      this.hasResult = false;
      this.errorMsg = `搜索失败（${this.crawlProgressMsg}）：${e.message}`;
    } finally {
      this.searching = false;
    }
  }

  private async pollUntilDone(jobId: string): Promise<CrawlStatus> {
    for (let i = 0; i < 120; i++) {
      const status = await getCrawlStatus(jobId);
      if (status.status === 'done') {
        this.crawlProgressMsg = '抓取完成';
        return status;
      }
      if (status.status === 'failed') {
        throw new Error('抓取失败');
      }
      if (status.status === 'degraded') {
        this.crawlProgressMsg = '已用离线样本兜底';
        return status;
      }
      this.crawlProgressMsg = '正在抓取中';
      await this.sleep(1000);
    }
    throw new Error('抓取超时');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise<void>((resolve: () => void) => {
      setTimeout(() => {
        resolve();
      }, ms);
    });
  }

  private isReviewExpanded(id: number): boolean {
    return this.expandedReviewId === id;
  }

  private toggleReview(id: number): void {
    this.expandedReviewId = this.expandedReviewId === id ? 0 : id;
  }

  private totalDist(): number {
    return this.dist.positive + this.dist.negative;
  }

  private distPercent(count: number): string {
    const total = this.totalDist();
    const pct = total === 0 ? 0 : (count / total) * 100;
    return pct.toFixed(1);
  }

  // 契约 §5：本地海报以 / 开头拼 BASE_URL；豆瓣外链直接用
  private posterUrl(poster: string): string {
    return poster.startsWith('/') ? BASE_URL + poster : poster;
  }

  @Builder
  sectionTitle(title: string) {
    Text(title)
      .fontSize(16)
      .fontWeight(FontWeight.Bold)
      .fontColor($r('app.color.text_main'));
  }

  build() {
    Column() {
      // 顶部搜索区
      Column() {
        Text('电影评论情感分析')
          .fontSize(22)
          .fontWeight(FontWeight.Bold)
          .fontColor($r('app.color.text_main'))
          .margin({ top: 24 });
        TextInput({ placeholder: '输入电影名字', text: this.keyword })
          .onChange((value: string) => {
            this.keyword = value;
          })
          .height(44)
          .margin({ top: 16 })
          .fontSize(16)
          .backgroundColor($r('app.color.card_background'));
        Button('搜索影视相关评价')
          .width('100%')
          .height(44)
          .margin({ top: 12 })
          .fontSize(16)
          .fontWeight(FontWeight.Medium)
          .backgroundColor($r('app.color.primary'))
          .fontColor('#FFFFFF')
          .scale({ x: this.btnScale, y: this.btnScale })
          .onTouch((event: TouchEvent) => {
            if (event.type === TouchType.Down) {
              this.btnScale = 0.96;
            } else if (event.type === TouchType.Up || event.type === TouchType.Cancel) {
              this.btnScale = 1;
            }
          })
          .animation({ duration: 120, curve: Curve.EaseOut })
          .onClick(() => {
            this.onSearch();
          });
      }
      .width('100%')
      .padding({ left: 16, right: 16 });

      if (this.hasResult) {
        Scroll() {
          Column() {
            // 影片信息 + 简介
            RevealCard() {
              Column() {
                Row() {
                  Image(this.posterUrl(this.movie.poster))
                    .width(90)
                    .height(124)
                    .objectFit(ImageFit.Cover)
                    .backgroundColor($r('app.color.track'))
                    .borderRadius(8);
                  Column() {
                    Text(this.movie.title)
                      .fontSize(16)
                      .fontWeight(FontWeight.Bold)
                      .fontColor($r('app.color.text_main'));
                    Text(`${this.movie.year} · ${this.movie.genres}`)
                      .fontSize(14)
                      .fontColor($r('app.color.text_secondary'))
                      .margin({ top: 4 });
                    Text(`评分 ${this.movie.rating}`)
                      .fontSize(14)
                      .fontColor($r('app.color.text_main'))
                      .margin({ top: 6 });
                    Text(`${this.movie.review_count} 条评论`)
                      .fontSize(12)
                      .fontColor($r('app.color.text_secondary'))
                      .margin({ top: 2 });
                  }
                  .alignItems(HorizontalAlign.Start)
                  .margin({ left: 14 })
                  .layoutWeight(1);
                }
                .width('100%');

                Text(this.movie.intro)
                  .fontSize(14)
                  .fontColor($r('app.color.text_main'))
                  .lineHeight(20)
                  .maxLines(this.introExpanded ? 100 : 4)
                  .textOverflow({ overflow: TextOverflow.Ellipsis })
                  .width('100%')
                  .margin({ top: 12 });

                Text(this.introExpanded ? '收起' : '展开')
                  .fontSize(14)
                  .fontColor($r('app.color.accent'))
                  .margin({ top: 8 })
                  .onClick(() => {
                    this.introExpanded = !this.introExpanded;
                  });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 });
            }

            if (this.crawlProgressMsg === '') {
            // 情感分布（环形图）
            RevealCard() {
              Column() {
                this.sectionTitle('情感分布');
                Row() {
                  RingChart({ positive: this.dist.positive, negative: this.dist.negative });
                }
                .width('100%')
                .justifyContent(FlexAlign.Center)
                .margin({ top: 6 });
                Row() {
                  Text(`正向 ${this.dist.positive}（${this.distPercent(this.dist.positive)}%）`)
                    .fontSize(14)
                    .fontColor(sentimentMeta('positive').color);
                  Text(`负向 ${this.dist.negative}（${this.distPercent(this.dist.negative)}%）`)
                    .fontSize(14)
                    .fontColor(sentimentMeta('negative').color)
                    .margin({ left: 16 });
                }
                .width('100%')
                .justifyContent(FlexAlign.Center)
                .margin({ top: 8 });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12 });
            }

            // 评论情感分析
            RevealCard() {
              Column() {
                this.sectionTitle('评论情感分析');
                ForEach(this.reviews.slice(0, Math.min(this.reviewCount, this.reviews.length)), (r: Review) => {
                  Column() {
                    Row() {
                      Text(r.text)
                        .fontSize(16)
                        .fontColor($r('app.color.text_main'))
                        .layoutWeight(1)
                        .maxLines(this.isReviewExpanded(r.id) ? 100 : 2)
                        .textOverflow({ overflow: TextOverflow.Ellipsis });
                      Text(sentimentMeta(r.pred_label).name)
                        .fontSize(12)
                        .fontColor(sentimentMeta(r.pred_label).color)
                        .padding({ left: 8, right: 8, top: 2, bottom: 2 })
                        .backgroundColor(sentimentMeta(r.pred_label).bg)
                        .borderRadius(10)
                        .margin({ left: 10 });
                    }
                    .width('100%')
                    .padding({ top: 12, bottom: 12 });

                    if (r.text.length > 30) {
                      Text(this.isReviewExpanded(r.id) ? '收起' : '展开')
                        .fontSize(13)
                        .fontColor($r('app.color.accent'))
                        .alignSelf(ItemAlign.Start)
                        .margin({ bottom: 8 })
                        .onClick(() => {
                          this.toggleReview(r.id);
                        });
                    }

                    Row()
                      .width('100%')
                      .height(0.5)
                      .backgroundColor($r('app.color.track'));
                  }
                  .width('100%');
                }, (r: Review) => r.id.toString());

                if (this.reviews.length > 5) {
                  Text(this.reviewCount >= this.reviews.length ? '收起' : '更多')
                    .fontSize(14)
                    .fontColor($r('app.color.accent'))
                    .width('100%')
                    .textAlign(TextAlign.Center)
                    .padding({ top: 12 })
                    .onClick(() => {
                      if (this.reviewCount >= this.reviews.length) {
                        this.reviewCount = 5;
                      } else {
                        this.reviewCount += 5;
                      }
                    });
                }
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12 });
            }

            // Top 热点词（条形图）
            RevealCard() {
              Column() {
                this.sectionTitle('Top 热点词');
                BarChart({ items: this.keywords });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12 });
            }

            // 褒贬倾向词
            RevealCard() {
              Column() {
                this.sectionTitle('褒贬倾向词');
                PolarityCompare({ data: this.polarity });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12 });
            }

            // 词云（后端渲染 PNG，前端 Image 加载）
            RevealCard() {
              Column() {
                this.sectionTitle('词云');
                Image(`${BASE_URL}/viz/wordcloud?context=movie:${this.movie.movie_id}&top_n=40`)
                  .width('100%')
                  .aspectRatio(1.6)
                  .objectFit(ImageFit.Contain)
                  .backgroundColor($r('app.color.track'))
                  .borderRadius(8)
                  .margin({ top: 8 });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12 });
            }

            // 评论趋势
            RevealCard() {
              Column() {
                this.sectionTitle('评论趋势');
                TrendChart({ days: this.trend });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
              .margin({ top: 12, bottom: 16 });
            }
            } else {
              RevealCard() {
                Column() {
                  LoadingProgress()
                    .width(36)
                    .height(36)
                    .color($r('app.color.accent'));
                  Text(this.crawlProgressMsg)
                    .fontSize(14)
                    .fontColor($r('app.color.text_secondary'))
                    .margin({ top: 10 });
                }
                .width('100%')
                .alignItems(HorizontalAlign.Center)
                .padding(24)
                .backgroundColor($r('app.color.card_background'))
                .borderRadius(16)
                .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
                .margin({ top: 12, bottom: 16 });
              }
            }
          }
          .width('100%')
          .padding({ left: 16, right: 16 });
        }
        .layoutWeight(1)
        .scrollBar(BarState.Off);
      } else if (this.searching) {
        Column() {
          LoadingProgress()
            .width(40)
            .height(40)
            .color($r('app.color.accent'));
          Text(this.crawlProgressMsg)
            .fontSize(14)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 10 });
        }
        .layoutWeight(1)
        .justifyContent(FlexAlign.Center);
      } else {
        // 空态 + 搜索历史 + 错误提示
        Column() {
          if (this.errorMsg !== '') {
            Text(this.errorMsg)
              .fontSize(14)
              .fontColor('#C62828')
              .margin({ top: 16 });
          }
          if (this.searchHistory.length > 0) {
            Row() {
              Text('搜索历史')
                .fontSize(16)
                .fontWeight(FontWeight.Bold)
                .fontColor($r('app.color.text_main'))
                .layoutWeight(1);
              Text('清空')
                .fontSize(14)
                .fontColor($r('app.color.text_secondary'))
                .onClick(() => {
                  this.searchHistory = [];
                });
            }
            .width('100%')
            .margin({ top: 16 });

            Flex({ wrap: FlexWrap.Wrap }) {
              ForEach(this.searchHistory, (h: HistoryItem) => {
                Text(`${h.keyword} · ${h.source}`)
                  .fontSize(14)
                  .fontColor($r('app.color.text_main'))
                  .padding({ left: 14, right: 14, top: 6, bottom: 6 })
                  .backgroundColor($r('app.color.card_background'))
                  .borderRadius(16)
                  .margin({ right: 8, top: 8 })
                  .stateStyles({
                    pressed: {
                      .scale({ x: 0.95, y: 0.95 })
                    }
                  })
                  .animation({ duration: 120 })
                  .onClick(() => {
                    this.keyword = h.keyword;
                    this.onSearch();
                  });
              }, (h: HistoryItem) => h.keyword + h.source);
            }
            .width('100%');
          } else {
            Text('输入电影名，点击搜索开始分析')
              .fontSize(14)
              .fontColor($r('app.color.text_secondary'))
              .margin({ top: 40 });
          }
        }
        .width('100%')
        .layoutWeight(1)
        .padding({ left: 16, right: 16 });
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.page_background'));
  }
}
