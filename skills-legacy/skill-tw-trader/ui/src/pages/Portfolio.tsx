import { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface Trade {
  date: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  pnl?: number;
  reason?: string;
}

interface JournalEntry {
  date: string;
  content: any;
}

interface EquityPoint {
  date: string;
  account_value: number;
}

export default function Portfolio() {
  const [portfolio, setPortfolio] = useState<any>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [journals, setJournals] = useState<JournalEntry[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);

  useEffect(() => {
    fetch('/api/portfolio')
      .then(res => res.json())
      .then(data => setPortfolio(data))
      .catch(() => {});

    fetch('/api/trades')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setTrades(data.slice(-20).reverse());
      })
      .catch(() => {});

    fetch('/api/portfolio/equity-history?days=90')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setEquityCurve(data);
      })
      .catch(() => {});

    fetch('/api/agent/journals')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setJournals(data);
      })
      .catch(() => {});
  }, []);

  const summary = portfolio?.summary;
  const accountValue = summary?.account_value ? Math.round(summary.account_value).toLocaleString() : '—';
  const todayPnlPct = summary?.today_realized_pnl_pct;
  const chartData = equityCurve.length > 0
    ? equityCurve.map(point => ({
        time: point.date.slice(5),
        equity: point.account_value,
      }))
    : summary?.account_value
      ? [{ time: 'Today', equity: summary.account_value }]
      : [];

  return (
    <div className="flex flex-col h-full bg-[#0a0a0a] border-l border-[#1f2937] w-full">
      <div className="px-6 py-4 border-b border-[#1f2937] bg-[#111111] flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-neutral-300 tracking-wider">PORTFOLIO & HISTORY</h2>
          <p className="text-xs text-neutral-500">Account overview and historical execution details</p>
        </div>
        <div className="text-right">
          <p className="text-xs font-mono text-neutral-500 uppercase tracking-wider">Total Equity</p>
          <p className="text-2xl font-bold font-mono text-white tracking-tight leading-none mt-1">NT$ {accountValue}</p>
          {todayPnlPct != null && (
            <p className={`font-mono font-bold text-xs mt-1 ${todayPnlPct >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {todayPnlPct >= 0 ? '+' : ''}{todayPnlPct.toFixed(2)}% Today
            </p>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-8 w-full">
        {/* Equity Curve */}
        <section className="h-[350px] w-full bg-black border border-[#1f2937] flex flex-col shrink-0">
          <div className="px-4 py-2 bg-[#161616] border-b border-[#1f2937] flex items-center justify-between">
            <span className="text-xs font-bold text-neutral-400 uppercase tracking-widest">Daily Equity Curve</span>
            <span className="text-[10px] font-bold text-neutral-500">
              {equityCurve.length > 0 ? `${equityCurve.length} snapshots` : 'No snapshots yet'}
            </span>
          </div>
          <div className="flex-1 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorEq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#525252" fontSize={11} tickLine={false} axisLine={false} dy={10} fontFamily="monospace" />
                <YAxis stroke="#525252" fontSize={11} tickLine={false} axisLine={false} domain={['dataMin - 5000', 'dataMax + 5000']} hide />
                <Tooltip
                  contentStyle={{ backgroundColor: '#111111', borderColor: '#1f2937', borderRadius: '0px', fontFamily: 'monospace' }}
                  itemStyle={{ color: '#10b981' }}
                  cursor={{ stroke: '#1f2937', strokeWidth: 1, strokeDasharray: '3 3' }}
                />
                <Area type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorEq)" activeDot={{ r: 4, fill: '#10b981', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Trade History Section */}
        <section className="flex flex-col bg-black border border-[#1f2937] overflow-hidden shrink-0 min-h-[300px]">
          <div className="px-4 py-2 bg-[#161616] border-b border-[#1f2937] text-xs font-bold text-neutral-400 uppercase tracking-widest">
            Trade History
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
              <thead className="bg-[#1a1a1a] text-neutral-500 uppercase border-b border-[#1f2937]">
                <tr>
                  <th className="px-4 py-2 font-normal">Date / Time</th>
                  <th className="px-4 py-2 font-normal">Symbol</th>
                  <th className="px-4 py-2 font-normal">Side</th>
                  <th className="px-4 py-2 font-normal text-right">Price</th>
                  <th className="px-4 py-2 font-normal text-right">Qty</th>
                  <th className="px-4 py-2 font-normal text-right">P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1f2937]">
                {trades.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-4 text-neutral-500 text-center">No trades yet</td></tr>
                )}
                {trades.map((t, idx) => (
                  <tr key={idx} className="hover:bg-[#1a1a1a]">
                    <td className="px-4 py-2 text-neutral-500">{t.date?.slice(0, 16)}</td>
                    <td className="px-4 py-2 font-bold text-neutral-300">{t.symbol}</td>
                    <td className={`px-4 py-2 font-bold ${t.action === 'BUY' ? 'text-emerald-500' : 'text-red-500'}`}>{t.action}</td>
                    <td className="px-4 py-2 text-right">{t.price?.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right">{t.quantity}</td>
                    <td className={`px-4 py-2 text-right ${(t.pnl ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}${Math.round(t.pnl).toLocaleString()}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* AI Journals Section */}
        <section className="flex flex-col bg-black border border-[#1f2937] overflow-hidden shrink-0 pb-10">
          <div className="px-4 py-2 bg-[#161616] border-b border-[#1f2937] text-xs font-bold text-neutral-400 uppercase tracking-widest shrink-0">
            AI Daily Journals
          </div>
          <div className="flex flex-col">
            {journals.length === 0 && (
              <div className="p-6 text-neutral-500 text-xs text-center">No journal entries yet</div>
            )}
            {journals.map(j => (
              <div
                key={j.date}
                className="p-6 border-b border-[#1f2937] hover:bg-[#1a1a1a]/30 transition-colors"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-bold text-emerald-400 tracking-wide">Journal</h3>
                  <span className="text-[10px] text-neutral-500 font-mono">{j.date}</span>
                </div>
                <pre className="text-xs text-neutral-400 leading-relaxed font-sans whitespace-pre-wrap max-w-4xl">
                  {typeof j.content === 'string' ? j.content : JSON.stringify(j.content, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
