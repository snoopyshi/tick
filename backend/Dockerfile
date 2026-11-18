# 单镜像：前端静态文件 + FastAPI API，由 uvicorn 统一对外。
# 必须在仓库根目录构建（需要同时拿到 frontend/ 和 backend/）：
#   docker build -f backend/Dockerfile -t tick .
#   docker run --rm -p 8000:8000 tick

# ---------------------------------------------------------------------------
# 阶段 1：构建前端（Vite）
# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend

WORKDIR /src

# corepack 启用 pnpm；跳过 Playwright 浏览器下载（镜像只做 production build）
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

# 先只拷依赖清单，利用 Docker 层缓存；package.json 不变时不必重装依赖
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 再拷源码并产出 dist/
COPY frontend/ ./
RUN pnpm build

# ---------------------------------------------------------------------------
# 阶段 2：安装后端依赖（uv）
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS backend

WORKDIR /app

# 编译字节码加速启动；依赖拷贝进镜像；不装开发依赖
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

# 先按 lockfile 装第三方依赖，不安装本项目，便于缓存
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 再装本项目到 .venv（非 editable）；源码装完后可删，运行时走 site-packages
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable && rm -rf src

# ---------------------------------------------------------------------------
# 阶段 3：运行镜像（只保留 Python 运行时、.venv、前端产物）
# ---------------------------------------------------------------------------
FROM python:3.13-slim-bookworm

WORKDIR /app

# 非 root 运行
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

# 从构建阶段拷入虚拟环境和前端静态文件
COPY --from=backend --chown=app:app /app/.venv /app/.venv
COPY --from=frontend --chown=app:app /src/dist /app/static

# PATH 指向 venv；挂前端静态目录；stdout 不缓冲便于看日志
ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    ENVIRONMENT=production \
    DEBUG=false \
    RELOAD=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# 容器内必须听 0.0.0.0，否则宿主机映射端口访问不到
CMD ["uvicorn", "tick.main:app", "--host", "0.0.0.0", "--port", "8000"]
