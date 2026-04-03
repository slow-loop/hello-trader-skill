import { useEffect, useState } from 'react';
import { Brain, AlertOctagon } from 'lucide-react';

interface PortfolioSummary {
  account_value?: number;
  exposure_pct?: number;
  cash_pct?: number;
  today_realized_pnl?: number;
  today_realized_pnl_pct?: number;
  unrealized_pnl?: number;
}

export default function AgentWidget() {
  const [summary, setSummary] = useState<PortfolioSummary>({});
  const [positions, setPositions] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<string[]>([]);

  useEffect(() => {
    fetch('/api/portfolio')
      .then(res => res.json())
      .then(data => {
        if (data?.summary) setSummary(data.summary);
        if (data?.positions) setPositions(data.positions);
        if (data?.alerts) setAlerts(data.alerts);
      })
      .catch(() => {});
  }, []);

  const mainPosition = positions.length > 0 ? positions[0] : null;

  return (
    <div className="flex flex-col h-full bg-[#111111] border-l border-neutral-800 w-[280px] flex-shrink-0">
      <div className="px-3 py-2 border-b border-neutral-800 bg-[#161616] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-emerald-500" />
          <span className="text-[11px] font-bold text-neutral-300 uppercase tracking-widest">Agent Logic</span>
        </div>
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-[pulse_2s_ease-in-out_infinite]"></div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-4 text-xs font-mono text-neutral-400">

        {mainPosition && (
          <div>
            <div className="uppercase tracking-widest text-[#565f89] font-bold mb-1">[Top Position]</div>
            <div className="border hover:border-neutral-600 border-neutral-800 p-2 bg-black whitespace-pre-wrap">
{`Symbol: ${mainPosition.symbol}
Shares: ${mainPosition.shares}
Avg: ${mainPosition.avg_price?.toFixed(2)}${mainPosition.current_price ? `\nPrice: ${mainPosition.current_price.toFixed(2)}` : ''}${mainPosition.unrealized_pnl != null ? `\nP&L: ${mainPosition.unrealized_pnl >= 0 ? '+' : ''}${Math.round(mainPosition.unrealized_pnl).toLocaleString()} (${mainPosition.unrealized_pnl_pct?.toFixed(1)}%)` : ''}`}
            </div>
          </div>
        )}

        <div>
          <div className="uppercase tracking-widest text-[#565f89] font-bold mb-1">[Active State]</div>
          <div className="border hover:border-neutral-600 border-neutral-800 p-2 bg-black whitespace-pre-wrap">
{`exposure: ${summary.exposure_pct ?? '—'}%
cash: ${summary.cash_pct ?? '—'}%
account: NT$ ${summary.account_value ? Math.round(summary.account_value).toLocaleString() : '—'}
today_pnl: ${summary.today_realized_pnl != null ? `${summary.today_realized_pnl >= 0 ? '+' : ''}${Math.round(summary.today_realized_pnl).toLocaleString()}` : '0'}`}
          </div>
        </div>

        {alerts.length > 0 && (
          <div>
            <div className="uppercase tracking-widest text-red-500 font-bold mb-1">[Alerts]</div>
            <div className="border border-red-500/30 p-2 bg-black whitespace-pre-wrap text-red-400">
              {alerts.join('\n')}
            </div>
          </div>
        )}

        <div className="mt-auto border-t border-neutral-800 pt-3 flex flex-col gap-2">
          <button
            onClick={() => fetch('/api/agent/force-execute', { method: 'POST' }).catch(() => {})}
            className="w-full bg-[#1a1a1a] hover:bg-[#222222] border border-neutral-700 text-neutral-300 py-1.5 font-bold tracking-wider transition-colors"
          >
            FORCE EXECUTE
          </button>
          <button
            onClick={() => {
              if (window.confirm('Emergency halt all trading? This will cancel all pending orders.')) {
                fetch('/api/agent/emergency-halt', { method: 'POST' }).catch(() => {});
              }
            }}
            className="w-full bg-[#ff3333] hover:bg-[#ff0000] text-white py-2 font-bold tracking-widest flex justify-center items-center gap-2 transition-colors"
          >
            <AlertOctagon className="w-4 h-4" /> EMERGENCY HALT
          </button>
        </div>

      </div>
    </div>
  );
}
