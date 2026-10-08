// 登录 / 注册页：设置页「去登录」进入，成功后写登录态并返回（游客可随时跳过，不影响主流程）
// 表单校验与后端契约一致：用户名 3~20 字符、密码 6~20 位；注册成功自动登录
import { router } from '@kit.ArkUI';
import { loginAuth, registerAuth } from '../services/api';

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
      router.back();
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
        .fontWeight(!this.isRegister === mode ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(!this.isRegister === mode ? $r('app.color.accent') : $r('app.color.text_secondary'));
      Row()
        .width(28)
        .height(3)
        .borderRadius(1.5)
        .backgroundColor(!this.isRegister === mode ? $r('app.color.accent') : Color.Transparent)
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
        // Logo + 标题（呼应开屏页）
        Column() {
          Text('🎬')
            .fontSize(34)
            .fontColor('#FFFFFF');
        }
        .width(72)
        .height(72)
        .borderRadius(36)
        .backgroundColor('#1890FF')
        .justifyContent(FlexAlign.Center);

        Text('MoodReel')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
          .fontColor('#FFFFFF')
          .margin({ top: 14 });
        Text(this.isRegister ? '注册账号，记录你的观影观点' : '登录后同步你的分析记录')
          .fontSize(13)
          .fontColor('#B8C4D0')
          .margin({ top: 6 });

        // 表单卡片
        Column() {
          // 登录 / 注册切换
          Row() {
            this.modeTab(false, '登录');
            this.modeTab(true, '注册');
          }
          .width('100%')
          .margin({ bottom: 16 });

          TextInput({ placeholder: '用户名（3~20 字符）', text: this.username })
            .onChange((value: string) => {
              this.username = value;
            })
            .height(44)
            .fontSize(15)
            .backgroundColor($r('app.color.page_background'))
            .borderRadius(10);

          TextInput({ placeholder: '密码（6~20 位）', text: this.password })
            .type(InputType.Password)
            .onChange((value: string) => {
              this.password = value;
            })
            .height(44)
            .fontSize(15)
            .backgroundColor($r('app.color.page_background'))
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
              .backgroundColor($r('app.color.page_background'))
              .borderRadius(10)
              .margin({ top: 12 });
          }

          Button(this.submitting ? '请稍候…' : (this.isRegister ? '注 册' : '登 录'))
            .width('100%')
            .height(44)
            .margin({ top: 18 })
            .fontSize(16)
            .fontWeight(FontWeight.Medium)
            .backgroundColor($r('app.color.accent'))
            .fontColor('#FFFFFF')
            .enabled(!this.submitting)
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
              this.submit();
            });

          if (this.errorMsg !== '') {
            Text(this.errorMsg)
              .fontSize(13)
              .fontColor('#C62828')
              .width('100%')
              .margin({ top: 12 });
          }
        }
        .width('100%')
        .alignItems(HorizontalAlign.Start)
        .padding(20)
        .backgroundColor($r('app.color.card_background'))
        .borderRadius(16)
        .shadow({ radius: 16, color: '#14000A1E', offsetX: 0, offsetY: 2 })
        .margin({ top: 28 });
      }
      .width('100%')
      .padding({ left: 24, right: 24 })
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
