# 日 K 接口返回前复权

- 状态：已实现
- 日期：2026-11-20
- 范围：backend 日 K 读取接口、因子内存缓存、标的页 K 线文案

## 1. 目标

K 线使用前复权价。不复权日 K 和后复权因子继续是唯一落盘的价格数据。前复权在读取时计算。

完成时要同时满足：

- `GET /api/v1/ohlcv/1d/{symbol}` 默认返回前复权开高低收，成交量仍是不复权。
- `adjust=none` 返回不复权价。
- 除数是该标的在内存中整段日 K 的最后一根因子。`limit` 只截取已经复权的结果。
- 因子未加载，或该标的因子日期与日 K 对不齐时，`adjust=qfq` 返回 503。`adjust=none` 和未知代码不受影响。
- 标的页继续请求该接口，图上方写明前复权。页面不实现复权公式。

## 2. 非目标

- 落盘前复权或后复权价格。
- `adjust=hfq`。后复权仍只存在于因子定义：不复权价 × factor。
- 用价格因子调整成交量或成交额。响应仍不返回 `amount`。
- 价格四舍五入。响应使用乘法得到的浮点数。
- 交易日分区迁移。读取跟随现有日 K 规则：有数据集清单就读分区，否则读单文件。
- 修改注册中心字段和入库命令。

## 3. 计算公式

`factor` 是已经落盘的后复权累计乘数，与该标的每一根日 K 的 `trade_date` 对齐。

前复权价 = 不复权价 × 当日 `factor` / 最后一根日 K 的 `factor`。

最后一根是内存中该标的完整序列的最后一根，不是本次响应窗口的最后一根。因此最新一根的前复权价等于不复权价。只请求最近 N 根时，这 N 根仍使用完整序列的最后一根因子。

`open`、`high`、`low`、`close` 使用同一乘数。`volume` 原样返回。

因子全程为 1 时，前复权价等于不复权价。

## 4. 接口

`GET /api/v1/ohlcv/1d/{symbol}`

| 参数 | 规则 |
| --- | --- |
| `limit` | 保持现状：省略则返回完整序列；可选，范围 1 到 5000 |
| `adjust` | `qfq` 或 `none`，默认 `qfq`。其他值由 FastAPI 返回 422 |

响应：

```json
{
  "symbol": "000001.SZ",
  "adjust": "qfq",
  "bars": [
    {
      "time": "2016-11-17",
      "open": 9.0,
      "high": 9.0,
      "low": 9.0,
      "close": 9.0,
      "volume": 1.0
    }
  ]
}
```

`adjust` 回显本次实际使用的口径。`bars` 内字段和顺序不变。

处理顺序：

1. 校验查询参数。
2. 内存中没有该标的日 K 时返回 200，`bars` 为空，`adjust` 为请求值。此时不检查因子。
3. `adjust=none` 时截取不复权序列并返回 200。
4. `adjust=qfq` 时，因子缓存为空，或该标的缺少因子，或因子日期序列与日 K 日期序列不一致，返回 503，`detail` 为 `adjust factors unavailable`。
5. 对完整序列做前复权，再按 `limit` 取尾部，返回 200。

## 5. 模块

| 模块 | 职责 |
| --- | --- |
| `backend/src/tick/market/adjust_view.py` | 纯函数。输入对齐后的不复权价和因子，输出前复权价。不读文件，不读缓存 |
| `backend/src/tick/market/factor_cache.py` | 按标的保存 `times` 与 `factor`。加载规则与日 K 缓存相同：调用方未指定路径且数据集清单存在时拼接分区，否则读单文件。文件不存在时清空缓存并记录 warning，进程继续启动 |
| `backend/src/tick/market/ohlcv_cache.py` | 仍只保存不复权序列。截取 `limit` 的规则不变 |
| `backend/src/tick/api/v1/endpoints/ohlcv.py` | 按第 4 节编排缓存、纯函数和状态码 |
| `backend/src/tick/schemas/ohlcv.py` | `OhlcvSeriesOut` 增加 `adjust` |
| `backend/src/tick/main.py` | 在加载日 K 缓存之后加载因子缓存 |
| `frontend/src/features/instruments/api/ohlcv.ts` | 响应 schema 接受 `adjust`。请求不传 `adjust`，使用默认前复权 |
| `frontend/src/features/instruments/components/instrument-chart-dialog.tsx` | 说明文案写明前复权。加载失败的展示保持现状，503 走现有失败分支 |

日期对齐在读缓存时判断：两边 `times` 长度相同且逐项相等才算对齐。纯函数不负责查缺。

## 6. 测试

- 因子全为 1：默认响应的价格等于不复权价，`adjust` 为 `qfq`，成交量不变。
- 前收盘 10、派现 1、除权日后因子为 `1 / 0.9`：除权日前的前复权收盘价为 9，最后一根前复权价等于不复权价。
- 同一序列加 `limit=1`：只返回最后一根，价格等于不复权最新价。`limit` 大于 1 时，响应里较早的 K 线仍除以完整序列的最后一根因子。接口没有起始日期参数。
- `adjust=none`：存在会改变价格的因子时，仍返回不复权价。
- 现有日 K 接口测试改为带上因子，并断言响应中的 `adjust`。只写入日 K、不写因子时，默认请求得到 503。
- 无因子文件：`adjust=qfq` 为 503，`adjust=none` 为 200。
- 因子日期与日 K 错开：`adjust=qfq` 为 503。
- 未知代码：200，`bars` 为空，`adjust` 为请求值。

## 7. 与数据底座规格的关系

存储、因子定义和分区规则仍以 `docs/superpowers/specs/2026-11-19-data-capability-registry-design.md` 为准。该规格里「日 K 接口保持原样、因子不载入进程」只覆盖注册中心那一轮。本规格改为在读取接口中载入因子并返回前复权视图。
