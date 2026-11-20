import { useQuery } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { fetchOhlcv1d } from '../api/ohlcv'
import { type Instrument } from '../data/schema'
import { DailyCandlestickChart } from './daily-candlestick-chart'

type InstrumentChartDialogProps = {
  instrument: Instrument | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const DEFAULT_VISIBLE_BARS = 60

export function InstrumentChartDialog({
  instrument,
  open,
  onOpenChange,
}: InstrumentChartDialogProps) {
  const symbol = instrument?.symbol ?? ''
  const query = useQuery({
    queryKey: ['ohlcv', '1d', symbol],
    queryFn: () => fetchOhlcv1d(symbol),
    enabled: open && symbol.length > 0,
  })

  const bars = query.data?.bars ?? []
  const title = instrument
    ? `${instrument.name}（${instrument.symbol}）`
    : '日 K'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='flex max-h-[90vh] w-[min(96vw,56rem)] max-w-none flex-col gap-4 sm:max-w-none'>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            已加载全部前复权日 K；默认展示最近 {DEFAULT_VISIBLE_BARS}{' '}
            根（可左右拖动查看更多）。
          </DialogDescription>
        </DialogHeader>

        <div className='min-h-[28rem] w-full flex-1'>
          {query.isLoading ? (
            <div className='flex h-[28rem] items-center justify-center text-sm text-muted-foreground'>
              加载中…
            </div>
          ) : query.isError ? (
            <div className='flex h-[28rem] items-center justify-center text-sm text-muted-foreground'>
              加载失败，请稍后重试。
            </div>
          ) : bars.length === 0 ? (
            <div className='flex h-[28rem] items-center justify-center text-sm text-muted-foreground'>
              暂无行情数据。
            </div>
          ) : (
            <DailyCandlestickChart
              bars={bars}
              initialVisibleBars={DEFAULT_VISIBLE_BARS}
              className='h-[28rem] w-full'
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
