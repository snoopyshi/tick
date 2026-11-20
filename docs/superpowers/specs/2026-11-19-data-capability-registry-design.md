# 数据能力注册中心与复权因子

- 状态：第 4–12 节已实现。日 K 与复权因子在迁移前仍走单文件；迁移后按交易日分区增量同步
- 日期：2026-11-19；修订：2026-11-20
- 范围：backend

## 1. 目标

做成本地研究底座的第一层：系统能回答「现在具备哪些数据能力、每一项是否可用、覆盖到哪里」，并且标准价格保持不复权。复权用单独的因子表表达。页面和以后的回测读同一份 Parquet。

完成时要同时满足：

- 四条能力可被查询：标的、不复权日 K、除权事件、复权因子。
- 日 K 与除权事件已入库的文件，重跑对应命令后状态为 `ready`。
- 由这两份 `ready` 数据算出复权因子并落盘，状态为 `ready`。
- 同一份输入重复计算，因子 Parquet 的字节数不变。

## 2. 非目标

- 注册中心页面。
- 把因子或全市场日 K 的读取方式改成在线查询。注册中心这一轮不改标的接口和日 K 接口，因子不载入进程。日 K 接口返回前复权见 `docs/superpowers/specs/2026-11-20-qfq-ohlcv-api-design.md`。
- 交易日历。周末和节假日没分区，不视为缺口。
- 分钟线入库。存储规则与日 K 相同，见第 12.6 节，本轮不实现。
- 从上市日累计的全历史后复权价。因子从本数据集每只股票的第一根日 K 起算。
- 指数日 K。
- 插件包扫描或入口点自动发现。新能力是代码里的一条显式声明。
- 整文件哈希。清单用行数和字节数发现文件被换过。

## 3. 现状

数据在 `DATA_DIR`（默认 `backend/data`）。

| 数据 | 文件 | 规模 | 说明 |
|---|---|---|---|
| 不复权日 K raw | `raw/ths/ohlcv/1d/a_share_daily_k_1d_none_10y_20261117.parquet` | 10,399,229 行，5580 只 | `adjusted` 全部为 `none`。日期约 2016-11-17 至 2026-11-17 |
| 标准日 K | `market/ohlcv/1d/a_share_daily_k_1d.parquet` | 同上 | 列已是标准日 K。`symbol + trade_date` 无重复。收盘价最小 0.4 |
| 除权事件 raw | `raw/ths/corp_actions/a_share_adjustment_factors_event_none_all_20261117.parquet` | 57,816 行，5438 只 | 字段是派现、送股、配股比例、配股价，没有可相乘的因子列 |
| 标准除权事件 | `market/corp_actions/a_share_corp_actions.parquet` | 同上 | 含 3 组相同 `(symbol, ex_date)`。其中只有 `603883.SH` / `2024-06-27` 落在日 K 窗口内 |
| 标的 | `market/instruments/instruments.parquet` | 7015 只 | A 股 5584，A 股指数 1431。`symbol` 无重复 |

除权事件相对日 K 的位置：严格早于第一根 K 线 22,277 行，恰好落在第一根 K 线当天 1 行，窗口内且晚于第一根 35,498 行，晚于最后一根 39 行，标的不在日 K 中 1 行。恰好落在第一根当天的那一行没有更早的收盘价。第 6.3 节把它和窗口前的行一起计入 `events_before_window`。另有 50 行派现、送股、配股比例都为 0；其中严格落在窗口内的有 42 行，只有这些进入 `events_zero`。两条负送股都在窗口之前。

现有入库命令只写 Parquet，不写清单。因此接上注册中心后，这三份文件在重跑对应命令之前状态是 `invalid`。

## 4. 能力模型

一条能力分成声明和覆盖。

声明写在代码里，描述能力是什么。没有声明的文件不算能力。覆盖写在 Parquet 旁边的清单里，由入库命令生成，描述这份数据实际有什么。

注册中心每次查询时读取清单，并用 Parquet footer 读取列名和行数，再读取文件大小。不读取行情列。

