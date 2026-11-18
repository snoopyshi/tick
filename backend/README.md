# Tick Backend

基于 FastAPI 的 API 服务。前端开发服务器默认跑在 `http://localhost:5173`，跨域来源已在配置里放行。

## 本地运行

```bash
cd backend
cp .env.example .env
uv sync
uv run tick
```

启动后：

- 健康检查：`GET http://127.0.0.1:8000/api/v1/health`
- 接口文档：`http://127.0.0.1:8000/docs`

也可以直接用 uvicorn：

```bash
uv run uvicorn tick.main:app --reload --host 127.0.0.1 --port 8000
```

## Docker

在仓库根目录构建一个镜像。镜像里包含前端静态文件和 API，容器监听 `8000`。

```bash
docker build -f backend/Dockerfile -t tick .
docker run --rm -p 8000:8000 tick
```

打开 `http://127.0.0.1:8000` 是页面，`http://127.0.0.1:8000/api/v1/health` 是健康检查。容器内进程固定监听 `0.0.0.0`，不受 `.env` 里的 `HOST` 影响。

## 检查

```bash
uv run pytest
uv run ruff check src tests
```

## 目录

```text
src/tick/
  main.py                 # 应用工厂与启动入口
  web.py                  # 托管前端构建产物
  core/config.py          # 环境变量配置
  api/v1/endpoints/       # 路由处理
  schemas/                # 请求与响应模型
tests/
```

新增接口时，在 `api/v1/endpoints/` 增加模块，并在 `api/v1/router.py` 挂上。
