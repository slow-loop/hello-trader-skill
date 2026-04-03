import { useParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Activity, ShieldAlert, Target, Zap } from 'lucide-react';

const mockPriceData = Array.from({ length: 50 }, (_, i) => ({
  time: `10:${i < 10 ? '0'+i : i}`,
  price: 800 + Math.sin(i / 5) * 10 + (Math.random() - 0.5) * 5,
  sma20: 800 + Math.sin((i - 5) / 5) * 8
}));

export default function TickerDetails() {
  const { symbol } = useParams();
  const displaySymbol = symbol || '2330';

  return (
    <div className="p-6 md:p-10 hide-scrollbar flex flex-col gap-6 h-full max-w-[1600px] mx-auto">
      <header className="flex items-center justify-between border-b border-neutral-800 pb-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-neutral-800 rounded-xl flex items-center justify-center font-bold text-xl text-white">
            {displaySymbol === '2330' ? 'TS' : displaySymbol.slice(0, 2)}
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
              {displaySymbol}.TW
              <span className="text-sm font-normal px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">Active Monitoring</span>
            </h1>
            <p className="text-neutral-400 mt-1">{displaySymbol === '2330' ? 'Taiwan Semiconductor Mfg. Co. Ltd.' : 'Stock Overview'}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-4xl font-bold text-white">805.50</p>
          <p className="text-emerald-500 font-medium text-sm mt-1">+5.50 (+0.69%)</p>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-0">
        {/* Chart Area */}
        <section className="col-span-1 lg:col-span-3 bg-[#12141c] border border-neutral-800 rounded-2xl p-4 flex flex-col">
          <div className="flex gap-4 mb-4">
            <button className="text-white font-medium text-sm px-4 py-2 bg-neutral-800 rounded-lg hover:bg-neutral-700 transition-colors">1D</button>
            <button className="text-neutral-400 font-medium text-sm px-4 py-2 hover:text-white transition-colors">1W</button>
            <button className="text-neutral-400 font-medium text-sm px-4 py-2 hover:text-white transition-colors">1M</button>
            <div className="h-6 w-px bg-neutral-800 my-auto mx-2"></div>
            <button className="text-emerald-500 font-medium text-sm px-4 py-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2">
              <Activity className="w-4 h-4" /> Indicators
            </button>
          </div>
          
          <div className="flex-1 min-h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockPriceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
                <XAxis dataKey="time" stroke="#525252" fontSize={12} tickLine={false} axisLine={false} dy={10} minTickGap={30} />
                <YAxis stroke="#525252" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} dx={-10} orientation="right" />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: '#181a24', borderColor: '#262626', borderRadius: '12px' }}
                  itemStyle={{ color: '#fff' }}
                />
                <Line type="monotone" dataKey="price" stroke="#ffffff" strokeWidth={2} dot={false} activeDot={{ r: 6, fill: '#10b981', strokeWidth: 0 }} />
                <Line type="monotone" dataKey="sma20" stroke="#a78bfa" strokeWidth={2} dot={false} strokeDasharray="5 5" name="SMA 20" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* AI Perspective Panel */}
        <section className="col-span-1 border border-emerald-500/20 bg-[#12141c] rounded-2xl overflow-hidden flex flex-col relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl"></div>
          
          <div className="p-4 bg-emerald-500/5 border-b border-emerald-500/10 flex items-center justify-between">
            <h2 className="text-emerald-500 font-bold flex items-center gap-2">
              <Zap className="w-5 h-5" fill="currentColor" />
              Agent's Perspective
            </h2>
          </div>
          
          <div className="p-5 flex-1 flex flex-col gap-6 overflow-y-auto">
            <div>
              <p className="text-xs text-neutral-400 uppercase tracking-widest font-semibold mb-2">Technical Summary</p>
              <div className="bg-[#1a1c24] rounded-xl p-4 border border-neutral-800">
                <p className="text-white text-sm leading-relaxed">
                  Price is trading above the 20 SMA with bullish momentum. 
                  MACD shows recent crossover, supporting upside continuation.
                  Volume profile suggests strong accumulation at 795 level.
                </p>
              </div>
            </div>

            <div>
              <p className="text-xs text-neutral-400 uppercase tracking-widest font-semibold mb-2 flex items-center gap-2">
                <Target className="w-4 h-4" /> Next Actions
              </p>
              <div className="space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-neutral-800 pb-2">
                  <span className="text-neutral-400">Entry Target</span>
                  <span className="text-white font-medium">802.00</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-neutral-800 pb-2">
                  <span className="text-neutral-400">Profit Target</span>
                  <span className="text-emerald-500 font-medium">820.50</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-neutral-400">Stop Loss</span>
                  <span className="text-red-500 font-medium flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3" /> 788.00
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-auto pt-4 flex gap-2">
              <button className="flex-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 rounded-xl py-3 font-medium text-sm transition-colors uppercase tracking-wider">
                Halt Tradng
              </button>
              <button className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-[#0e1015] rounded-xl py-3 font-bold text-sm transition-colors uppercase tracking-wider">
                Force Buy
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