### 4.1 声明

| 字段 | 含义 |
|---|---|
| `id` | 稳定标识。调用方只用它 |
| `title` | 短名称 |
| `grain` | 一行的主键 |
| `columns` | 标准列，顺序与 Parquet 一致 |
| `adjust` | 价格口径。非价格能力为空 |
| `depends_on` | 生产它之前必须 `ready` 的能力 |
| `path` | 相对 `DATA_DIR` 的 POSIX 路径 |
| `producer` | 写出这份数据的命令 |

`depends_on` 只约束生产命令。它不改变被依赖能力自己的状态。

### 4.2 清单

路径规则：把 Parquet 后缀换成 `.manifest.json`。日 K 的清单是 `market/ohlcv/1d/a_share_daily_k_1d.manifest.json`。这是当前单文件实现。日 K 和复权因子的目标布局见第 12 节，清单改为数据集的 `manifest.json`。

公共字段：

| 字段 | 规则 |
|---|---|
| `capability_id` | 等于声明 `id` |
| `schema_version` | 整数 `1` |
| `columns` | 与声明相同，含顺序 |
| `rows` | 写出的表行数 |
| `bytes` | 正式 Parquet 替换完成后的文件字节数 |
| `symbols` | `symbol` 去重个数 |
| `vendor` | `ths` |
| `snapshot_id` | 见各能力 |
| `produced_at` | 写入时刻的 UTC 时间，秒精度，形如 `2026-11-19T05:30:00Z` |

时序能力追加 `min_date`、`max_date`（`YYYY-MM-DD`）。日 K 有 `adjust`。标的有 `asset_types`。因子有五个事件计数。不适用的字段不写入清单；查询响应里用 `null`。清单里多出来的字段忽略。

### 4.3 状态

只使用三种状态。

| 状态 | 条件 |
|---|---|
| `missing` | 标准 Parquet 不存在 |
| `invalid` | 文件在，但清单缺失、损坏，或与文件、声明不一致 |
| `ready` | 没有 issue |

`issues` 使用固定代码：

| 代码 | 条件 |
|---|---|
| `parquet_not_found` | 标准文件不在 |
| `manifest_not_found` | 文件在，清单不在 |
| `manifest_unreadable` | 清单不是合法 JSON，或缺少任一公共字段 |
| `schema_version_unsupported` | `schema_version` 不是 1 |
| `capability_id_mismatch` | 清单中的 id 与声明不同 |
| `columns_mismatch` | 清单列、文件列、声明列有任一不一致，含顺序 |
| `adjust_mismatch` | 声明有 `adjust`，清单缺少 `adjust` 或值不同 |
| `rows_mismatch` | footer 行数与清单 `rows` 不同 |
| `bytes_mismatch` | 文件大小与清单 `bytes` 不同 |

判定顺序：

1. 文件不在：`missing`，`issues` 只有 `parquet_not_found`，`coverage` 为 `null`。不再读清单。
2. 清单不在：`invalid`，`issues` 只有 `manifest_not_found`，`coverage` 为 `null`。
3. 清单读不出：`invalid`，`issues` 只有 `manifest_unreadable`，`coverage` 为 `null`。
4. 其余代码互相独立，能同时出现。只要有一个，状态就是 `invalid`。清单能解析时就填充 `coverage`，即使状态是 `invalid`。
5. 没有任何 issue：`ready`。

字节数相同的内容改写不会被发现。这是本设计接受的限制。

## 5. 首批四条能力

