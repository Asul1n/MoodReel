import { TabHome } from '../views/TabHome';
import { TabSettings } from '../views/TabSettings';
import { HistoryItem } from '../model/Models';

@Entry
@Component
struct Index {
  @State currentIndex: number = 0;

  aboutToAppear(): void {
    AppStorage.setOrCreate('crawlSource', 'douban');
    AppStorage.setOrCreate('isDarkMode', false);
    const emptyHistory: HistoryItem[] = [];
    PersistentStorage.persistProp('searchHistory', emptyHistory);
  }

  @Builder
  tabBarItem(index: number, icon: string, title: string) {
    Column({ space: 2 }) {
      Text(icon)
        .fontSize(20);
      Text(title)
        .fontSize(11)
        .fontColor(this.currentIndex === index ? $r('app.color.accent') : $r('app.color.text_secondary'));
    }
    .width('100%')
    .height('100%')
    .justifyContent(FlexAlign.Center);
  }

  build() {
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
  }
}
