// 趋势折线图（Canvas 自绘）：累计新增评论
import { TrendItem } from '../../model/Models';

@Component
export struct LineChart {
  @Prop items: TrendItem[] = [];
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);

  build() {
    Canvas(this.ctx)
      .width('100%')
      .height(180)
      .onReady(() => {
        this.draw();
      });
  }

  private maxCount(): number {
    let m = 0;
    for (const it of this.items) {
      if (it.count > m) {
        m = it.count;
      }
    }
    return m;
  }

  private draw(): void {
    if (this.items.length < 2) {
      return;
    }
    const max = this.maxCount();
    if (max <= 0) {
      return;
    }
    const w = this.ctx.width;
    const h = this.ctx.height;
    const padLeft = 16;
    const padRight = 16;
    const padTop = 16;
    const padBottom = 28;
    const chartW = w - padLeft - padRight;
    const chartH = h - padTop - padBottom;
    const stepX = chartW / (this.items.length - 1);

    // 折线
    this.ctx.beginPath();
    this.ctx.strokeStyle = '#3F51B5';
    this.ctx.lineWidth = 2;
    for (let i = 0; i < this.items.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + chartH - (this.items[i].count / max) * chartH;
      if (i === 0) {
        this.ctx.moveTo(x, y);
      } else {
        this.ctx.lineTo(x, y);
      }
    }
    this.ctx.stroke();

    // 数据点
    for (let i = 0; i < this.items.length; i++) {
      const x = padLeft + i * stepX;
      const y = padTop + chartH - (this.items[i].count / max) * chartH;
      this.ctx.beginPath();
      this.ctx.arc(x, y, 3, 0, Math.PI * 2);
      this.ctx.fillStyle = '#3F51B5';
      this.ctx.fill();
    }

    // X 轴标签
    this.ctx.fillStyle = '#888888';
    this.ctx.font = '11px sans-serif';
    this.ctx.textAlign = 'center';
    for (let i = 0; i < this.items.length; i++) {
      const x = padLeft + i * stepX;
      this.ctx.fillText(this.items[i].label, x, h - 8);
    }
  }
}
