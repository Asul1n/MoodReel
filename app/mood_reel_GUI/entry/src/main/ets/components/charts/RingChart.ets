// 环形图（Canvas 自绘）：正负情感占比，红色部分从 0 增长的进场动画
import { sentimentMeta } from '../../common/Constants';

@Component
export struct RingChart {
  @Prop positive: number = 0;
  @Prop negative: number = 0;
  private progress: number = 0; // 红色增长动画进度 0~1
  private settings: RenderingContextSettings = new RenderingContextSettings(true);
  private ctx: CanvasRenderingContext2D = new CanvasRenderingContext2D(this.settings);

  build() {
    Canvas(this.ctx)
      .width(200)
      .height(200)
      .onReady(() => {
        this.draw();
      })
      .onVisibleAreaChange([0.0, 1.0], (isVisible: boolean, currentRatio: number) => {
        if (isVisible && this.progress === 0) {
          this.animateProgress();
        }
      });
  }

  private total(): number {
    return this.positive + this.negative;
  }

  private animateProgress(): void {
    const duration = 800;
    const start = Date.now();
    const timer: number = setInterval(() => {
      const elapsed = Date.now() - start;
      this.progress = Math.min(1, elapsed / duration);
      this.draw();
      if (this.progress >= 1) {
        clearInterval(timer);
      }
    }, 16);
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
    const start = -Math.PI / 2;
    // 先画满绿色（初始状态全部为绿色）
    this.drawSegment(cx, cy, r, innerR, start, start + Math.PI * 2, sentimentMeta('positive').color);
    // 再画红色（从 0 增长到指定比例）
    const redAngle = (this.negative / total) * Math.PI * 2 * this.progress;
    this.drawSegment(cx, cy, r, innerR, start, start + redAngle, sentimentMeta('negative').color);
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
