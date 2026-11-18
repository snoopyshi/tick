import { apiClient } from '@/lib/api-client'
import { instrumentListSchema, type InstrumentList } from './data/schema'

export type FetchInstrumentsParams = {
  q?: string
  assetType?: string[]
  limit: number
  offset: number
}

export async function fetchInstruments(
  params: FetchInstrumentsParams
): Promise<InstrumentList> {
  const response = await apiClient.get('/api/v1/instruments', {
    params: {
      q: params.q || undefined,
      asset_type:
        params.assetType && params.assetType.length > 0
          ? params.assetType.join(',')
          : undefined,
      limit: params.limit,
      offset: params.offset,
    },
  })
  return instrumentListSchema.parse(response.data)
}
