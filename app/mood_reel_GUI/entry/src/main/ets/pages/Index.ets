import { TabHome } from '../views/TabHome';
import { TabSettings } from '../views/TabSettings';
import { HistoryItem } from '../model/Models';

@Entry
@Component
struct Index {
  @State currentIndex: number = 0;
  @State splashVisible: boolean = true;
  @State splashOpacity: number = 1;

  aboutToAppear(): void {
    AppStorage.setOrCreate('crawlSource', 'douban');
    AppStorage.setOrCreate('isDarkMode', false);
    const emptyHistory: HistoryItem[] = [];
    PersistentStorage.persistProp('searchHistory', emptyHistory);

    // 开屏动画：1.5s 后淡出，再移除
    setTimeout(() => {
      this.splashOpacity = 0;
      setTimeout(() => {
        this.splashVisible = false;
      }, 400);
    }, 1500);
  }

  @Builder
  tabBarItem(index: number, icon: string, title: string) {
    Column({ space: 2 }) {
      Text(icon)
        .fontSize(20);
      Text(title)
        .fontSize(11)
        .fontColor(this.currentIndex === index ? $r('app.color.primary') : $r('app.color.text_secondary'));
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center);
  }

  build() {
    Stack() {
      Tabs({ barPosition: BarPosition.End }) {
        TabContent() {
          TabHome();
        }
        .tabBar(this.tabBarItem(0, '🏠', '主页'));

        TabContent() {
          TabSettings();
        }
        .tabBar(this.tabBarItem(1, '⚙️', '设置'));
      }
      .onChange((index: number) => {
        this.currentIndex = index;
      })
      .width('100%')
      .height('100%');

      // 开屏遮罩
      if (this.splashVisible) {
        Column() {
          Text('影评分析')
            .fontSize(48)
            .fontWeight(FontWeight.Bold)
            .fontColor('#000000');
        }
        .width('100%')
        .height('100%')
        .justifyContent(FlexAlign.Center)
        .backgroundColor('#2196F3')
        .opacity(this.splashOpacity)
        .animation({ duration: 400, curve: Curve.EaseOut });
      }
    }
    .width('100%')
    .height('100%');
  }
}
