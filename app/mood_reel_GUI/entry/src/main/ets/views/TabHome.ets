// 主页：搜索电影名 → 触发抓取 → 展示情感分析结果
import { Movie, Review, KeywordItem, SentimentDist, PolarityData, TrendDay, HistoryItem } from '../model/Models';
import { sentimentMeta } from '../common/Constants';
import {
  crawlMovie,
  fetchSentimentDist,
  fetchReviews,
  fetchKeywords,
  fetchPolarity,
  fetchTrend
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

  @State movie: Movie = { movieId: '', title: '', year: 0, source: '' };
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

  private onSearch(): void {
    const kw = this.keyword.trim();
    if (kw.length === 0) {
      return;
    }
    this.searching = true;
    this.hasResult = false;
    this.addHistory(kw, this.crawlSource);

    // 发起抓取（POST /crawl）
    crawlMovie(kw, this.crawlSource);

    // 模拟后端返回
    setTimeout(() => {
      const m: Movie = {
        movieId: `mock-${this.crawlSource}-1`,
        title: kw,
        year: 2024,
        source: this.crawlSource,
      };
      this.movie = m;
      this.dist = fetchSentimentDist();
      this.reviews = fetchReviews();
      this.keywords = fetchKeywords();
      this.polarity = fetchPolarity();
      this.trend = fetchTrend();
      this.searching = false;
      this.hasResult = true;
    }, 600);
  }

  private totalDist(): number {
    return this.dist.positive + this.dist.negative;
  }

  private distPercent(count: number): string {
    const total = this.totalDist();
    const pct = total === 0 ? 0 : (count / total) * 100;
    return pct.toFixed(1);
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
            // 影片信息
            RevealCard() {
              Column() {
                Text(this.movie.title)
                  .fontSize(16)
                  .fontWeight(FontWeight.Bold)
                  .fontColor($r('app.color.text_main'));
                Text(`${this.movie.source} · ${this.movie.year}`)
                  .fontSize(14)
                  .fontColor($r('app.color.text_secondary'))
                  .margin({ top: 4 });
              }
              .width('100%')
              .alignItems(HorizontalAlign.Start)
              .padding(16)
              .backgroundColor($r('app.color.card_background'))
              .borderRadius(16)
              .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 });
            }

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
                ForEach(this.reviews, (r: Review) => {
                  Row() {
                    Text(r.text)
                      .fontSize(16)
                      .fontColor($r('app.color.text_main'))
                      .layoutWeight(1)
                      .maxLines(2)
                      .textOverflow({ overflow: TextOverflow.Ellipsis });
                    Text(sentimentMeta(r.label).name)
                      .fontSize(12)
                      .fontColor(sentimentMeta(r.label).color)
                      .padding({ left: 8, right: 8, top: 2, bottom: 2 })
                      .backgroundColor(sentimentMeta(r.label).bg)
                      .borderRadius(10)
                      .margin({ left: 10 });
                  }
                  .width('100%')
                  .margin({ top: 10 });
                }, (r: Review) => r.id.toString());
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

            // 新增评论趋势
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
          Text('正在抓取并分析…')
            .fontSize(14)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 10 });
        }
        .layoutWeight(1)
        .justifyContent(FlexAlign.Center);
      } else {
        // 空态 + 搜索历史
        Column() {
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
