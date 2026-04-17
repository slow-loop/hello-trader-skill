import { useState, useEffect } from 'react'
import { api } from '../api/client.ts'
import type { EvaluatedWatchlistItem, TradeRecord, PositionStatus } from '../api/types.ts'

interface Props {
  selectedSymbol: string
  onSelectSymbol: (symbol: string) => void
}

type Tab = 'watchlist' | 'trades' | 'positions'

function fmt(n: number | undefined, decimals = 2) {
  return n != null ? n.toFixed(decimals) : '—'
}

function pctColor(v?: number) {
  if (v == null || v === 0) return 'text-gray-500'
  return v > 0 ? 'text-green-700' : 'text-red-600'
}

export default function LeftPanel({ selectedSymbol, onSelectSymbol }: Props) {
  const [tab, setTab] = useState<Tab>('watchlist')
  const [watchlist, setWatchlist] = useState<EvaluatedWatchlistItem[]>([])
  const [trades, setTrades] = useState<TradeRecord[]>([])
  const [positions, setPositions] = useState<PositionStatus[]>([])

  useEffect(() => {
    api.watchlist(true)
      .then(d => setWatchlist(d.items))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (tab !== 'trades') return
    api.trades(30).then(setTrades).catch(() => {})
  }, [tab])

  useEffect(() => {
    if (tab !== 'positions') return
    api.account().then(d => setPositions(d.positions)).catch(() => {})
  }, [tab])

  const tabBtn = (t: Tab, label: string) => (
    <button
      onClick={() => setTab(t)}
      className={`flex-1 py-2 text-xs font-medium tracking-wide border-b-2 transition-colors ${
        tab === t ? 'border-gray-900 text-gray-900' : 'border-transparent text-gray-400 hover:text-gray-600'
      }`}
    >
      {label}
    </button>
  )

  return (
    <div className="w-56 h-full flex flex-col border-r border-gray-200 bg-white shrink-0">
      <div className="flex border-b border-gray-200">
        {tabBtn('watchlist', 'Watch')}
        {tabBtn('trades', 'Trades')}
        {tabBtn('positions', 'Pos.')}
      </div>

      <div className="flex-1 overflow-y-auto text-xs">
        {tab === 'watchlist' && (
          <table className="w-full">
            <thead className="sticky top-0 bg-white border-b border-gray-100">
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-3 py-1.5 text-right font-medium">Chg%</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-4 text-gray-400 text-center">Loading…</td></tr>
              )}
              {watchlist.map(item => {
                const bars = item.analysis?.bars ?? []
                const last = bars.at(-1)
                const prev = bars.at(-2)
                const pct = last && prev && prev.close > 0
                  ? ((last.close - prev.close) / prev.close) * 100
                  : undefined
                const isSelected = item.symbol === selectedSymbol
                return (
                  <tr
                    key={item.symbol}
                    onClick={() => onSelectSymbol(item.symbol)}
                    className={`cursor-pointer hover:bg-gray-50 ${isSelected ? 'bg-gray-50' : ''}`}
                  >
                    <td className={`px-3 py-2 font-medium ${isSelected ? 'text-gray-900' : 'text-gray-700'}`}>
                      {item.symbol.replace('.TW', '').replace('.TWO', '')}
                      {item.evaluation?.trigger_met && (
                        <span className="ml-1 text-[9px] text-green-700 font-bold">▲</span>
                      )}
                    </td>
                    <td className={`px-3 py-2 text-right tabular ${pctColor(pct)}`}>
                      {pct != null ? `${pct >= 0 ? '+' : ''}${fmt(pct)}%` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {tab === 'trades' && (
          <table className="w-full">
            <thead className="sticky top-0 bg-white border-b border-gray-100">
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-3 py-1.5 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-4 text-gray-400 text-center">No trades</td></tr>
              )}
              {trades.map((t, i) => (
                <tr key={i} className="hover:bg-gray-50 cursor-pointer" onClick={() => onSelectSymbol(t.symbol)}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-800">{t.symbol.replace('.TW', '')}</div>
                    <div className="text-gray-400 text-[10px]">{t.action} {t.quantity} @ {fmt(t.price)}</div>
                  </td>
                  <td className={`px-3 py-2 text-right tabular ${pctColor(t.pnl)}`}>
                    {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString()}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'positions' && (
          <table className="w-full">
            <thead className="sticky top-0 bg-white border-b border-gray-100">
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
                <th className="px-3 py-1.5 text-right font-medium">P&L%</th>
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-4 text-gray-400 text-center">No positions</td></tr>
              )}
              {positions.map(p => (
                <tr key={p.symbol} className="hover:bg-gray-50 cursor-pointer" onClick={() => onSelectSymbol(p.symbol)}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-800">{p.symbol.replace('.TW', '')}</div>
                    <div className="text-gray-400 text-[10px]">{p.quantity} @ {fmt(p.avg_price)}</div>
                  </td>
                  <td className={`px-3 py-2 text-right tabular ${pctColor(p.unrealized_pnl_pct)}`}>
                    {p.unrealized_pnl_pct != null
                      ? `${p.unrealized_pnl_pct >= 0 ? '+' : ''}${fmt(p.unrealized_pnl_pct, 1)}%`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
