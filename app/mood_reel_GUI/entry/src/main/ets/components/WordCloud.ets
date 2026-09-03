// 加权词云：按权重缩放字号的标签排版
import { KeywordItem } from '../model/Models';

@Component
export struct WordCloud {
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

  private fontSize(weight: number): number {
    const max = this.maxWeight();
    const ratio = max === 0 ? 0 : weight / max;
    return Math.round(11 + ratio * 15);
  }

  build() {
    Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.Center, alignItems: ItemAlign.Center }) {
      ForEach(this.items, (it: KeywordItem) => {
        Text(it.keyword)
          .fontSize(this.fontSize(it.weight))
          .fontColor($r('app.color.primary'))
          .margin({ left: 6, right: 6, top: 4, bottom: 4 });
      }, (it: KeywordItem) => it.keyword);
    }
    .width('100%');
  }
}
