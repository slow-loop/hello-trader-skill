import { ArrowUpRight, ArrowDownRight, Search, Filter } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const tradeHistory = [
  { id: 'TRD-001', type: 'Buy', symbol: '2330.TW', name: 'TSMC', price: 750.00, shares: 1000, value: 750000, date: '2026-03-21 10:15:00', reason: 'SMA20 Bounce confirmed with high volume. MACD histogram crossed above zero.' },
  { id: 'TRD-002', type: 'Sell', symbol: '2317.TW', name: 'Hon Hai', price: 118.50, shares: 2000, value: 237000, date: '2026-03-20 13:20:00', reason: 'Hit trailing stop loss (ATR-based). Taking partial profits early due to looming CPI report.' },
  { id: 'TRD-003', type: 'Buy', symbol: '2454.TW', name: 'MediaTek', price: 1050.00, shares: 500, value: 525000, date: '2026-03-19 09:45:00', reason: 'Breakout above structural resistance at 1040. Sentiment overlay remains highly positive.' },
];

export default function Trades() {
  const navigate = useNavigate();

  return (
    <div className="p-6 md:p-10 hide-scrollbar flex flex-col gap-8 max-w-7xl mx-auto min-h-full">
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Trade History</h1>
          <p className="text-neutral-400 mt-1">Audit log of all agent executions and rationale</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search ticker or reason..." 
              className="bg-[#12141c] border border-neutral-800 rounded-xl pl-9 pr-4 py-2 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500/50 w-64"
            />
          </div>
          <button className="bg-[#12141c] border border-neutral-800 text-neutral-400 hover:text-white rounded-xl p-2.5 transition-colors">
            <Filter className="w-4 h-4" />
          </button>
        </div>
      </header>

      <section className="flex-1 bg-[#12141c] border border-neutral-800 rounded-2xl overflow-hidden shadow-xl">
        <ul className="divide-y divide-neutral-800/50">
          {tradeHistory.map((trade) => (
            <li key={trade.id} className="p-6 hover:bg-neutral-800/20 transition-colors group">
              <div className="flex flex-col lg:flex-row gap-6 lg:items-center justify-between">
                
                <div className="flex items-start gap-4 lg:w-1/3">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${
                    trade.type === 'Buy' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'
                  }`}>
                    {trade.type === 'Buy' ? <ArrowUpRight className="w-6 h-6" /> : <ArrowDownRight className="w-6 h-6" />}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white flex items-center gap-2 cursor-pointer hover:text-emerald-500 transition-colors" onClick={() => navigate(`/ticker/${trade.symbol.split('.')[0]}`)}>
                      {trade.symbol} <span className="text-sm font-normal text-neutral-500">{trade.name}</span>
                    </h3>
                    <p className="text-sm text-neutral-400 mt-0.5">{trade.date} • {trade.id}</p>
                  </div>
                </div>

                <div className="flex justify-between items-center lg:w-1/4">
                  <div>
                    <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Execution</p>
                    <p className="text-lg font-mono text-white">{trade.shares.toLocaleString()} @ {trade.price.toFixed(2)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-neutral-500 uppercase tracking-wider mb-1">Total Value</p>
                    <p className="text-white font-medium">NT$ {trade.value.toLocaleString()}</p>
                  </div>
                </div>

                <div className="lg:w-2/5 mt-2 lg:mt-0 bg-[#0e1015] rounded-xl p-4 border border-neutral-800/50 relative overflow-hidden group-hover:border-neutral-700 transition-colors">
                  <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500/50"></div>
                  <p className="text-xs font-semibold text-indigo-400 uppercase tracking-widest mb-1">Agent Rationale</p>
                  <p className="text-sm text-neutral-300 leading-relaxed italic">{trade.reason}</p>
                </div>
                
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
