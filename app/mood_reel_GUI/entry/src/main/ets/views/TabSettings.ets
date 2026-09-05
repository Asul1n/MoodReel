// 设置：夜间模式 / 采集源选择
import { ConfigurationConstant } from '@kit.AbilityKit';
import { SOURCE_OPTIONS, SourceOption } from '../common/Constants';

@Component
export struct TabSettings {
  @StorageLink('isDarkMode') isDarkMode: boolean = false;
  @StorageLink('crawlSource') crawlSource: string = 'douban';

  private applyColorMode(isDark: boolean): void {
    try {
      const hostCtx = this.getUIContext().getHostContext();
      if (hostCtx !== undefined) {
        hostCtx.getApplicationContext().setColorMode(
          isDark ? ConfigurationConstant.ColorMode.COLOR_MODE_DARK : ConfigurationConstant.ColorMode.COLOR_MODE_LIGHT
        );
      }
    } catch (err) {
      // 颜色模式设置失败时忽略
    }
  }

  build() {
    Column() {
      Text('设置')
        .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .fontColor($r('app.color.text_main'))
        .margin({ top: 24, bottom: 6 });
      Text('主题 / 采集源')
        .fontSize(14)
        .fontColor($r('app.color.text_secondary'))
        .margin({ bottom: 12 });

      // 夜间模式
      Row() {
        Column() {
          Text('夜间模式')
            .fontSize(16)
            .fontColor($r('app.color.text_main'));
          Text('开启后应用深色外观')
            .fontSize(14)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 2 });
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1);

        Toggle({ type: ToggleType.Switch, isOn: this.isDarkMode })
          .onChange((isOn: boolean) => {
            this.isDarkMode = isOn;
            this.applyColorMode(isOn);
          });
      }
      .width('100%')
      .padding(16)
      .backgroundColor($r('app.color.card_background'))
      .borderRadius(16)
      .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 });

      // 采集源选择
      Column() {
        Text('采集源')
          .fontSize(14)
          .fontColor($r('app.color.text_secondary'));
        Row({ space: 12 }) {
          ForEach(SOURCE_OPTIONS, (opt: SourceOption) => {
            Text(opt.name)
              .fontSize(16)
              .fontWeight(this.crawlSource === opt.value ? FontWeight.Bold : FontWeight.Normal)
              .fontColor(this.crawlSource === opt.value ? $r('app.color.accent') : $r('app.color.text_secondary'))
              .padding({ left: 22, right: 22, top: 8, bottom: 8 })
              .border({
                width: 1,
                color: this.crawlSource === opt.value ? $r('app.color.accent') : $r('app.color.text_secondary')
              })
              .borderRadius(18)
              .stateStyles({
                pressed: {
                  .scale({ x: 0.95, y: 0.95 })
                }
              })
              .animation({ duration: 120 })
              .onClick(() => {
                this.crawlSource = opt.value;
              });
          }, (opt: SourceOption) => opt.value);
        }
        .margin({ top: 10 });
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
      .padding(16)
      .backgroundColor($r('app.color.card_background'))
      .borderRadius(16)
      .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
      .margin({ top: 16 });
    }
    .width('100%')
    .height('100%')
    .padding({ left: 16, right: 16 })
    .backgroundColor($r('app.color.page_background'));
  }
}
