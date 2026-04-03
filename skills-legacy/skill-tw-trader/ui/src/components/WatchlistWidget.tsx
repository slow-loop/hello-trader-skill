import { Search, List } from 'lucide-react';

const watchlist = [
  { sym: '2330', name: 'TSMC', price: '805.50', chg: '+5.50', chgPct: '+0.69%' },
  { sym: '2317', name: 'Hon Hai', price: '118.50', chg: '-1.50', chgPct: '-1.25%' },
  { sym: '2454', name: 'MediaTek', price: '1050.00', chg: '+5.00', chgPct: '+0.48%' },
  { sym: '2308', name: 'Delta', price: '300.50', chg: '0.00', chgPct: '0.00%' },
  { sym: '2382', name: 'Quanta', price: '255.00', chg: '+3.50', chgPct: '+1.39%' },
  { sym: '3231', name: 'Wistron', price: '120.00', chg: '-0.50', chgPct: '-0.41%' },
];

export default function WatchlistWidget() {
  return (
    <div className="flex flex-col h-full bg-[#111111] border-r border-neutral-800 w-64 flex-shrink-0">
      <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800 bg-[#161616]">
        <div className="flex gap-2">
          <List className="w-4 h-4 text-neutral-400" />
          <span className="text-xs font-bold text-neural-300 uppercase tracking-widest">Watchlist</span>
        </div>
        <Search className="w-4 h-4 text-neutral-500 cursor-pointer hover:text-white" />
      </div>

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-left text-[11px] font-mono whitespace-nowrap">
          <thead className="bg-[#1a1a1a] text-neutral-500 uppercase sticky top-0 z-10 border-b border-neutral-800">
            <tr>
              <th className="px-2 py-1 font-normal w-12">Sym</th>
              <th className="px-2 py-1 font-normal text-right">Last</th>
              <th className="px-2 py-1 font-normal text-right">Chg%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e1e1e]">
            {watchlist.map((item) => {
              const isUp = item.chg.startsWith('+');
              const isZero = item.chg === '0.00';
              const color = isZero ? 'text-neutral-400' : isUp ? 'text-emerald-500' : 'text-red-500';

              return (
                <tr key={item.sym} className="hover:bg-[#1a1a1a] cursor-pointer group">
                  <td className="px-2 py-1.5 align-middle">
                    <div className="font-bold text-neutral-200 group-hover:text-emerald-500 transition-colors">{item.sym}</div>
                    <div className="text-[10px] text-neutral-500 truncate max-w-[60px] cursor-default" title={item.name}>{item.name.slice(0, 8)}</div>
                  </td>
                  <td className={`px-2 py-1.5 align-middle text-right font-bold ${color}`}>
                    {item.price}
                  </td>
                  <td className={`px-2 py-1.5 align-middle text-right ${color}`}>
                    <div className="bg-opacity-10 px-1 py-0.5 inline-block">
                      {item.chgPct}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
