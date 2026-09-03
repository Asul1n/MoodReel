// 横向条形图：Top 热点词
import { KeywordItem } from '../../model/Models';

@Component
export struct BarChart {
  @Prop items: KeywordItem[] = [];

  private maxWeight(): number {
    let m = 0;
    for (const it of this.items) {
      if (it.weight > m) {
        m = it.weight;
      }
    }
    return m;
  }

  private fillPercent(weight: number): string {
    const max = this.maxWeight();
    const pct = max === 0 ? 0 : (weight / max) * 100;
    return `${pct.toFixed(1)}%`;
  }

  build() {
    Column({ space: 10 }) {
      ForEach(this.items, (it: KeywordItem, idx: number) => {
        Row() {
          Text(`${idx + 1}`)
            .fontSize(11)
            .fontColor($r('app.color.text_secondary'))
            .width(20);
          Text(it.keyword)
            .fontSize(13)
            .fontColor($r('app.color.text_main'))
            .width(56);
          Stack({ alignContent: Alignment.Start }) {
            Row()
              .width('100%')
              .height(14)
              .backgroundColor($r('app.color.track'))
              .borderRadius(7);
            Row()
              .width(this.fillPercent(it.weight))
              .height(14)
              .backgroundColor($r('app.color.primary'))
              .borderRadius(7);
          }
          .layoutWeight(1)
          .margin({ left: 8, right: 8 });
          Text(`${Math.round(it.weight * 100)}`)
            .fontSize(11)
            .fontColor($r('app.color.text_secondary'))
            .width(30)
            .textAlign(TextAlign.End);
        }
        .width('100%')
        .alignItems(VerticalAlign.Center);
      }, (it: KeywordItem) => it.keyword);
    }
    .width('100%');
  }
}
