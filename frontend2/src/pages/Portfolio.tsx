import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api/client.ts'
import type { WorkspaceStatus, TradeRecord, JournalDocument, EquityPoint } from '../api/types.ts'

function fmt(n: number | undefined, d = 2) {
  return n != null ? n.toFixed(d) : '—'
}

function pctColor(v?: number) {
  if (v == null || v === 0) return 'text-gray-500'
  return v > 0 ? 'text-green-700' : 'text-red-600'
}

export default function Portfolio() {
  const [account, setAccount] = useState<WorkspaceStatus | null>(null)
  const [trades, setTrades] = useState<TradeRecord[]>([])
  const [equity, setEquity] = useState<EquityPoint[]>([])
  const [journals, setJournals] = useState<JournalDocument[]>([])
  const [lessons, setLessons] = useState('')
  const [editingLessons, setEditingLessons] = useState(false)
  const [lessonsDraft, setLessonsDraft] = useState('')

  useEffect(() => {
    api.account().then(setAccount).catch(() => {})
    api.trades(50).then(setTrades).catch(() => {})
    api.equityHistory(90).then(setEquity).catch(() => {})
    api.journals(10).then(summaries => {
      Promise.all(summaries.slice(0, 5).map(s => api.journal(s.date)))
        .then(setJournals)
        .catch(() => {})
    }).catch(() => {})
    api.lessons().then(d => {
      setLessons(d.content)
      setLessonsDraft(d.content)
    }).catch(() => {})
  }, [])

  const av = account ? Math.round(account.account_value).toLocaleString() : '—'
  const rpnl = account?.realized_pnl
  const chartData = equity.map(p => ({ date: p.date.slice(5), value: p.account_value }))

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      {/* header */}
      <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-sm font-semibold text-gray-900 tracking-wide">Portfolio</h1>
        <div className="text-right">
          <div className="text-xs text-gray-400 mb-0.5">Account Value</div>
          <div className="text-xl font-semibold text-gray-900 tabular">{av}</div>
          {rpnl != null && (
            <div className={`text-xs tabular ${pctColor(rpnl)}`}>
              Realized P&L {rpnl >= 0 ? '+' : ''}{Math.round(rpnl).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-6 flex flex-col gap-6">
        {/* equity curve */}
        <section className="bg-white border border-gray-200 rounded">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Equity Curve</span>
            <span className="text-xs text-gray-400">{equity.length > 0 ? `${equity.length} days` : 'No data yet'}</span>
          </div>
          <div className="h-48 px-2 pt-2 pb-1">
            {equity.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-gray-400">
                Run /heartbeat to start recording snapshots
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" stroke="#d1d5db" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#d1d5db" fontSize={10} tickLine={false} axisLine={false} width={60}
                    tickFormatter={v => Math.round(v / 1000) + 'k'} />
                  <Tooltip
                    contentStyle={{ border: '1px solid #e5e7eb', borderRadius: 4, fontSize: 11 }}
                    formatter={(v) => [typeof v === 'number' ? Math.round(v).toLocaleString() : v, 'NAV']}
                  />
                  <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={1.5}
                    fill="url(#eq)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        {/* positions */}
        {account && account.positions.length > 0 && (
          <section className="bg-white border border-gray-200 rounded">
            <div className="px-4 py-3 border-b border-gray-100">
              <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Positions</span>
            </div>
            <table className="w-full text-xs">
              <thead className="border-b border-gray-100">
                <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                  <th className="px-4 py-2 text-left font-medium">Symbol</th>
                  <th className="px-4 py-2 text-right font-medium">Qty</th>
                  <th className="px-4 py-2 text-right font-medium">Avg</th>
                  <th className="px-4 py-2 text-right font-medium">Price</th>
                  <th className="px-4 py-2 text-right font-medium">P&L</th>
                  <th className="px-4 py-2 text-right font-medium">Alloc%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {account.positions.map(p => (
                  <tr key={p.symbol} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium text-gray-800">{p.symbol.replace('.TW', '')}</td>
                    <td className="px-4 py-2 text-right tabular text-gray-600">{p.quantity}</td>
                    <td className="px-4 py-2 text-right tabular text-gray-600">{fmt(p.avg_price)}</td>
                    <td className="px-4 py-2 text-right tabular text-gray-600">{p.current_price ? fmt(p.current_price) : '—'}</td>
                    <td className={`px-4 py-2 text-right tabular ${pctColor(p.unrealized_pnl)}`}>
                      {p.unrealized_pnl != null ? `${p.unrealized_pnl >= 0 ? '+' : ''}${Math.round(p.unrealized_pnl).toLocaleString()}` : '—'}
                    </td>
                    <td className="px-4 py-2 text-right tabular text-gray-500">
                      {p.allocation_pct != null ? `${fmt(p.allocation_pct, 1)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* trade history */}
        <section className="bg-white border border-gray-200 rounded">
          <div className="px-4 py-3 border-b border-gray-100">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Trade History</span>
          </div>
          <table className="w-full text-xs">
            <thead className="border-b border-gray-100">
              <tr className="text-gray-400 uppercase text-[10px] tracking-wide">
                <th className="px-4 py-2 text-left font-medium">Time</th>
                <th className="px-4 py-2 text-left font-medium">Symbol</th>
                <th className="px-4 py-2 text-left font-medium">Side</th>
                <th className="px-4 py-2 text-right font-medium">Price</th>
                <th className="px-4 py-2 text-right font-medium">Qty</th>
                <th className="px-4 py-2 text-right font-medium">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {trades.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-4 text-gray-400 text-center">No trades yet</td></tr>
              )}
              {trades.map((t, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-gray-400 tabular">{t.executed_at.slice(0, 16)}</td>
                  <td className="px-4 py-2 font-medium text-gray-800">{t.symbol.replace('.TW', '')}</td>
                  <td className={`px-4 py-2 font-medium ${t.action === 'BUY' ? 'text-green-700' : 'text-red-600'}`}>{t.action}</td>
                  <td className="px-4 py-2 text-right tabular text-gray-600">{fmt(t.price)}</td>
                  <td className="px-4 py-2 text-right tabular text-gray-600">{t.quantity}</td>
                  <td className={`px-4 py-2 text-right tabular ${pctColor(t.pnl)}`}>
                    {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString()}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* journals */}
        <section className="bg-white border border-gray-200 rounded">
          <div className="px-4 py-3 border-b border-gray-100">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Journals</span>
          </div>
          <div className="divide-y divide-gray-100">
            {journals.length === 0 && (
              <div className="px-4 py-4 text-xs text-gray-400 text-center">No journal entries</div>
            )}
            {journals.map(j => (
              <div key={j.date} className="px-4 py-3">
                <div className="text-[10px] text-gray-400 font-medium uppercase tracking-wide mb-1">{j.date}</div>
                {j.entries.map((e, i) => (
                  <div key={i} className="text-xs text-gray-600 mb-1">
                    {e.notes?.map((n, ni) => <p key={ni} className="leading-relaxed">{n}</p>)}
                    {e.actions?.map((a, ai) => (
                      <p key={ai} className="text-gray-500 text-[11px]">→ {a}</p>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* lessons */}
        <section className="bg-white border border-gray-200 rounded">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">Lessons</span>
            {!editingLessons ? (
              <button
                onClick={() => { setLessonsDraft(lessons); setEditingLessons(true) }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >Edit</button>
            ) : (
              <div className="flex gap-2">
                <button
                  onClick={() => setEditingLessons(false)}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >Cancel</button>
                <button
                  onClick={() => {
                    api.saveLessons(lessonsDraft)
                      .then(() => { setLessons(lessonsDraft); setEditingLessons(false) })
                      .catch(() => {})
                  }}
                  className="text-xs text-gray-700 font-medium hover:text-gray-900"
                >Save</button>
              </div>
            )}
          </div>
          <div className="px-4 py-3">
            {editingLessons ? (
              <textarea
                value={lessonsDraft}
                onChange={e => setLessonsDraft(e.target.value)}
                rows={8}
                className="w-full text-xs text-gray-700 border border-gray-200 rounded p-2 resize-y focus:outline-none focus:border-gray-400"
              />
            ) : (
              <pre className="text-xs text-gray-600 whitespace-pre-wrap leading-relaxed font-sans">
                {lessons || <span className="text-gray-400">No lessons recorded yet</span>}
              </pre>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
