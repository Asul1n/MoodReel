// 环形图（Canvas 自绘）：正负情感占比
import { sentimentMeta } from '../../common/Constants';

@Component
export struct RingChart {
  @Prop positive: number = 0;
  @Prop negative: number = 0;
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);

  build() {
    Canvas(this.ctx)
      .width(200)
      .height(200)
      .onReady(() => {
        this.draw();
      });
  }

  private total(): number {
    return this.positive + this.negative;
  }

  private draw(): void {
    const total = this.total();
    if (total <= 0) {
      return;
    }
    const cx = 100;
    const cy = 100;
    const r = 88;
    const innerR = 56;
    const negAngle = (this.negative / total) * Math.PI * 2;
    const start = -Math.PI / 2;
    // 负向（红色）
    this.drawSegment(cx, cy, r, innerR, start, start + negAngle, sentimentMeta('negative').color);
    // 正向（绿色）
    this.drawSegment(cx, cy, r, innerR, start + negAngle, start + Math.PI * 2, sentimentMeta('positive').color);
  }

  private drawSegment(cx: number, cy: number, r: number, innerR: number, startAngle: number, endAngle: number, color: string): void {
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, r, startAngle, endAngle);
    this.ctx.arc(cx, cy, innerR, endAngle, startAngle, true);
    this.ctx.closePath();
    this.ctx.fillStyle = color;
    this.ctx.fill();
  }
}
