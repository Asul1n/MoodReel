#!/usr/bin/env bash
# =============================================================================
#  MoodReel 后端启动脚本（Linux / WSL / macOS）
#
#  用法：  ./start.sh            默认 0.0.0.0:8000，不热重载
#          ./start.sh 8001       指定端口
#          ./start.sh dev        端口 8000 + --reload 热重载
#          ./start.sh dev 8001   指定端口 + 热重载
#
#  首次运行会自动建 .venv 并装依赖；已存在则直接启动。
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$VENV/bin/python"
PORT=8000
RELOAD=""

# ---- 解析参数 ---------------------------------------------------------------
if [ "${1:-}" = "dev" ]; then
  RELOAD="--reload"
  PORT="${2:-8000}"
elif [ -n "${1:-}" ]; then
  PORT="$1"
fi

# ---- .env -------------------------------------------------------------------
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "[setup] 未找到 .env，正在从 .env.example 复制"
    cp .env.example .env
  else
    echo "[warn]  没有 .env，也没有 .env.example 可复制"
  fi
fi

# ---- 虚拟环境 ---------------------------------------------------------------
if [ ! -x "$PY" ]; then
  echo "[setup] 创建虚拟环境 $VENV"
  python3 -m venv "$VENV"
  echo "[setup] 安装依赖（首次运行，需数分钟）"
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r requirements.txt -r requirements-dev.txt
  echo "[setup] 完成"
fi

# ---- torch 可选依赖 ---------------------------------------------------------
if ! "$PY" -c "import torch" >/dev/null 2>&1; then
  echo "[warn]  未安装 torch：/analyze/en 不可用，其余接口（中文/采集/推荐/认证）正常"
  echo "        启用：$PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu"
fi

# ---- 打印访问地址 -----------------------------------------------------------
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
echo
echo "============================================================"
echo " MoodReel 后端启动，端口 $PORT"
echo "   本机 : http://127.0.0.1:$PORT"
echo "   文档 : http://127.0.0.1:$PORT/docs"
echo "   探活 : http://127.0.0.1:$PORT/health"
[ -n "$LAN_IP" ] && echo "   局域网: http://$LAN_IP:$PORT  （App 设置页填这个）"
echo "============================================================"
echo

# ---- 启动 -------------------------------------------------------------------
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" $RELOAD
