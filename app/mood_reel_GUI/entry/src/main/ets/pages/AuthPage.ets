// 登录 / 注册页：开屏后未登录自动进入（底部提供游客入口），设置页「去登录」亦可进入
// 蓝白渐变简洁风（配色固定，不随夜间主题变化）；校验口径与后端契约一致：用户名 3~20 字符、密码 6~20 位
import { router } from '@kit.ArkUI';
import { loginAuth, registerAuth } from '../services/api';

// 页面固定配色（蓝白简洁风，独立于全局主题色）
const COLOR_PRIMARY: string = '#1890FF';
const COLOR_MAIN_TEXT: string = '#1A2C3E';
const COLOR_SUB_TEXT: string = '#8A94A6';
const COLOR_INPUT_BG: string = '#F5F7FA';
const COLOR_ERROR: string = '#C62828';

@Entry
@Component
struct AuthPage {
  @State isRegister: boolean = false;
  @State username: string = '';
  @State password: string = '';
  @State confirmPassword: string = '';
  @State submitting: boolean = false;
  @State errorMsg: string = '';
  @State btnScale: number = 1;

  // 返回错误提示文案，空串表示校验通过（口径与后端契约一致）
  private validate(): string {
    const name = this.username.trim();
    if (name.length < 3 || name.length > 20) {
      return '用户名需 3~20 个字符（中文、字母、数字、下划线，不含空格）';
    }
    if (this.password.length < 6 || this.password.length > 20) {
      return '密码需 6~20 位';
    }
    if (this.isRegister && this.confirmPassword !== this.password) {
      return '两次输入的密码不一致';
    }
    return '';
  }

  private saveLoginState(token: string, username: string): void {
    AppStorage.setOrCreate('authToken', token);
    AppStorage.setOrCreate('authUsername', username);
  }

  // 离开本页：从设置页进入（栈里已有主页）则返回；从开屏进入则进主页
  // 注意：router.getLength() 返回 string（API 历史设计），需转数字再比较
  private leavePage(): void {
    if (Number(router.getLength()) > 1) {
      router.back();
    } else {
      router.replaceUrl({ url: 'pages/Index' });
    }
  }

  private async submit(): Promise<void> {
    const err = this.validate();
    if (err !== '') {
      this.errorMsg = err;
      return;
    }
    this.submitting = true;
    this.errorMsg = '';
    const name = this.username.trim();
    try {
      if (this.isRegister) {
        await registerAuth(name, this.password);
      }
      const out = await loginAuth(name, this.password);
      this.saveLoginState(out.token, out.user.username);
      this.leavePage();
    } catch (err) {
      const e = err as Error;
      this.errorMsg = e.message;
    } finally {
      this.submitting = false;
    }
  }

  @Builder
  modeTab(mode: boolean, title: string) {
    Column() {
      Text(title)
        .fontSize(16)
        .fontWeight(this.isRegister === mode ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(this.isRegister === mode ? COLOR_PRIMARY : COLOR_SUB_TEXT);
      Row()
        .width(26)
        .height(3)
        .borderRadius(1.5)
        .backgroundColor(this.isRegister === mode ? COLOR_PRIMARY : Color.Transparent)
        .margin({ top: 4 });
    }
    .layoutWeight(1)
    .justifyContent(FlexAlign.Center)
    .onClick(() => {
      this.isRegister = mode;
      this.errorMsg = '';
    });
  }

  build() {
    Stack() {
      Column() {
        // 顶部品牌区（蓝色渐变段内，白色文字）
        Column() {
          Text('🎬')
            .fontSize(34)
            .fontColor(COLOR_PRIMARY);
        }
        .width(72)
        .height(72)
        .borderRadius(36)
        .backgroundColor('#FFFFFF')
        .justifyContent(FlexAlign.Center)
        .shadow({ radius: 14, color: '#2610427A', offsetX: 0, offsetY: 4 });

        Text('MoodReel')
          .fontSize(26)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .margin({ top: 16 });
        Text('电影评论情感分析')
          .fontSize(13)
          .fontColor('#E4F0FF')
          .margin({ top: 4 });

        // 表单卡片（白色浮层）
        Column() {
          // 登录 / 注册切换
          Row() {
            this.modeTab(false, '登录');
            this.modeTab(true, '注册');
          }
          .width('100%')
          .margin({ bottom: 20 });

          TextInput({ placeholder: '用户名（3~20 字符）', text: this.username })
            .onChange((value: string) => {
              this.username = value;
            })
            .height(44)
            .fontSize(15)
            .fontColor(COLOR_MAIN_TEXT)
            .placeholderColor('#A8B3C1')
            .backgroundColor(COLOR_INPUT_BG)
            .borderRadius(10);

          TextInput({ placeholder: '密码（6~20 位）', text: this.password })
            .type(InputType.Password)
            .onChange((value: string) => {
              this.password = value;
            })
            .height(44)
            .fontSize(15)
            .fontColor(COLOR_MAIN_TEXT)
            .placeholderColor('#A8B3C1')
            .backgroundColor(COLOR_INPUT_BG)
            .borderRadius(10)
            .margin({ top: 12 });

          if (this.isRegister) {
            TextInput({ placeholder: '确认密码', text: this.confirmPassword })
              .type(InputType.Password)
              .onChange((value: string) => {
                this.confirmPassword = value;
              })
              .height(44)
              .fontSize(15)
              .fontColor(COLOR_MAIN_TEXT)
              .placeholderColor('#A8B3C1')
              .backgroundColor(COLOR_INPUT_BG)
              .borderRadius(10)
              .margin({ top: 12 });
          }

          Button(this.submitting ? '请稍候…' : (this.isRegister ? '注 册' : '登 录'))
            .width('100%')
            .height(44)
            .margin({ top: 20 })
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .backgroundColor(COLOR_PRIMARY)
            .fontColor('#FFFFFF')
            .borderRadius(22)
            .enabled(!this.submitting)
            .scale({ x: this.btnScale, y: this.btnScale })
            .onTouch((event: TouchEvent) => {
              if (event.type === TouchType.Down) {
                this.btnScale = 0.97;
              } else if (event.type === TouchType.Up || event.type === TouchType.Cancel) {
                this.btnScale = 1;
              }
            })
            .animation({ duration: 120, curve: Curve.EaseOut })
            .onClick(() => {
              this.submit();
            });

          if (this.errorMsg !== '') {
            Text(this.errorMsg)
              .fontSize(13)
              .fontColor(COLOR_ERROR)
              .width('100%')
              .margin({ top: 12 });
          }
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding({ left: 20, right: 20, top: 18, bottom: 24 })
        .backgroundColor('#FFFFFF')
        .borderRadius(20)
        .shadow({ radius: 24, color: '#1A1890FF', offsetX: 0, offsetY: 6 })
        .margin({ top: 36 });

        // 游客入口（主按钮下方，次级样式保持简洁）
        Text('暂不登录，以游客身份进入 →')
          .fontSize(14)
          .fontColor('#4E88C7')
          .margin({ top: 22 })
          .padding({ top: 8, bottom: 8, left: 16, right: 16 })
          .onClick(() => {
            this.leavePage();
          });
      }
      .width('100%')
      .padding({ left: 24, right: 24 })
      .justifyContent(FlexAlign.Center);
    }
    .width('100%')
    .height('100%')
    .linearGradient({
      direction: GradientDirection.Bottom,
      colors: [['#1890FF', 0.0], ['#6FB0FF', 0.28], ['#FFFFFF', 0.68]]
    });
  }
}
