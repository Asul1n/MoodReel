// 登场动画容器：滚入视口时淡入 + 上滑
@Component
export struct RevealCard {
  @BuilderParam content: () => void;
  @State appeared: boolean = false;

  build() {
    Column() {
      this.content();
    }
    .width('100%')
    .opacity(this.appeared ? 1 : 0)
    .translate({ y: this.appeared ? 0 : 32 })
    .onVisibleAreaChange([0.0, 1.0], (isVisible: boolean, currentRatio: number) => {
      if (isVisible && !this.appeared) {
        animateTo({ duration: 350, curve: Curve.EaseOut }, () => {
          this.appeared = true;
        });
      }
    });
  }
}
