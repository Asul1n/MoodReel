// 设置：用户（登录/注册）/ 后端地址 / 夜间模式 / 采集源选择
import { ConfigurationConstant } from '@kit.AbilityKit';
import { router } from '@kit.ArkUI';
import { SOURCE_OPTIONS, SourceOption, BASE_URL, getBaseUrl } from '../common/Constants';
import { checkHealth, HealthOut } from '../services/api';

@Component
export struct TabSettings {
  @StorageLink('isDarkMode') isDarkMode: boolean = false;
  @StorageLink('crawlSource') crawlSource: string = 'douban';
  @StorageLink('baseUrl') baseUrl: string = BASE_URL;
  @StorageLink('authToken') authToken: string = '';
  @StorageLink('authUsername') authUsername: string = '';
  @State testing: boolean = false;
  @State testMsg: string = '';

  private isLoggedIn(): boolean {
    return this.authToken.length > 0;
  }

  // 未登录 → 去登录/注册页；已登录 → 退出登录（仅清本地登录态）
  private onUserAction(): void {
    if (this.isLoggedIn()) {
      AppStorage.setOrCreate('authToken', '');
      AppStorage.setOrCreate('authUsername', '');
      return;
    }
    router.pushUrl({ url: 'pages/AuthPage' });
  }

  // 去掉结尾多余的 /，避免拼出 http://ip:8000//health
  private normalizeUrl(url: string): string {
    let u: string = url.trim();
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    return u;
  }

  private async onTestConnection(): Promise<void> {
    const url: string = this.normalizeUrl(this.baseUrl);
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      this.testMsg = '地址需以 http:// 或 https:// 开头';
      return;
    }
    this.baseUrl = url;                       // 回写到 AppStorage（持久化）
    AppStorage.setOrCreate('baseUrl', url);
    this.testing = true;
    this.testMsg = '正在连接 ' + url + ' …';
    try {
      const health: HealthOut = await checkHealth();
      this.testMsg = health.ok
        ? `连接成功 · 版本 ${health.version} · 模型${health.model_ready ? '已就绪' : '未就绪'}`
        : '后端返回异常，请检查服务状态';
    } catch (err) {
      const e = err as Error;
      this.testMsg = `连接失败：${e.message}（确认后端已启动、端口放行、同一局域网）`;
    } finally {
      this.testing = false;
    }
  }

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
    Scroll() {
      Column() {
        Text('设置')
          .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .fontColor($r('app.color.text_main'))
        .margin({ top: 24, bottom: 6 });
      Text('账户 / 后端地址 / 主题 / 采集源')
        .fontSize(14)
        .fontColor($r('app.color.text_secondary'))
        .margin({ bottom: 12 });

      // 用户卡片（游客模式：未登录也能使用全部功能，登录仅为身份标识）
      Row() {
        Text(this.isLoggedIn() ? this.authUsername.substring(0, 1) : '🙋')
          .fontSize(18)
          .fontColor('#FFFFFF')
          .width(44)
          .height(44)
          .borderRadius(22)
          .backgroundColor(this.isLoggedIn() ? $r('app.color.accent') : $r('app.color.track'))
          .textAlign(TextAlign.Center);

        Column() {
          Text(this.isLoggedIn() ? this.authUsername : '未登录')
            .fontSize(16)
            .fontWeight(FontWeight.Bold)
            .fontColor($r('app.color.text_main'));
          Text(this.isLoggedIn() ? '已登录 · 可同步分析记录' : '游客模式 · 登录后可同步数据')
            .fontSize(12)
            .fontColor($r('app.color.text_secondary'))
            .margin({ top: 2 });
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        .margin({ left: 12 });

        Button(this.isLoggedIn() ? '退出登录' : '去登录')
          .fontSize(13)
          .backgroundColor(this.isLoggedIn() ? $r('app.color.track') : $r('app.color.accent'))
          .fontColor(this.isLoggedIn() ? $r('app.color.text_main') : '#FFFFFF')
          .onClick(() => {
            this.onUserAction();
          });
      }
      .width('100%')
      .padding(16)
      .backgroundColor($r('app.color.card_background'))
      .borderRadius(16)
      .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
      .margin({ bottom: 16 });

      // 后端服务地址（局域网联调：填后端同学机器的局域网 IP）
      Column() {
        Text('后端服务地址')
          .fontSize(14)
          .fontColor($r('app.color.text_secondary'));

        TextInput({ placeholder: 'http://192.168.x.x:8000', text: this.baseUrl })
          .fontSize(14)
          .fontColor($r('app.color.text_main'))
          .placeholderColor($r('app.color.text_secondary'))
          .backgroundColor($r('app.color.page_background'))
          .borderRadius(10)
          .padding({ left: 12, right: 12, top: 8, bottom: 8 })
          .margin({ top: 10 })
          .onChange((value: string) => {
            this.baseUrl = value;
          });

        Row({ space: 10 }) {
          Button(this.testing ? '测试中…' : '测试连接')
            .fontSize(14)
            .enabled(!this.testing)
            .onClick(() => {
              this.onTestConnection();
            });
          Button('恢复默认')
            .fontSize(14)
            .onClick(() => {
              this.baseUrl = BASE_URL;
              AppStorage.setOrCreate('baseUrl', BASE_URL);
              this.testMsg = '已恢复默认地址';
            });
        }
        .margin({ top: 12 });

        Text(this.testMsg.length > 0 ? this.testMsg : `当前生效：${getBaseUrl()}`)
          .fontSize(12)
          .fontColor($r('app.color.text_secondary'))
          .margin({ top: 10 });

        Text('提示：模拟器访问本机后端用 http://10.0.2.2:8000；访问同局域网后端同学的机器用 http://他的局域网IP:8000')
          .fontSize(12)
          .fontColor($r('app.color.text_secondary'))
          .margin({ top: 6 });
      }
      .width('100%')
      .alignItems(HorizontalAlign.Start)
      .padding(16)
      .backgroundColor($r('app.color.card_background'))
      .borderRadius(16)
      .shadow({ radius: 16, color: '#141A2C3E', offsetX: 0, offsetY: 2 })
      .margin({ bottom: 16 });

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
      .alignItems(HorizontalAlign.Start)
      .padding({ left: 16, right: 16 });
    }
    .width('100%')
    .height('100%')
    .backgroundColor($r('app.color.page_background'))
    .scrollBar(BarState.Off)
    .edgeEffect(EdgeEffect.Spring);
  }
}
