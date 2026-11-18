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

## 数据目录

通过 `DATA_DIR` 配置（默认 `./data`）。启动时会创建必要子目录。

```text
{DATA_DIR}/
  db/tick.db                              # SQLite 约定（本版不建表）
  raw/ths/ohlcv/1d/
    a_share_daily_k_1d_none_10y_20261117.parquet   # 同花顺原始日 K
  market/ohlcv/1d/
    a_share_daily_k_1d.parquet                     # 系统标准日 K（业务只读这里）
```

把同花顺原始文件放到 `raw/ths/...` 后，转换成系统标准数据：

```bash
uv run tick-ingest-ths-daily
```

标准日 K 字段：`symbol, trade_date, open, high, low, close, volume, amount, adjust, vendor, currency`。

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
  core/paths.py           # DATA_DIR 下路径约定
  market/                 # 行情标准定义与厂商适配
  api/v1/endpoints/       # 路由处理
  schemas/                # 请求与响应模型
tests/
```

新增接口时，在 `api/v1/endpoints/` 增加模块，并在 `api/v1/router.py` 挂上。
