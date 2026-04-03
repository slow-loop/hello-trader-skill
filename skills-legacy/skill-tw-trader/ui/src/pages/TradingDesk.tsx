import { useState, useEffect, useRef } from 'react';
import LeftPanelWidget from '../components/LeftPanelWidget';
import ChartWidget from '../components/ChartWidget';
import AgentWidget from '../components/AgentWidget';

interface Trade {
  date: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  pnl?: number;
  reason?: string;
}

export default function TradingDesk() {
  const [selectedSymbol, setSelectedSymbol] = useState('2330.TW');
  const [selectedName, setSelectedName] = useState('Taiwan Semiconductor');
  const [selectedDays, setSelectedDays] = useState(150);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [visibleIndicators, setVisibleIndicators] = useState<string[]>(['sma20', 'sma60']);
  const [showIndicatorsMenu, setShowIndicatorsMenu] = useState(false);
  const indicatorsMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showIndicatorsMenu) return;
    const handler = (e: MouseEvent) => {
      if (indicatorsMenuRef.current && !indicatorsMenuRef.current.contains(e.target as Node)) {
        setShowIndicatorsMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showIndicatorsMenu]);

  useEffect(() => {
    fetch('/api/trades')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setTrades(data);
      })
      .catch(() => {});
  }, []);

  const handleSelectSymbol = (symbol: string, name?: string) => {
    setSelectedSymbol(symbol);
    if (name) setSelectedName(name);
  };

  return (
    <div className="flex w-full h-full min-h-0 bg-black">
      {/* Left Column: Combined Tab Panel */}
      <LeftPanelWidget onSelectSymbol={handleSelectSymbol} selectedSymbol={selectedSymbol} />

      {/* Center Column: Multi-pane Charts */}
      <div className="flex-1 flex flex-col h-full min-w-0 border-r border-[#1f2937] relative bg-black">
         {/* Top Navbar for the chart area */}
         <div className="h-8 shrink-0 bg-[#0a0a0a] border-b border-[#1f2937] flex items-center px-4 justify-between">
          <div className="flex items-center gap-4">
            <span className="font-bold text-xs tracking-widest text-[#d1d5db]">{selectedSymbol} <span className="text-neutral-500 font-normal">| {selectedName}</span></span>
            <div className="flex gap-2 text-[10px] font-bold text-neutral-500 items-center">
              <button 
                onClick={() => setSelectedDays(7)}
                className={`transition-colors ${selectedDays === 7 ? 'text-emerald-500 bg-[#1f2937]/50 px-1 rounded-sm' : 'hover:text-white'}`}
              >1W</button>
              <button 
                onClick={() => setSelectedDays(30)}
                className={`transition-colors ${selectedDays === 30 ? 'text-emerald-500 bg-[#1f2937]/50 px-1 rounded-sm' : 'hover:text-white'}`}
              >1M</button>
              <button 
                onClick={() => setSelectedDays(90)}
                className={`transition-colors ${selectedDays === 90 ? 'text-emerald-500 bg-[#1f2937]/50 px-1 rounded-sm' : 'hover:text-white'}`}
              >3M</button>
              <button 
                onClick={() => setSelectedDays(180)}
                className={`transition-colors ${selectedDays === 180 ? 'text-emerald-500 bg-[#1f2937]/50 px-1 rounded-sm' : 'hover:text-white'}`}
              >6M</button>
              <button 
                onClick={() => setSelectedDays(365)}
                className={`transition-colors ${selectedDays === 365 ? 'text-emerald-500 bg-[#1f2937]/50 px-1 rounded-sm' : 'hover:text-white'}`}
              >1Y</button>
              <div className="w-px h-3 bg-[#1f2937] mx-1"></div>
              <div className="relative" ref={indicatorsMenuRef}>
                <button
                  onClick={() => setShowIndicatorsMenu(!showIndicatorsMenu)}
                  className={`hover:text-emerald-400 text-emerald-500 transition-colors flex items-center gap-1 bg-emerald-500/10 px-1.5 py-0.5 rounded border ${showIndicatorsMenu ? 'border-emerald-500' : 'border-emerald-500/20'}`}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                  Indicators
                </button>
                {showIndicatorsMenu && (
                  <div className="absolute top-full right-0 mt-1 bg-[#0a0a0a] border border-[#1f2937] rounded shadow-xl z-50 py-1 min-w-[120px]">
                    {[
                      { id: 'sma20', label: 'SMA 20' },
                      { id: 'sma60', label: 'SMA 60' },
                      { id: 'ema20', label: 'EMA 20' },
                    ].map(ind => (
                      <label key={ind.id} className="flex items-center px-2 py-1.5 hover:bg-[#111111] cursor-pointer gap-2">
                        <input 
                          type="checkbox" 
                          checked={visibleIndicators.includes(ind.id)}
                          onChange={(e) => {
                            if (e.target.checked) setVisibleIndicators([...visibleIndicators, ind.id]);
                            else setVisibleIndicators(visibleIndicators.filter(i => i !== ind.id));
                          }}
                          className="w-3 h-3 rounded bg-black border-[#1f2937] text-emerald-500 focus:ring-0"
                        />
                        <span className="text-[10px] text-neutral-300 font-bold">{ind.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
         </div>
         <div className="flex-1 min-h-[400px]">
            <ChartWidget symbol={selectedSymbol} days={selectedDays} trades={trades} visibleIndicators={visibleIndicators} />
         </div>
      </div>

      {/* Right Column: Agent Logic */}
      <div className="h-full shrink-0">
        <AgentWidget />
      </div>
    </div>
  )
}
