import { Search, TrendingUp, AlertCircle, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const watchlistData = [
  { symbol: '2330.TW', name: 'Taiwan Semiconductor', price: 800.00, change: '+1.5%', condition: 'Near SMA20 bounce zone' },
  { symbol: '2454.TW', name: 'MediaTek', price: 1100.00, change: '-0.8%', condition: 'Waiting for MACD crossover' },
  { symbol: '3231.TW', name: 'Wistron', price: 120.50, change: '+3.2%', condition: 'Breaking out of resistance' },
];

const headlines = [
  { source: 'Reuters', title: 'TSMC Q1 Revenue beats expectations amid AI boom', time: '10m ago', sentiment: 'positive' },
  { source: 'Bloomberg', title: 'Taiwan Central Bank holds rates steady', time: '1h ago', sentiment: 'neutral' },
  { source: 'Financial Times', title: 'Tech stocks drive Asian markets higher', time: '2h ago', sentiment: 'positive' },
];

export default function Watchlist() {
  const navigate = useNavigate();

  return (
    <div className="p-6 md:p-10 hide-scrollbar flex flex-col gap-8 max-w-7xl mx-auto">
      <header>
        <h1 className="text-3xl font-bold text-white tracking-tight">Watchlist & Market</h1>
        <p className="text-neutral-400 mt-1">AI agent monitoring conditions and market context</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Watchlist Section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <Search className="w-5 h-5 text-emerald-500" />
              Agent Watchlist
            </h2>
            <div className="px-3 py-1 rounded-full bg-neutral-800 text-xs font-medium text-neutral-300">
              3 Active
            </div>
          </div>
          
          <div className="flex flex-col gap-3">
            {watchlistData.map((item) => (
              <div 
                key={item.symbol}
                onClick={() => navigate(`/ticker/${item.symbol.split('.')[0]}`)}
                className="bg-[#12141c] hover:bg-[#1a1c24] border border-neutral-800 rounded-2xl p-5 cursor-pointer transition-all group"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-emerald-500 transition-colors">{item.symbol}</h3>
                    <p className="text-sm text-neutral-500">{item.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-mono text-white">{item.price.toFixed(2)}</p>
                    <p className={item.change.startsWith('+') ? 'text-emerald-500 text-sm' : 'text-red-500 text-sm'}>
                      {item.change}
                    </p>
                  </div>
                </div>
                <div className="bg-neutral-900/50 rounded-lg p-3 border border-neutral-800/50 flex items-start gap-2">
                  <Bot className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-neutral-300"><span className="text-emerald-500 font-medium">Trigger:</span> {item.condition}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Market News Section */}
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-500" />
              Market Context
            </h2>
          </div>

          <div className="bg-[#12141c] border border-neutral-800 rounded-2xl p-6 h-full flex flex-col gap-5 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl"></div>
            
            {headlines.map((news, i) => (
              <div key={i} className="flex gap-4 items-start pb-5 border-b border-neutral-800/50 last:border-0 last:pb-0 relative z-10">
                <div className="mt-1">
                  {news.sentiment === 'positive' && <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></div>}
                  {news.sentiment === 'negative' && <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></div>}
                  {news.sentiment === 'neutral' && <div className="w-2 h-2 rounded-full bg-neutral-400"></div>}
                </div>
                <div>
                  <div className="flex gap-2 text-xs text-neutral-500 font-medium mb-1 items-center">
                    <span>{news.source}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3"/> {news.time}</span>
                  </div>
                  <h4 className="text-neutral-200 hover:text-white transition-colors cursor-pointer text-sm leading-relaxed">{news.title}</h4>
                </div>
              </div>
            ))}

            <div className="mt-auto pt-4 relative z-10">
              <div className="bg-neutral-900/80 backdrop-blur-sm border border-neutral-800 rounded-xl p-4 flex gap-3">
                <AlertCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                <p className="text-sm text-neutral-300 leading-relaxed">
                  <span className="text-white font-medium">Agent Summary:</span> Market broadly positive, heavily driven by tech sector block orders. Volatility remains low, safe to execute algorithmic setups targeting upside breakouts.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

// Custom simple bot icon for this file since lucide bot doesn't auto import if not specified
function Bot(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 8V4H8" />
      <rect width="16" height="12" x="4" y="8" rx="2" />
      <path d="M2 14h2" />
      <path d="M20 14h2" />
      <path d="M15 13v2" />
      <path d="M9 13v2" />
    </svg>
  );
}