| id | title | grain | adjust | depends_on | path | producer |
|---|---|---|---|---|---|---|
| `market.instruments` | 标的 | `symbol` | — | — | `market/instruments/instruments.parquet` | `tick-ingest-fuyao-tickers` |
| `market.ohlcv.1d` | 不复权日K | `symbol + trade_date` | `none` | — | 当前是单文件 `market/ohlcv/1d/a_share_daily_k_1d.parquet`。第 12 节改为按交易日分区 | `tick-ingest-ths-daily` |
| `market.corp_actions` | 除权事件 | `symbol + ex_date` | — | — | `market/corp_actions/a_share_corp_actions.parquet` | `tick-ingest-ths-corp-actions` |
| `market.adjust_factors` | 复权因子 | `symbol + trade_date` | — | 日 K、除权事件 | 当前是单文件 `market/adjust_factors/a_share_adjust_factors.parquet`。第 12 节改为按交易日分区 | `tick-ingest-adjust-factors` |

列：

- 标的、日 K、除权事件继续使用 `schema.py` 里的现有列。
- 因子列新增为 `symbol, trade_date, factor, vendor`。`factor` 为 float64。

`snapshot_id`：

- 日 K：raw 文件名去掉目录与后缀，`a_share_daily_k_1d_none_10y_20261117`。
- 除权事件：`a_share_adjustment_factors_event_none_all_20261117`。
- 标的：raw 表的 `snapshot_ms` 只有一个非空值时，写这个整数的十进制文本；否则写 `tickers`。
- 因子：`derived:{日 K snapshot_id}+{除权事件 snapshot_id}`。两个 id 取自这两份已经 `ready` 的清单。

标的清单写 `asset_types`，值是每个 `asset_type` 的行数。日 K 的 `min_date` / `max_date` 取 `trade_date`。除权事件取 `ex_date`。因子的日期范围与它所读取的日 K 相同。

除权事件的标准表保持 raw 的行，不去掉 3 组同日重复。去重和合成只在计算因子时发生。

## 6. 复权因子

### 6.1 含义

`factor` 是后复权累计乘数，挂在每一根不复权日 K 上。

- 每只标的第一根 K 线的因子是 `1`。
- 两次除权之间因子不变。
- 后复权价 = `不复权价 × factor`。
- 前复权价 = `不复权价 × factor / 该标的最后一根 K 线的 factor`。最新一根的前复权价等于不复权价。
- 窗口内的新除权只改变除权日及之后的因子。

这个因子锚定在本数据集的第一根日 K，不锚定在上市日。后复权价格水平和从上市日累计的同花顺后复权价可以差一个常数倍。窗口内的复权收益率对齐。

没有窗口内除权的标的，全部因子为 `1`。因子表的 `(symbol, trade_date)` 与日 K 完全一致，行数相同。`vendor` 全部为 `ths`。输出按 `symbol, trade_date` 升序排列。

### 6.2 单次除权

`prev_close` 是 `trade_date < ex_date` 的最后一根不复权收盘价。除权日当天没有 K 线时，新因子从第一根 `trade_date >= ex_date` 的 K 线开始生效。

```text
ex_close = (prev_close - dividend + allotment_price × allotment_ratio)
           / (1 + bonus + allotment_ratio)

ratio = ex_close / prev_close
```

除权日及之后的因子 = `旧因子 / ratio`。

例：前收盘 10，每股派现 1，无送股无配股。`ratio = 0.9`。除权日及之后的因子变为 `1 / 0.9`。

同一天、归类为使用的多行，先合成一次再计算：

1. 各字段完全相同的行只留一条。
2. 派现、送股、配股比例分别相加。
3. 配股价按配股比例加权。配股比例合计为 0 时，配股价按 0。

`603883.SH` 在 `2024-06-27` 的两行不同，必须合成后只除一次。

送股可以为负，表示缩股，公式不变。

### 6.3 事件归类

对每一行原始除权事件按顺序归入一个桶：

1. 标的不在日 K 中 → `events_no_bars`
2. `ex_date` 早于或等于该标的第一根 K 线 → `events_before_window`
3. `ex_date` 晚于该标的最后一根 K 线 → `events_after_window`
4. 派现、送股、配股比例都为 0 → `events_zero`
5. 其余 → `events_applied`

五个计数之和等于除权事件行数。只有第 5 类进入第 6.2 节。第 5 类内部先做同日合成。

### 6.4 计算失败

