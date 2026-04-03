import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries, CrosshairMode } from 'lightweight-charts';

interface Trade {
  date: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  pnl?: number;
  reason?: string;
}

interface ChartWidgetProps {
  symbol: string;
  days?: number;
  trades?: Trade[];
  visibleIndicators?: string[];
}

function computeSMA(data: { time: any; close: number }[], period: number) {
  const result: { time: any; value: number }[] = [];
  if (data.length < period) return result;
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += data[j].close;
    }
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

function computeEMA(data: { time: any; close: number }[], period: number) {
  const result: { time: any; value: number }[] = [];
  if (data.length < 1) return result;
  const k = 2 / (period + 1);
  let ema = data[0].close;
  result.push({ time: data[0].time, value: ema });
  for (let i = 1; i < data.length; i++) {
    ema = (data[i].close - ema) * k + ema;
    result.push({ time: data[i].time, value: ema });
  }
  return result;
}

export default function ChartWidget({
  symbol,
  days = 150,
  trades = [],
  visibleIndicators = ['sma20', 'sma60']
}: ChartWidgetProps) {
  const mainChartRef = useRef<HTMLDivElement>(null);
  const volChartRef = useRef<HTMLDivElement>(null);
  const sma20SeriesRef = useRef<any>(null);
  const sma60SeriesRef = useRef<any>(null);
  const ema20SeriesRef = useRef<any>(null);
  const visibleIndicatorsRef = useRef(visibleIndicators);
  const [legend, setLegend] = useState({ open: 0, high: 0, low: 0, close: 0, sma20: null as number | null, sma60: null as number | null, ema20: null as number | null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mainChartRef.current || !volChartRef.current) return;

    let cancelled = false;
    const mainEl = mainChartRef.current;
    const volEl = volChartRef.current;

    const commonOptions = {
      layout: {
        background: { type: ColorType.Solid, color: '#000000' },
        textColor: '#D1D5DB',
      },
      grid: {
        vertLines: { color: '#1F2937' },
        horzLines: { color: '#1F2937' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#6B7280', labelBackgroundColor: '#1F2937' },
        horzLine: { color: '#6B7280', labelBackgroundColor: '#1F2937' },
      },
      timeScale: {
        timeVisible: false,
        secondsVisible: false,
        borderColor: '#374151',
      },
      autoSize: true,
    };

    const mainChart: any = createChart(mainEl, {
      ...commonOptions,
      rightPriceScale: { borderColor: '#374151' },
    } as any);

    const volChart: any = createChart(volEl, {
      ...commonOptions,
      rightPriceScale: { borderColor: '#374151', scaleMargins: { top: 0.1, bottom: 0 } },
    } as any);

    const candlestickSeries: any = mainChart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    const vi = visibleIndicatorsRef.current;
    const sma20Series: any = mainChart.addSeries(LineSeries, {
      color: '#a78bfa',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      title: 'SMA 20',
      visible: vi.includes('sma20'),
    });
    sma20SeriesRef.current = sma20Series;

    const sma60Series: any = mainChart.addSeries(LineSeries, {
      color: '#fbbf24',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      title: 'SMA 60',
      visible: vi.includes('sma60'),
    });
    sma60SeriesRef.current = sma60Series;

    const ema20Series: any = mainChart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 1.5,
      crosshairMarkerVisible: false,
      title: 'EMA 20',
      visible: vi.includes('ema20'),
    });
    ema20SeriesRef.current = ema20Series;

    const volumeSeries = volChart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });

    // Fetch data
    setLoading(true);
    setError(null);

    fetch(`/api/market/history/${encodeURIComponent(symbol)}?days=${days}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(rawData => {
        if (cancelled) return;
        setLoading(false);

        if (!rawData || rawData.length === 0) {
          setError('No data available');
          return;
        }

        // Find the date column name
        const dateKey = rawData[0].Date ? 'Date' : 'date';
        const openKey = rawData[0].Open ? 'Open' : 'open';
        const highKey = rawData[0].High ? 'High' : 'high';
        const lowKey = rawData[0].Low ? 'Low' : 'low';
        const closeKey = rawData[0].Close ? 'Close' : 'close';
        const volumeKey = rawData[0].Volume ? 'Volume' : 'volume';

        const chartData = rawData.map((d: any) => ({
          time: d[dateKey],
          open: d[openKey],
          high: d[highKey],
          low: d[lowKey],
          close: d[closeKey],
          volume: d[volumeKey],
        }));

        // Set candlestick data
        candlestickSeries.setData(chartData.map((d: any) => ({
          time: d.time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        })));

        // Set volume data
        volumeSeries.setData(chartData.map((d: any) => ({
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? 'rgba(38, 166, 154, 0.8)' : 'rgba(239, 83, 80, 0.8)',
        })));

        // Compute and set SMA/EMA
        const sma20Data = computeSMA(chartData, 20);
        const sma60Data = computeSMA(chartData, 60);
        const ema20Data = computeEMA(chartData, 20);
        sma20Series.setData(sma20Data);
        sma60Series.setData(sma60Data);
        ema20Series.setData(ema20Data);

        // Set Markers for Trades
        if (trades && trades.length > 0) {
          const symbolTrades = trades.filter(t => t.symbol === symbol);
          const markers = symbolTrades.map(t => {
            const tradeDate = t.date.split('T')[0];
            const isBuy = t.action === 'BUY';
            return {
              time: tradeDate,
              position: isBuy ? 'belowBar' : 'aboveBar' as any,
              color: isBuy ? '#10b981' : '#ef4444',
              shape: isBuy ? 'arrowUp' : 'arrowDown' as any,
              text: `${t.action} @ ${t.price}`,
              size: 1,
            };
          }).filter(m => chartData.some((d: any) => d.time === m.time));

          candlestickSeries.setMarkers(markers);
        }

        // Set legend to last candle + last indicator values
        const last = chartData[chartData.length - 1];
        if (last) {
          const lastSma20 = sma20Data.length > 0 ? sma20Data[sma20Data.length - 1].value : null;
          const lastSma60 = sma60Data.length > 0 ? sma60Data[sma60Data.length - 1].value : null;
          const lastEma20 = ema20Data.length > 0 ? ema20Data[ema20Data.length - 1].value : null;
          setLegend({ open: last.open, high: last.high, low: last.low, close: last.close, sma20: lastSma20, sma60: lastSma60, ema20: lastEma20 });
        }
      })
      .catch(err => {
        if (cancelled) return;
        setLoading(false);
        setError(err.message);
      });

    // Sync charts
    try {
      mainChart.timeScale().subscribeVisibleLogicalRangeChange((range: any) => {
        if (range) volChart.timeScale().setVisibleLogicalRange(range);
      });
      volChart.timeScale().subscribeVisibleLogicalRangeChange((range: any) => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
      });

      mainChart.subscribeCrosshairMove((param: any) => {
        if (param.point && param.seriesPrices && param.seriesPrices.size > 0) {
          const firstPrice = param.seriesPrices.values().next().value;
          volChart.setCrosshairPosition(firstPrice, param.time, volumeSeries);
        } else {
          volChart.clearCrosshairPosition();
        }
        if (param.time && param.seriesPrices && param.seriesPrices.size > 0) {
          const data = param.seriesPrices.get(candlestickSeries) as any;
          if (data && data.open !== undefined) {
            const sma20Val = sma20SeriesRef.current ? param.seriesPrices.get(sma20SeriesRef.current) as number | undefined : undefined;
            const sma60Val = sma60SeriesRef.current ? param.seriesPrices.get(sma60SeriesRef.current) as number | undefined : undefined;
            const ema20Val = ema20SeriesRef.current ? param.seriesPrices.get(ema20SeriesRef.current) as number | undefined : undefined;
            setLegend({
              open: data.open, high: data.high, low: data.low, close: data.close,
              sma20: sma20Val ?? null,
              sma60: sma60Val ?? null,
              ema20: ema20Val ?? null,
            });
          }
        }
      });

      volChart.subscribeCrosshairMove((param: any) => {
        if (param.point && param.seriesPrices && param.seriesPrices.size > 0) {
          const firstPrice = param.seriesPrices.values().next().value;
          mainChart.setCrosshairPosition(firstPrice, param.time, candlestickSeries);
        } else {
          mainChart.clearCrosshairPosition();
        }
      });
    } catch (e) { /* fallback gracefully */ }

    return () => {
      cancelled = true;
      mainChart.remove();
      volChart.remove();
    };
  }, [symbol, days, trades]);

  // Update indicator visibility without rebuilding the chart
  useEffect(() => {
    visibleIndicatorsRef.current = visibleIndicators;
    if (sma20SeriesRef.current) sma20SeriesRef.current.applyOptions({ visible: visibleIndicators.includes('sma20') });
    if (sma60SeriesRef.current) sma60SeriesRef.current.applyOptions({ visible: visibleIndicators.includes('sma60') });
    if (ema20SeriesRef.current) ema20SeriesRef.current.applyOptions({ visible: visibleIndicators.includes('ema20') });
  }, [visibleIndicators]);

  return (
    <div className="h-full w-full flex flex-col bg-black">
      {/* 70% height for Candles */}
      <div className="flex-[3] w-full min-h-0 relative border-b border-[#1f2937]">
        <div className="absolute top-2 left-4 z-10 pointers-events-none flex items-center gap-4">
          <div className="text-[10px] font-mono font-bold text-neutral-300 flex gap-3 bg-[#000000]/60 px-2 py-1 rounded">
            <span>O <span className="text-emerald-500">{legend.open.toFixed(2)}</span></span>
            <span>H <span className="text-emerald-500">{legend.high.toFixed(2)}</span></span>
            <span>L <span className="text-emerald-500">{legend.low.toFixed(2)}</span></span>
            <span>C <span className="text-emerald-500">{legend.close.toFixed(2)}</span></span>
          </div>
          <div className="text-[10px] font-mono font-bold flex gap-3 bg-[#000000]/60 px-2 py-1 rounded select-none">
            {visibleIndicators.includes('sma20') && <span className="text-[#a78bfa]">SMA 20{legend.sma20 != null ? `: ${legend.sma20.toFixed(2)}` : ''}</span>}
            {visibleIndicators.includes('sma60') && <span className="text-[#fbbf24]">SMA 60{legend.sma60 != null ? `: ${legend.sma60.toFixed(2)}` : ''}</span>}
            {visibleIndicators.includes('ema20') && <span className="text-[#3b82f6]">EMA 20{legend.ema20 != null ? `: ${legend.ema20.toFixed(2)}` : ''}</span>}
          </div>
        </div>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <span className="text-neutral-500 text-xs font-mono">Loading {symbol}...</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <span className="text-red-500 text-xs font-mono">Error: {error}</span>
          </div>
        )}
        <div ref={mainChartRef} className="absolute inset-0 w-full h-full" />
      </div>

      {/* 30% height for Volume */}
      <div className="flex-[1] w-full min-h-0 relative">
        <div className="absolute top-2 left-4 z-10 pointers-events-none">
          <div className="text-[10px] font-mono font-bold text-neutral-400 bg-[#000000]/60 px-2 py-1 rounded">Volume</div>
        </div>
        <div ref={volChartRef} className="absolute inset-0 w-full h-full" />
      </div>
    </div>
  );
}
