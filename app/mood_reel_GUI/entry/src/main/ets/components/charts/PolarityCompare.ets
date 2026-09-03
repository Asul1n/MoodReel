// 褒贬倾向词对比：夸什么 / 骂什么 两列
import { PolarityData, PolarityItem } from '../../model/Models';

@Component
export struct PolarityCompare {
  @Prop data: PolarityData = { pos: [], neg: [] };

  private fontSize(score: number): number {
    return Math.round(12 + score * 8);
  }

  build() {
    Row() {
      // 夸什么
      Column() {
        Text('👍 夸什么')
          .fontSize(13)
          .fontWeight(FontWeight.Bold)
          .fontColor('#2E7D32');
        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(this.data.pos, (it: PolarityItem) => {
            Text(it.word)
              .fontSize(this.fontSize(it.score))
              .fontColor('#2E7D32')
              .margin({ right: 10, top: 8 });
          }, (it: PolarityItem) => it.word);
        }
        .width('100%')
        .margin({ top: 6 });
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1);

      // 骂什么
      Column() {
        Text('👎 骂什么')
          .fontSize(13)
          .fontWeight(FontWeight.Bold)
          .fontColor('#C62828');
        Flex({ wrap: FlexWrap.Wrap }) {
          ForEach(this.data.neg, (it: PolarityItem) => {
            Text(it.word)
              .fontSize(this.fontSize(it.score))
              .fontColor('#C62828')
              .margin({ right: 10, top: 8 });
          }, (it: PolarityItem) => it.word);
        }
        .width('100%')
        .margin({ top: 6 });
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1);
    }
    .width('100%')
    .alignItems(VerticalAlign.Top);
  }
}
