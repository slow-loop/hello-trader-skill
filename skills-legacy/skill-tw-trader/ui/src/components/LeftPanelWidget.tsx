import { useState, useEffect } from 'react';

interface WatchlistEntry {
  symbol: string;
  notes?: string[];
  updated_at?: string;
  // populated from quote API
  price?: number;
  change?: number;
  change_pct?: number;
}

interface Trade {
  date: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  pnl?: number;
  reason?: string;
}

interface Position {
  symbol: string;
  shares: number;
  avg_price: number;
  current_price?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  allocation_pct?: number;
}

interface LeftPanelWidgetProps {
  onSelectSymbol: (symbol: string, name?: string) => void;
  selectedSymbol: string;
}

export default function LeftPanelWidget({ onSelectSymbol, selectedSymbol }: LeftPanelWidgetProps) {
  const [activeTab, setActiveTab] = useState<'watchlist' | 'orders' | 'positions'>('watchlist');
  const [watchlist, setWatchlist] = useState<WatchlistEntry[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [positionsLoaded, setPositionsLoaded] = useState(false);

  // Fetch watchlist + quotes
  useEffect(() => {
    fetch('/api/agent/watchlist')
      .then(res => res.json())
      .then(async (data: any[]) => {
        if (!data || !Array.isArray(data)) return;

        const entries: WatchlistEntry[] = data.map(d => ({
          symbol: d.symbol || d.ticker || '',
          notes: d.notes,
          updated_at: d.updated_at,
        }));
        setWatchlist(entries);

        // Fetch quotes for each
        for (const entry of entries) {
          if (!entry.symbol) continue;
          try {
            const res = await fetch(`/api/market/quote/${encodeURIComponent(entry.symbol)}`);
            if (res.ok) {
              const quote = await res.json();
              setWatchlist(prev => prev.map(w =>
                w.symbol === entry.symbol
                  ? { ...w, price: quote.price, change: quote.change, change_pct: quote.change_pct }
                  : w
              ));
            }
          } catch { /* ignore */ }
        }
      })
      .catch(() => {});
  }, []);

  // Fetch trades
  useEffect(() => {
    if (activeTab !== 'orders') return;
    fetch('/api/trades')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setTrades(data.slice(-20).reverse());
        }
      })
      .catch(() => {});
  }, [activeTab]);

  // Fetch positions
  useEffect(() => {
    if (activeTab !== 'positions') return;
    fetch('/api/portfolio')
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.positions)) {
          setPositions(data.positions);
          setPositionsLoaded(true);
        }
      })
      .catch(() => {});
  }, [activeTab]);

  const TW_NAMES: Record<string, string> = {
    '2330': 'Taiwan Semiconductor',
    '2454': 'MediaTek',
    '2317': 'Hon Hai',
    '2412': 'Chunghwa Telecom',
    '2308': 'Delta Electronics',
    '2303': 'United Microelectronics',
    '3711': 'ASMedia Technology',
    '3034': 'Novatek',
    '2382': 'Quanta Computer',
    '2357': 'Asustek',
    '2395': 'Advantech',
    '2379': 'Realtek',
    '2408': 'Innolux',
    '2474': 'Catcher Technology',
    '2301': 'Lite-On Technology',
    '2313': 'Winbond',
    '2455': 'eMemory Technology',
    '3324': 'Siliconmotion',
  };

  const stripTW = (sym: string) => sym.replace('.TW', '').replace('.TWO', '');
  const getStockName = (sym: string) => TW_NAMES[stripTW(sym)] ?? stripTW(sym);

  return (
    <div className="flex flex-col h-full bg-[#111111] border-r border-[#1f2937] w-[320px] flex-shrink-0">
      {/* Unified Tab Header */}
      <div className="flex border-b border-[#1f2937] bg-[#161616] overflow-x-auto hide-scrollbar shrink-0">
        <button
          onClick={() => setActiveTab('watchlist')}
          className={`px-3 py-2 text-[11px] font-bold tracking-wider uppercase border-r border-[#1f2937] whitespace-nowrap transition-colors flex-1 ${activeTab === 'watchlist' ? 'text-emerald-500 bg-[#1f2937]/50' : 'text-neutral-500 hover:text-white'}`}
        >
          Watchlist
        </button>
        <button
          onClick={() => setActiveTab('orders')}
          className={`px-3 py-2 text-[11px] font-bold tracking-wider uppercase border-r border-[#1f2937] whitespace-nowrap transition-colors flex-1 ${activeTab === 'orders' ? 'text-emerald-500 bg-[#1f2937]/50' : 'text-neutral-500 hover:text-white'}`}
        >
          Orders
        </button>
        <button
          onClick={() => setActiveTab('positions')}
          className={`px-3 py-2 text-[11px] font-bold tracking-wider uppercase whitespace-nowrap transition-colors flex-[1.5] ${activeTab === 'positions' ? 'text-emerald-500 bg-[#1f2937]/50' : 'text-neutral-500 hover:text-white'}`}
        >
          Positions ({positionsLoaded ? positions.length : '—'})
        </button>
      </div>

      <div className="flex-1 overflow-y-auto w-full">
        {activeTab === 'watchlist' && (
          <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
            <thead className="bg-[#1a1a1a] text-neutral-500 uppercase sticky top-0 z-10 border-b border-[#1f2937]">
              <tr>
                <th className="px-3 py-1.5 font-normal w-12">Sym</th>
                <th className="px-3 py-1.5 font-normal text-right">Last</th>
                <th className="px-3 py-1.5 font-normal text-right">Chg%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e1e1e]">
              {watchlist.length === 0 && (
                <tr><td colSpan={3} className="px-3 py-4 text-neutral-500 text-center">Loading...</td></tr>
              )}
              {watchlist.map((item) => {
                const isUp = (item.change_pct ?? 0) > 0;
                const isZero = !item.change_pct || item.change_pct === 0;
                const color = isZero ? 'text-neutral-400' : isUp ? 'text-emerald-500' : 'text-red-500';
                const isSelected = item.symbol === selectedSymbol;
                return (
                  <tr
                    key={item.symbol}
                    className={`hover:bg-[#1a1a1a] cursor-pointer group ${isSelected ? 'bg-[#1a1a1a]' : ''}`}
                    onClick={() => onSelectSymbol(item.symbol, getStockName(item.symbol))}
                  >
                    <td className="px-3 py-2 align-middle">
                      <div className={`font-bold ${isSelected ? 'text-emerald-500' : 'text-neutral-200 group-hover:text-emerald-500'} transition-colors`}>{stripTW(item.symbol)}</div>
                    </td>
                    <td className={`px-3 py-2 align-middle text-right font-bold ${color}`}>
                      {item.price != null ? item.price.toFixed(2) : '—'}
                    </td>
                    <td className={`px-3 py-2 align-middle text-right ${color}`}>
                      {item.change_pct != null ? `${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}%` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {activeTab === 'orders' && (
          <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
            <thead className="bg-[#1a1a1a] text-neutral-500 uppercase sticky top-0 z-10 border-b border-[#1f2937]">
              <tr>
                <th className="px-3 py-1.5 font-normal">Time/Sym</th>
                <th className="px-3 py-1.5 font-normal text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e1e1e]">
              {trades.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-4 text-neutral-500 text-center">No trades yet</td></tr>
              )}
              {trades.map((t, idx) => (
                <tr key={idx} className="hover:bg-[#1a1a1a]">
                  <td className="px-3 py-2 text-neutral-500">
                    <div className="text-white font-bold">{t.symbol}</div>
                    <div className="text-[10px]">{t.date?.slice(0, 16)}</div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className={t.action === 'BUY' ? 'text-emerald-500 font-bold' : 'text-red-500 font-bold'}>{t.action} {t.quantity}</div>
                    <div className="text-[10px] text-neutral-400">@ {t.price?.toFixed(2)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {activeTab === 'positions' && (
          <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
            <thead className="bg-[#1a1a1a] text-neutral-500 uppercase sticky top-0 z-10 border-b border-[#1f2937]">
              <tr>
                <th className="px-3 py-1.5 font-normal">Symbol</th>
                <th className="px-3 py-1.5 font-normal text-right">Shares</th>
                <th className="px-3 py-1.5 font-normal text-right">P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1e1e1e]">
              {positions.length === 0 && (
                <tr><td colSpan={3} className="px-3 py-4 text-neutral-500 text-center">No positions</td></tr>
              )}
              {positions.map((p) => {
                const pnlColor = (p.unrealized_pnl ?? 0) >= 0 ? 'text-emerald-500' : 'text-red-500';
                return (
                  <tr key={p.symbol} className="hover:bg-[#1a1a1a] cursor-pointer" onClick={() => onSelectSymbol(p.symbol, getStockName(p.symbol))}>
                    <td className="px-3 py-2">
                      <div className="text-white font-bold">{stripTW(p.symbol)}</div>
                      <div className="text-[10px] text-neutral-500">avg {p.avg_price?.toFixed(2)}</div>
                    </td>
                    <td className="px-3 py-2 text-right text-neutral-300">{p.shares}</td>
                    <td className={`px-3 py-2 text-right ${pnlColor}`}>
                      {p.unrealized_pnl != null ? `${p.unrealized_pnl >= 0 ? '+' : ''}${Math.round(p.unrealized_pnl).toLocaleString()}` : '—'}
                      {p.unrealized_pnl_pct != null && (
                        <div className="text-[10px]">{p.unrealized_pnl_pct >= 0 ? '+' : ''}{p.unrealized_pnl_pct.toFixed(1)}%</div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
