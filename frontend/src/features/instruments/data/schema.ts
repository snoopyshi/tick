import { z } from 'zod'

export const instrumentSchema = z.object({
  symbol: z.string(),
  ticker: z.string(),
  name: z.string(),
  exchange: z.string().nullable(),
  asset_type: z.string(),
  currency: z.string(),
  list_date: z.string().nullable(),
  end_date: z.string().nullable(),
  last_trade_date: z.string().nullable(),
  last_delivery_date: z.string().nullable(),
  updated_at: z.string().nullable(),
})

export type Instrument = z.infer<typeof instrumentSchema>

export const instrumentListSchema = z.object({
  total: z.number().int().nonnegative(),
  items: z.array(instrumentSchema),
})

export type InstrumentList = z.infer<typeof instrumentListSchema>
