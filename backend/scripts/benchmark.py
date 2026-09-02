"""吞吐基准：验证">=200 条/秒"（成员B）。

方法（写进报告）：
- 加载与线上一致的模型与 tokenizer
- 取留存测试集/整库中 N=200/400/1000 条英文影评，一次性 batch 前向
- 计时得到 items/s，记录硬件(CPU 型号/内存)、batch 大小、脚本版本、日期
用法：
    python scripts/benchmark.py --n 400 --repeat 5
"""
import argparse
import time
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "IMDB_Dataset.csv"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

TARGET = 200.0  # 条/秒


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DATA_FILE)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()

    # TODO(成员B)：
    #  1) 加载模型（或 import app.services.textcnn 的 analyze_batch 计时）
    #  2) 抽样 N 条 -> 前向 -> 计算 items/s
    #  3) 打印 {n, elapsed_ms, throughput}，吞吐 < TARGET 时给出建议（batch 化/线程池）
    raise NotImplementedError("成员B实现吞吐评测")


if __name__ == "__main__":
    main()
