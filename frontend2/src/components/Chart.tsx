import { useEffect, useRef } from 'react'
import { createChart, type IChartApi, type ISeriesApi, CandlestickSeries, LineSeries } from 'lightweight-charts'
import { api } from '../api/client.ts'
// import type { Bar } from '../api/types.ts' // Removed because Bar is no longer explicitly typed here

interface Props {
  symbol: string
}

export default function Chart({ symbol }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const smaRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#fff' }, textColor: '#6b7280' },
      grid: { vertLines: { color: '#f3f4f6' }, horzLines: { color: '#f3f4f6' } },
      timeScale: { borderColor: '#e5e7eb' },
      rightPriceScale: { borderColor: '#e5e7eb' },
    })
    chartRef.current = chart

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    })
    candleRef.current = candle

    const sma = chart.addSeries(LineSeries, {
      color: '#6366f1',
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    smaRef.current = sma

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!candleRef.current || !smaRef.current) return
    api.chart(symbol).then(data => {
      const bars = data.bars ?? []
      candleRef.current!.setData(
        bars.map(b => {
          const parsedTime = (b.bar_time || b.time || '').split('T')[0]
          return { time: parsedTime as never, open: b.open, high: b.high, low: b.low, close: b.close }
        })
      )
      const sma20 = (data.indicators?.['sma20'] ?? data.indicators?.['SMA_20'] ?? []) as number[]
      if (sma20.length > 0) {
        smaRef.current!.setData(
          bars.slice(-sma20.length).map((b, i) => {
            const parsedTime = (b.bar_time || b.time || '').split('T')[0]
            return { time: parsedTime as never, value: sma20[i]! }
          })
        )
      } else {
        smaRef.current!.setData([])
      }
      chartRef.current?.timeScale().fitContent()
    }).catch(() => { })
  }, [symbol])

  return <div ref={containerRef} className="w-full h-full" />
}
