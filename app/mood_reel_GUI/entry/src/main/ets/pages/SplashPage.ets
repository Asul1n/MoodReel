// 开屏动画页：Logo 放大淡入 → 标题上滑淡入 → 加载指示器 → 跳转主页
import { router } from '@kit.ArkUI';

@Entry
@Component
struct SplashPage {
  @State logoScale: number = 0;
  @State logoOpacity: number = 0;
  @State titleTranslate: number = 40;
  @State titleOpacity: number = 0;
  @State showLoading: boolean = false;

  aboutToAppear(): void {
    // 1. Logo 入场（scale + opacity）
    setTimeout(() => {
      animateTo({ duration: 900, curve: Curve.EaseOut }, () => {
        this.logoScale = 1;
        this.logoOpacity = 1;
      });
    }, 100);

    // 2. 标题入场（Logo 放大到约 80% 时）
    setTimeout(() => {
      animateTo({ duration: 600, curve: Curve.EaseOut }, () => {
        this.titleTranslate = 0;
        this.titleOpacity = 1;
      });
      this.showLoading = true;
    }, 750);

    // 3. 动画播完延迟 300ms 跳转（replaceUrl 防止返回键回到开屏页）
    setTimeout(() => {
      router.replaceUrl({ url: 'pages/Index' });
    }, 2800);
  }

  build() {
    Stack() {
      Column() {
        // Logo：圆形 + 胶片图标
        Column() {
          Text('🎬')
            .fontSize(52)
            .fontColor('#FFFFFF');
        }
        .width(104)
        .height(104)
        .borderRadius(52)
        .backgroundColor('#1890FF')
        .justifyContent(FlexAlign.Center)
        .scale({ x: this.logoScale, y: this.logoScale })
        .opacity(this.logoOpacity);

        // 标题
        Text('MoodReel')
          .fontSize(32)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .margin({ top: 24 })
          .translate({ y: this.titleTranslate })
          .opacity(this.titleOpacity);

        // 加载指示器
        if (this.showLoading) {
          LoadingProgress()
            .width(30)
            .height(30)
            .color('#FFFFFF')
            .margin({ top: 48 });
        }
      }
      .width('100%')
      .height('100%')
      .justifyContent(FlexAlign.Center);
    }
    .width('100%')
    .height('100%')
    .linearGradient({
      direction: GradientDirection.Bottom,
      colors: [['#1A2C3E', 0.0], ['#0D1A2B', 1.0]]
    });
  }
}
