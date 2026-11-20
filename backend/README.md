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
  db/tick.db
  raw/ths/ohlcv/1d/
    a_share_daily_k_1d_none_10y_20261117.parquet
  raw/ths/corp_actions/
    a_share_adjustment_factors_event_none_all_20261117.parquet
  raw/ths/tickers/
    tickers.parquet                         # 同花顺标的列表快照（经扶摇 API）
  market/ohlcv/1d/
    a_share_daily_k_1d.parquet              # 迁移前的单文件日 K
    manifest.json                           # 迁移后的数据集清单
    trade_date=YYYY-MM-DD/part.parquet      # 一个交易日、全部标的
  market/corp_actions/
    a_share_corp_actions.parquet            # 系统标准除权事件
  market/instruments/
    instruments.parquet                     # 系统标的主表
    vendor_symbol_map.parquet               # 厂商码 → 系统 symbol
  market/adjust_factors/
    a_share_adjust_factors.parquet          # 迁移前的单文件因子
    manifest.json
    trade_date=YYYY-MM-DD/part.parquet
```

标的和除权事件仍是单文件，旁边有同名清单（`.manifest.json`）。日 K 和复权因子在迁移前也是这种清单；迁移后改用目录里的 `manifest.json`，注册中心优先读它。状态仍是 `ready` / `invalid` / `missing`。

把同花顺原始文件放到 `raw/ths/...` 后转换：

```bash
uv run tick-ingest-ths-daily
uv run tick-ingest-ths-corp-actions
```

经扶摇 HTTP 网关拉取同花顺标的列表并写入系统主数据（需配置 `FUYAO_KEY`；厂商统一为 `ths`；系统 `symbol` = `thscode`，如 `600519.SH`）。默认同时拉取 **A 股**与 **A 股指数**（`a-share,a-share-index`）：

```bash
uv run tick-ingest-fuyao-tickers
# 仅股票或仅指数：
uv run tick-ingest-fuyao-tickers --asset-type a-share
uv run tick-ingest-fuyao-tickers --asset-type a-share-index
# 或仅转换已有 raw：
uv run tick-ingest-fuyao-tickers --no-fetch
```

日 K 和除权事件都是 `ready` 之后，由这两份标准表计算复权因子（不改写不复权价格）。这是整表重算，适合第一次建库：

```bash
uv run tick-ingest-adjust-factors
```

已有单文件日 K 时，先拆成按交易日分区，原文件保留：

```bash
uv run tick-migrate-trade-date-partitions
```

之后盘后只提交本批交易日。停更数天时把这些日期放进同一批。单文件还在、数据集清单还没有时，这条命令会拒绝执行：

```bash
uv run tick-ingest-ohlcv-batch --bars path/to/bars.parquet
```

- 标准日 K：`symbol, trade_date, open, high, low, close, volume, amount, adjust, vendor, currency`
- 标准复权因子：`symbol, trade_date, factor, vendor`（后复权累计乘数；前复权在读取时用最后一根因子去除）
- 标准除权事件：`symbol, ex_date, dividend_per_share, bonus_per_share, allotment_ratio, allotment_price, vendor, currency`
- 标准标的：`symbol, ticker, name, exchange, asset_type, currency, list_date, end_date, last_trade_date, last_delivery_date, updated_at`
- 厂商映射：`vendor, vendor_symbol, symbol, is_primary`

启动时会把 `market/instruments/instruments.parquet`、日 K 和复权因子一并载入进程内存。日 K 接口默认用因子把开高低收换成前复权，成交量保持不复权。日 K 或因子已有数据集清单时，按清单拼接各交易日分区。文件不存在时跳过并打 warning。

标的与行情 API：

```http
GET /api/v1/instruments?q=&asset_type=&limit=50&offset=0
GET /api/v1/ohlcv/1d/{symbol}          # 默认前复权；adjust=none 为不复权；optional ?limit=N
GET /api/v1/data/capabilities
GET /api/v1/data/capabilities/{id}
```

省略 `asset_type` 时返回全部类型；日 K 无数据时返回空 `bars`。前端开发经 Vite 把 `/api` 代理到本服务；标的列表点击代码可弹窗查看日 K。

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
