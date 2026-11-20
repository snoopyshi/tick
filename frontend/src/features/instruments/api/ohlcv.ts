import { z } from 'zod'
import { apiClient } from '@/lib/api-client'

const ohlcvBarSchema = z.object({
  time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
})

const ohlcvSeriesSchema = z.object({
  symbol: z.string(),
  adjust: z.enum(['qfq', 'none']),
  bars: z.array(ohlcvBarSchema),
})

export type OhlcvBar = z.infer<typeof ohlcvBarSchema>
export type OhlcvSeries = z.infer<typeof ohlcvSeriesSchema>

/** Fetch daily OHLCV. Omit ``limit`` to receive the full series. */
export async function fetchOhlcv1d(
  symbol: string,
  limit?: number
): Promise<OhlcvSeries> {
  const response = await apiClient.get(
    `/api/v1/ohlcv/1d/${encodeURIComponent(symbol)}`,
    { params: limit == null ? undefined : { limit } }
  )
  return ohlcvSeriesSchema.parse(response.data)
}