窗口内事件出现以下任一情况时，计算失败，不写出也不替换因子文件：

- `prev_close <= 0`
- `1 + bonus + allotment_ratio <= 0`
- `ex_close <= 0`
- 除权日之前没有该标的的任何 K 线

最后一条在第 6.3 节已把「早于或等于第一根 K 线」排除。保留这条是为了防止归类和取价不一致。现有数据里有 1 行除权日等于第一根 K 线，按第 6.3 节计入 `events_before_window`，不触发失败。

## 7. 模块

| 模块 | 职责 |
|---|---|
| `backend/src/tick/market/schema.py` | 增加 `ADJUST_FACTOR_COLUMNS` |
| `backend/src/tick/market/catalog.py` | 四条声明、清单路径、状态判定、`list_capabilities()`、`get_capability()` |
| `backend/src/tick/market/manifest.py` | 清单的原子写入；读失败变成该项的 `manifest_unreadable`，不影响其他能力 |
| `backend/src/tick/market/adjust_factors.py` | 纯函数：输入日 K 与除权事件，输出因子表和五个计数。不写文件 |
| `backend/pyproject.toml` | 增加脚本 `tick-ingest-adjust-factors` |
| `backend/src/tick/market/ingest_adjust_factors.py` | 检查依赖、调用计算、原子写入。命令 `tick-ingest-adjust-factors` |
| `backend/src/tick/schemas/capabilities.py` | 响应模型 |
| `backend/src/tick/api/v1/endpoints/capabilities.py` | 两个 GET |
| `backend/src/tick/core/paths.py` | 增加因子 Parquet 路径 |

`catalog.py` 里的声明路径是相对 `DATA_DIR` 的 POSIX 路径。接口返回这个相对路径，不返回绝对路径。

现有三条入库命令在写标准 Parquet 时改为第 8 节的原子顺序，并写清单。日 K 转换后若 `adjust` 有空值或任一值不是 `none`，命令失败，正式文件不动。标的出现重复 `symbol`，或日 K 出现重复 `symbol + trade_date`，命令失败，正式文件不动。除权事件入库不去重。

## 8. 写入顺序

标准 Parquet 和清单都先写临时文件，再替换。

1. 表写到临时 Parquet。此时正式文件仍是上一版。
2. 用这张表准备清单内容。`bytes` 还不能填。
3. 临时 Parquet 替换为正式文件。
4. 读取正式文件字节数，填入清单。
5. 清单写到临时文件并替换为正式清单。
6. 第 5 步失败：删除正式 Parquet 和临时文件，命令以非零退出。此时上一版文件也已经不在，该能力状态为 `missing`。下一次成功入库会同时恢复文件和清单。任何失败路径都删除本次留下的临时文件。

因子命令在第 1 步之前先查注册中心。日 K 或除权事件不是 `ready` 时，退出码为 1，打印这两项的 `status` 和 `issues`，不创建临时文件。

计算失败发生在第 1 步之前，正式因子文件保持不动。

同一输入再次运行因子命令时，Parquet 字节数不变。`produced_at` 只出现在清单中，不写入 Parquet。

## 9. 查询

```http
GET /api/v1/data/capabilities
GET /api/v1/data/capabilities/{id}
```

列表响应：

```json
{
  "total": 4,
  "items": []
}
```

单条响应字段：

| 字段 | 含义 |
|---|---|
| `id` `title` `status` `grain` `columns` `adjust` `depends_on` `producer` `path` | 来自声明。`adjust` 无口径时为 `null` |
| `coverage` | 清单能解析时填充，否则 `null` |
| `issues` | 代码数组。`ready` 时为空数组 |

`coverage` 字段：`rows`、`bytes`、`symbols`、`vendor`、`snapshot_id`、`produced_at`、`min_date`、`max_date`、`asset_types`、`events_applied`、`events_before_window`、`events_after_window`、`events_zero`、`events_no_bars`。清单没有的计数字段为 `null`。

