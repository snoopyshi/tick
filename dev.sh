#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 本地开发一键启动：后端 FastAPI + 前端 Vite
# 用法（在仓库根目录）：
#   ./dev.sh
# Ctrl+C / 脚本退出时，会把两边进程树一起停掉。
# ---------------------------------------------------------------------------

set -euo pipefail

# 无论从哪里调用，都定位到仓库根目录
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

# 递归结束进程及其子进程（uvicorn --reload、pnpm/vite 都会再拉子进程）
kill_tree() {
  local pid="$1"
  local child
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" 2>/dev/null; then
    return 0
  fi
  while read -r child; do
    [[ -n "${child}" ]] && kill_tree "${child}"
  done < <(pgrep -P "${pid}" || true)
  kill "${pid}" 2>/dev/null || true
  wait "${pid}" 2>/dev/null || true
}

cleanup() {
  # 先清 trap，避免 cleanup 里再触发 EXIT 形成递归
  trap - EXIT INT TERM
  kill_tree "${FRONTEND_PID}"
  kill_tree "${BACKEND_PID}"
}

# 正常退出、Ctrl+C、被 kill 时都走 cleanup
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# 后端：缺 .env 时从示例生成，同步依赖后后台启动（热重载由 .env 的 RELOAD 控制）
# ---------------------------------------------------------------------------
echo "==> 准备后端"
cd "${ROOT}/backend"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "    已从 .env.example 生成 .env"
fi
uv sync
uv run tick &
BACKEND_PID=$!

# ---------------------------------------------------------------------------
# 前端：缺 node_modules 时安装依赖；固定绑 127.0.0.1:5173
# ---------------------------------------------------------------------------
echo "==> 准备前端"
cd "${ROOT}/frontend"
if [[ ! -d node_modules ]]; then
  pnpm install
fi
# macOS 上 Vite 默认可能只听 [::1]，用 127.0.0.1 访问会失败
pnpm exec vite --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

echo
echo "后端: http://127.0.0.1:8000  (docs: /docs, health: /api/v1/health)"
echo "前端: http://127.0.0.1:5173"
echo "按 Ctrl+C 停止"
echo

# ---------------------------------------------------------------------------
# 守着两边进程：任一退出就结束脚本，由 cleanup 关掉另一边
# ---------------------------------------------------------------------------
while kill -0 "${BACKEND_PID}" 2>/dev/null && kill -0 "${FRONTEND_PID}" 2>/dev/null; do
  sleep 1
done

if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
  wait "${BACKEND_PID}" || true
  echo "后端已退出" >&2
  exit 1
fi
wait "${FRONTEND_PID}" || true
echo "前端已退出" >&2
exit 1
