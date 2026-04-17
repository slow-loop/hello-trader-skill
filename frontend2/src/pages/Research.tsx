import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import type { ScreenerResult } from '../api/types.ts'

const STRATEGIES = ['momentum']

function fmt(n: number | undefined, d = 2) {
  return n != null ? n.toFixed(d) : '—'
}

function pctColor(v?: number) {
  if (v == null || v === 0) return 'text-gray-500'
  return v > 0 ? 'text-green-700' : 'text-red-600'
}

export default function Research() {
  const [strategy, setStrategy] = useState('momentum')
  const [results, setResults] = useState<ScreenerResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState('')

  const run = (s: string) => {
    setStrategy(s)
    setLoading(true)
    setError('')
    api.screener(s, 30)
      .then(r => { setResults(r.items); setProfile(r.market_profile) })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { run('momentum') }, [])

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-gray-900">Screener</h1>
          {profile && <span className="text-xs text-gray-400 uppercase">{profile}</span>}
        </div>
        <div className="flex gap-1">
          {STRATEGIES.map(s => (
            <button
              key={s}
              onClick={() => run(s)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                strategy === s
                  ? 'bg-gray-900 text-white'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-gray-400'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* table */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center h-32 text-xs text-gray-400">Loading…</div>
        )}
        {error && (
          <div className="px-6 py-4 text-xs text-red-600">{error}</div>
        )}
        {!loading && !error && (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white border-b border-gray-200">
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="px-4 py-2.5 text-left font-medium">Symbol</th>
                <th className="px-4 py-2.5 text-left font-medium">Name</th>
                <th className="px-4 py-2.5 text-right font-medium">Close</th>
                <th className="px-4 py-2.5 text-right font-medium">Chg%</th>
                <th className="px-4 py-2.5 text-right font-medium">Value (M)</th>
                <th className="px-4 py-2.5 text-left font-medium w-64">Signal</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {results.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-gray-400 text-center">No results</td></tr>
              )}
              {results.map(item => (
                <tr key={item.symbol} className="hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-medium text-gray-800">
                    {item.symbol.replace('.TW', '').replace('.TWO', '')}
                  </td>
                  <td className="px-4 py-2.5 text-gray-500 max-w-[160px] truncate">{item.name}</td>
                  <td className="px-4 py-2.5 text-right tabular text-gray-700">{fmt(item.close)}</td>
                  <td className={`px-4 py-2.5 text-right tabular ${pctColor(item.change_pct)}`}>
                    {item.change_pct != null ? `${item.change_pct >= 0 ? '+' : ''}${fmt(item.change_pct)}%` : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular text-gray-500">
                    {item.trade_value ? (item.trade_value / 1e6).toFixed(0) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 text-[10px] leading-relaxed">
                    {item.analysis?.summary ?? ''}
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