未知 `id` 返回 404，`detail` 为 `unknown capability`。已声明但文件不在返回 200，`status` 为 `missing`。

服务启动不加载因子，也不为注册中心把日 K 读进内存。

## 10. 测试

使用合成小表。测试不读取约一千万行的日 K 文件。

注册中心：

- 文件不在 → `missing`，issue 为 `parquet_not_found`。
- 文件在、清单不在 → `invalid`，issue 为 `manifest_not_found`。
- 清单 JSON 损坏 → 只有该项为 `manifest_unreadable`，列表中的其他能力仍返回。
- 列顺序不同、`adjust` 不同、行数不同、字节数不同，各自产生对应代码。多个问题同时存在时，`issues` 包含全部代码。
- 清单能解析但行数不符时，`coverage` 仍返回清单中的值。
- 未知 id → 404。已知且文件不在 → 200。

因子：

- 前收盘 10、派现 1 → `ratio = 0.9`，除权日及之后因子为 `1 / 0.9`。用最后一根因子去除，得到前复权价。
- 同一天两行不同的事件只改变一次因子。
- 两行完全相同的事件只算一次。
- 窗口前、除权日等于第一根 K 线、窗口后、全零、标的不在日 K 中的事件不改变因子。五个计数之和等于输入行数。
- 因子浮点用容差比较，不要求 `1 / 0.9` 的十进制文本相同。
- 没有除权的标的因子全为 1。输出主键与日 K 相同。
- 分母小于等于 0 时，已有因子文件不被替换。
- 依赖为 `missing` 或 `invalid` 时，命令退出码为 1，不产生因子文件。

日 K 入库：

- 出现 `adjust=qfq`，或重复的 `symbol + trade_date` 时，正式日 K 文件保持不变。

## 11. 实现顺序

1. 声明、清单读写、状态判定和两个查询接口。此时现有三份 Parquet 状态为 `invalid`。
2. 三条现有入库命令写清单，并加上第 7 节的失败条件。重跑后这三项为 `ready`。
3. 因子计算、`tick-ingest-adjust-factors` 和它的清单。依赖 `ready` 后运行，因子状态变为 `ready`。

以上三步已完成，对应单文件整表重写。第 12 节的分区迁移和按交易日增量也已实现：`tick-migrate-trade-date-partitions`、`tick-ingest-ohlcv-batch`。单文件仍在且数据集清单不存在时，日增量命令会拒绝执行。

## 12. 按交易日增量

日 K 和复权因子不再各放一个大文件。盘后同步的单位是一批交易日：只覆盖这批日期的分区，其余分区不读、不写。只同步一天时，批大小为 1。停更数天之后一次性补数，是同一条路径，批里包含这些交易日。

标的和除权事件保持第 4–11 节的单文件整表替换。这两类只有几千到几万行。

### 12.1 分区

```text
market/ohlcv/1d/manifest.json
market/ohlcv/1d/trade_date=YYYY-MM-DD/part.parquet
market/adjust_factors/manifest.json
market/adjust_factors/trade_date=YYYY-MM-DD/part.parquet
```

一个分区是一个交易日、当天有行情的全部标的。分区内列与现在的标准列相同，仍带 `trade_date`，读多个分区时可以直接拼起来。分区内按 `symbol` 升序。`adjust` 仍必须全部是 `none`。主键 `symbol + trade_date` 在分区内不得重复。

数据集清单是目录下的 `manifest.json`，不再用「把单个 Parquet 后缀换成 `.manifest.json`」。`schema_version` 为 `2`。公共字段之外增加：

| 字段 | 含义 |
|---|---|
| `layout` | 固定 `trade_date` |
| `watermark` | 已落盘分区中的最大交易日 |
| `partitions` | 每个已落盘交易日一条：`trade_date`、`rows`、`bytes` |
| `batch_dates` | 最近一次成功批次写过的交易日，升序 |

