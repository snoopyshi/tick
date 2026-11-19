import { useEffect, useRef } from 'react'
import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { useTheme } from '@/context/theme-provider'
import { type OhlcvBar } from '../api/ohlcv'

type DailyCandlestickChartProps = {
  bars: OhlcvBar[]
  /** Initial visible window (most recent N bars). Full series stays loaded for pan/zoom. */
  initialVisibleBars?: number
  className?: string
}

const UP_COLOR = '#ef4444'
const DOWN_COLOR = '#22c55e'
const DEFAULT_VISIBLE_BARS = 60

export function DailyCandlestickChart({
  bars,
  initialVisibleBars = DEFAULT_VISIBLE_BARS,
  className,
}: DailyCandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const { resolvedTheme } = useTheme()

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const isDark = resolvedTheme === 'dark'
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isDark ? '#a1a1aa' : '#71717a',
      },
      grid: {
        vertLines: { color: isDark ? '#27272a' : '#e4e4e7' },
        horzLines: { color: isDark ? '#27272a' : '#e4e4e7' },
      },
      rightPriceScale: {
        borderColor: isDark ? '#3f3f46' : '#d4d4d8',
      },
      timeScale: {
        borderColor: isDark ? '#3f3f46' : '#d4d4d8',
      },
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    })

    const volumeSeries = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: 'volume' },
        priceScaleId: '',
      },
      1
    )
    chart.panes()[1]?.setStretchFactor(0.28)
    chart.panes()[0]?.setStretchFactor(0.72)

    chartRef.current = chart
    candleRef.current = candleSeries
    volumeRef.current = volumeSeries

    return () => {
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      volumeRef.current = null
    }
  }, [resolvedTheme])

  useEffect(() => {
    const candleSeries = candleRef.current
    const volumeSeries = volumeRef.current
    const chart = chartRef.current
    if (!candleSeries || !volumeSeries || !chart) return

    candleSeries.setData(
      bars.map((bar) => ({
        time: bar.time as Time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }))
    )
    volumeSeries.setData(
      bars.map((bar) => ({
        time: bar.time as Time,
        value: bar.volume,
        color: bar.close >= bar.open ? `${UP_COLOR}99` : `${DOWN_COLOR}99`,
      }))
    )
    const total = bars.length
    if (total === 0) return

    const visible = Math.min(initialVisibleBars, total)
    chart.timeScale().setVisibleLogicalRange({
      from: total - visible,
      to: total - 1,
    })
  }, [bars, initialVisibleBars])

  return <div ref={containerRef} className={className} />
}
