// Steam 风格评论趋势柱状图：每日双柱（绿=好评，红=差评），横轴连续日期，可横向滑动
import { TrendDay } from '../../model/Models';
import { sentimentMeta } from '../../common/Constants';

@Component
export struct TrendChart {
  @Prop days: TrendDay[] = [];
  @State progress: number = 0;

  private totalPositive(): number {
    let s = 0;
    for (const d of this.days) {
      s += d.positive;
    }
    return s;
  }

  private totalNegative(): number {
    let s = 0;
    for (const d of this.days) {
      s += d.negative;
    }
    return s;
  }

  private positiveRate(): string {
    const total = this.totalPositive() + this.totalNegative();
    return total === 0 ? '0.0%' : `${((this.totalPositive() / total) * 100).toFixed(1)}%`;
  }

  private maxCount(): number {
    let m = 0;
    for (const d of this.days) {
      if (d.positive > m) {
        m = d.positive;
      }
      if (d.negative > m) {
        m = d.negative;
      }
    }
    return m;
  }

  private barHeight(count: number): number {
    const max = this.maxCount();
    return max === 0 ? 0 : Math.round((count / max) * 120 * this.progress);
  }

  private shortDate(date: string): string {
    return date.length >= 10 ? date.substring(5) : date;
  }

  build() {
    Column() {
      // 汇总指标
      Row() {
        Column() {
          Text(`${this.totalPositive()}`)
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor(sentimentMeta('positive').color);
          Text('总好评')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 2 });
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Center);

        Column() {
          Text(`${this.totalNegative()}`)
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor(sentimentMeta('negative').color);
          Text('总差评')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 2 });
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Center);

        Column() {
          Text(this.positiveRate())
            .fontSize(18)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.text_main'));
          Text('好评率')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 2 });
        }
        .layoutWeight(1)
        .alignItems(HorizontalAlign.Center);
      }
      .width('100%')
      .margin({ top: 8, bottom: 12 });

      // 图表（横向滚动，每根柱保留占位保持时间轴连续）
      Scroll() {
        Row({ space: 2 }) {
          ForEach(this.days, (d: TrendDay) => {
            Column() {
              Row() {
                Column()
                  .width(9)
                  .height(this.barHeight(d.positive))
                  .backgroundColor(sentimentMeta('positive').color)
                  .borderRadius({ topLeft: 2, topRight: 2 });
                Column()
                  .width(9)
                  .height(this.barHeight(d.negative))
                  .backgroundColor(sentimentMeta('negative').color)
                  .borderRadius({ topLeft: 2, topRight: 2 })
                  .margin({ left: 2 });
              }
              .alignItems(VerticalAlign.Bottom)
              .height(120);
              Text(this.shortDate(d.date))
                .fontSize(9)
                .fontColor($r('app.color.text_secondary'))
                .margin({ top: 4 });
            }
            .width(30)
            .alignItems(HorizontalAlign.Center);
          }, (d: TrendDay) => d.date);
        }
        .padding({ top: 4 });
      }
      .scrollable(ScrollDirection.Horizontal)
      .scrollBar(BarState.Off)
      .width('100%');

      // 图例
      Row() {
        Row() {
          Row()
            .width(8)
            .height(8)
            .borderRadius(4)
            .backgroundColor(sentimentMeta('positive').color);
          Text('好评')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ left: 4 });
        }
        .margin({ right: 16 });
        Row() {
          Row()
            .width(8)
            .height(8)
            .borderRadius(4)
            .backgroundColor(sentimentMeta('negative').color);
          Text('差评')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ left: 4 });
        }
      }
      .width('100%')
      .margin({ top: 8 });
    }
    .width('100%')
    .alignItems(HorizontalAlign.Start)
    .onVisibleAreaChange([0.0, 1.0], (isVisible: boolean, currentRatio: number) => {
      if (isVisible && this.progress === 0) {
        animateTo({ duration: 700, curve: Curve.EaseOut }, () => {
          this.progress = 1;
        });
      }
    });
  }
}