`rows` 是各分区行数之和，由入库按「减掉被替换分区的旧行数、加上新行数」维护，不扫描历史分区。`symbols` 是水位分区里的标的数，不是十年去重。`min_date` 是分区中的最小交易日，`max_date` 等于 `watermark`。

没有交易日历。清单只记录已经落盘的交易日。周末、节假日或尚未同步的交易日都是「没有这个分区」。查询不把它们报成错误。

### 12.2 一批交易日

输入是这批交易日的增量行，不是十年全量。同一批重跑只替换这批日期，用来修正盘后修订。

1. 在临时文件中写好这批每个交易日的日 K 分区和因子分区。正式分区先不动。
2. 因子按第 12.3 节算完，且日 K 通过 `adjust=none` 和主键唯一检查之后，才用临时文件替换正式分区。
3. 替换全部成功后，再原子替换数据集清单。
4. 任一步失败：删除本次临时文件，已有正式分区和清单保持原样。

查询只读清单。不打开每一个历史分区，也不重算历史分区的字节数。水位分区的 footer 行数与清单不一致时，该能力为 `invalid`，issue 为 `rows_mismatch`。清单不在、损坏，或 `schema_version` 不是 2，规则与第 4.3 节相同。单文件时代的 `parquet_not_found` 对这两种能力改为：清单和分区都不在时是 `missing`。

### 12.3 因子只重算受影响的日期

公式、同日合成、五个事件桶与第 6 节相同。变化的是写入范围。

先取这批里最早的交易日 `batch_start`，再取严格早于 `batch_start` 的最后一个已有因子分区，作为起点。该分区里的因子原样接着用。

然后只走过需要更新的交易日：

- 这批日期都晚于当前水位：从起点把这批日期按升序走完。某天没有除权，当天因子等于前一交易日。某天有除权，从那天的前收盘按第 6.2 节计算，并应用到这批剩余日期。更早的因子分区不写。
- 这批日期插在已有分区中间，或其中有除权：从这批里最早的除权日重算到当前水位，包括该日之后已经存在的因子分区。除权日之前的因子分区不写。这批里没有除权时，只写这批日期，因子等于各自前一交易日的因子，其后分区不写。

前收盘来自 `trade_date < ex_date` 的最后一根 K 线。它可能在本批分区里，也可能只在更早的一个分区里。只读那一个分区的收盘价，不读十年日 K。

新出现的标的，其第一根 K 线因子为 `1`。除权日等于这根 K 线时计入 `events_before_window`，与第 6.3 节相同。

`prev_close <= 0`、分母小于等于 0、`ex_close <= 0`，或除权日前没有任何 K 线时，整批失败，正式分区不替换。

### 12.4 从现有单文件迁出

现有 `a_share_daily_k_1d.parquet` 和 `a_share_adjust_factors.parquet` 各拆成一套交易日分区，并写成 `schema_version=2` 的清单。这是一次性迁移。迁移完成前，注册中心仍按第 4–11 节把它们当作单文件。

迁移后的日常入库不再接收十年全量作为日 K 输入。全量只用于这次拆分，或用于重建某一批被点名的交易日。

### 12.5 测试

用跨越不少于三个交易日、两个标的的小表。不读约一千万行的日 K。

- 只提交最新一天：更早分区的字节数不变，水位变为这一天，无除权时因子等于前一日。
- 同一天再提交一次：只有这一天的分区被替换。
- 一次提交连续三天，其中第二天有派现：这三天被写入，第三天的因子已经带上第二天的比例，更早分区不变。
- 在已有水位之后缺了中间一天再补上，且该日有除权：从该除权日到水位的因子分区被重写，除权日之前不变。
- 批次计算失败：正式分区和清单的字节数与失败前相同。
- 清单的 `watermark` 与分区列表一致；查询不打开水位以外的分区文件。

### 12.6 分钟线

分钟线以后使用同一布局，只把频率放进路径：`market/ohlcv/1m/trade_date=YYYY-MM-DD/part.parquet`。能力标识另立，例如 `market.ohlcv.1m`。本轮不建这个能力，也不做分钟因子。

