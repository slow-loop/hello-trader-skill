import { Activity } from 'lucide-react';

const trades = [
  { time: '10:15:30', sym: '2330.TW', side: 'BUY', qty: 1000, price: 802.00, status: 'FILLED' },
  { time: '10:10:05', sym: '2317.TW', side: 'SELL', qty: 2000, price: 118.50, status: 'FILLED' },
  { time: '09:45:00', sym: '2454.TW', side: 'BUY', qty: 500, price: 1045.00, status: 'FILLED' },
  { time: '09:05:12', sym: '2382.TW', side: 'BUY', qty: 3000, price: 251.50, status: 'CANCELED' },
];

export default function TradesWidget() {
  return (
    <div className="flex flex-col h-48 bg-[#0a0a0a] border-t border-neutral-800 shrink-0">
      <div className="flex border-b border-neutral-800 bg-[#141414]">
        <button className="px-4 py-1.5 text-xs font-bold text-white border-r border-neutral-800">Orders & Trades</button>
        <button className="px-4 py-1.5 text-xs font-bold text-neutral-500 hover:text-white border-r border-neutral-800">Positions (3)</button>
        <button className="px-4 py-1.5 text-xs font-bold text-neutral-500 hover:text-white border-r border-neutral-800 flex items-center gap-1"><Activity className="w-3 h-3"/> AI Logs</button>
      </div>
      
      <div className="flex-1 overflow-y-auto w-full">
         <table className="w-full text-left text-[11px] font-mono whitespace-nowrap table-fixed">
          <thead className="bg-[#1a1a1a] text-neutral-500 uppercase sticky top-0 z-10 border-b border-neutral-800">
            <tr>
              <th className="px-3 py-1 font-normal w-24">Time</th>
              <th className="px-3 py-1 font-normal w-28">Symbol</th>
              <th className="px-3 py-1 font-normal w-20">Side</th>
              <th className="px-3 py-1 font-normal w-24 text-right">Qty</th>
              <th className="px-3 py-1 font-normal w-24 text-right">Price</th>
              <th className="px-3 py-1 font-normal w-24">Status</th>
              <th className="px-3 py-1 font-normal">Memo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e1e1e]">
            {trades.map((t, idx) => (
              <tr key={idx} className="hover:bg-[#1a1a1a]">
                <td className="px-3 py-1.5 text-neutral-500">{t.time}</td>
                <td className="px-3 py-1.5 font-bold text-neutral-300">{t.sym}</td>
                <td className={`px-3 py-1.5 font-bold ${t.side === 'BUY' ? 'text-emerald-500' : 'text-red-500'}`}>{t.side}</td>
                <td className="px-3 py-1.5 text-right">{t.qty}</td>
                <td className="px-3 py-1.5 text-right font-bold text-white">{t.price.toFixed(2)}</td>
                <td className={`px-3 py-1.5 ${t.status === 'FILLED' ? 'text-neutral-300' : 'text-neutral-600 line-through'}`}>{t.status}</td>
                <td className="px-3 py-1.5 text-neutral-500 truncate" title="Agent Exec">Agent Exec - SMA Breakout</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
