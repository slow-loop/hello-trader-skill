import { useState } from 'react';
import { Bot, BookOpen, Brain, Settings, AlertTriangle, Play, Pause } from 'lucide-react';

export default function AgentHub() {
  const [activeTab, setActiveTab] = useState<'journal' | 'memory' | 'settings'>('journal');
  const [agentStatus, setAgentStatus] = useState<'running' | 'halted'>('running');

  return (
    <div className="p-6 md:p-10 hide-scrollbar flex flex-col gap-6 max-w-7xl mx-auto h-full">
      <header className="flex items-center justify-between border-b border-neutral-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight flex items-center gap-3">
            <Bot className="w-8 h-8 text-emerald-500" /> Agent Hub
          </h1>
          <p className="text-neutral-400 mt-1">Brain, Memory, and System Configuration</p>
        </div>
        <div className="flex gap-2">
          {agentStatus === 'running' ? (
            <button 
              onClick={() => setAgentStatus('halted')}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 rounded-xl transition-colors font-medium text-sm w-36 justify-center uppercase tracking-wider"
            >
              <Pause className="w-4 h-4" fill="currentColor" /> Halt AI
            </button>
          ) : (
            <button 
              onClick={() => setAgentStatus('running')}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500 border border-emerald-500/30 rounded-xl transition-colors font-medium text-sm w-36 justify-center uppercase tracking-wider"
            >
              <Play className="w-4 h-4" fill="currentColor" /> Resume AI
            </button>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-neutral-800">
        <TabButton active={activeTab === 'journal'} onClick={() => setActiveTab('journal')} icon={<BookOpen className="w-4 h-4"/>} label="Journal (Live Feed)" />
        <TabButton active={activeTab === 'memory'} onClick={() => setActiveTab('memory')} icon={<Brain className="w-4 h-4"/>} label="Memory (Lessons)" />
        <TabButton active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} icon={<Settings className="w-4 h-4"/>} label="Settings (Persona)" />
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto bg-[#12141c] border border-neutral-800 rounded-2xl p-6 relative">
        {activeTab === 'journal' && (
          <div className="flex flex-col gap-6">
            <div className="border-l-2 border-neutral-800 pl-4 py-1 relative">
              <div className="absolute w-3 h-3 bg-emerald-500 rounded-full -left-[7px] top-1.5 shadow-[0_0_8px_rgba(16,185,129,0.8)]"></div>
              <p className="text-xs text-neutral-500 mb-1 font-mono">10:16:04 AM</p>
              <p className="text-white">Executed Buy order for <span className="text-emerald-500 font-bold">2330.TW</span>. Price 802.00 is holding strong above VWAP. Recording state to memory.</p>
            </div>
            <div className="border-l-2 border-neutral-800 pl-4 py-1 relative">
              <div className="absolute w-3 h-3 bg-neutral-700 rounded-full -left-[7px] top-1.5"></div>
              <p className="text-xs text-neutral-500 mb-1 font-mono">10:10:00 AM</p>
              <p className="text-neutral-300">Scanning market conditions. Filtered 35 stocks. 3 active setups found.</p>
            </div>
            <div className="border-l-2 border-neutral-800 pl-4 py-1 relative">
              <div className="absolute w-3 h-3 bg-indigo-500 rounded-full -left-[7px] top-1.5"></div>
              <p className="text-xs text-neutral-500 mb-1 font-mono">09:00:00 AM</p>
              <p className="text-indigo-200">Waking up. Market open detected. Checking macro news feed.</p>
            </div>
          </div>
        )}

        {activeTab === 'memory' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-[#1a1c24] p-5 rounded-xl border border-neutral-800/50">
              <h3 className="text-lg font-semibold text-white mb-4 border-b border-neutral-800 pb-2 flex justify-between">
                <span>Working State</span>
                <span className="text-xs font-mono text-neutral-500">state.md</span>
              </h3>
              <pre className="text-sm text-neutral-400 font-mono whitespace-pre-wrap">
{`current_focus: Taiwanese Semi Sector
risk_level: Moderate
cash_allocation: 60%
open_orders: 0
halted: false`}
              </pre>
            </div>
            <div className="bg-[#1a1c24] p-5 rounded-xl border border-neutral-800/50 relative overflow-hidden">
              <div className="absolute bottom-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl"></div>
              <h3 className="text-lg font-semibold text-indigo-400 mb-4 border-b border-indigo-500/20 pb-2 flex justify-between relative z-10">
                <span>Learned Lessons</span>
                <span className="text-xs font-mono text-indigo-500/50">lessons.md</span>
              </h3>
              <ul className="list-disc pl-5 text-sm text-indigo-100/70 space-y-2 relative z-10">
                <li>Never trade the first 15 mins of open on CPI days. (Learned 2025-11-20)</li>
                <li>Bollinger band break must be confirmed by volume &gt; 150% average. False breakouts cost 5% drawdowns previously.</li>
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="flex flex-col gap-8 max-w-3xl">
            <div>
              <h2 className="text-xl font-bold text-white mb-4">Prompt & Persona Configuration</h2>
              <div className="bg-[#0e1015] p-4 rounded-xl border border-neutral-800 mb-4 font-mono text-sm text-neutral-300">
                <p className="text-neutral-500 mb-2"># PERSONA.md snippet</p>
                You are a pragmatic, risk-averse Taiwan stock market trader...
              </div>
              <button className="px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-white rounded-lg text-sm transition-colors">Edit Persona</button>
            </div>

            <div className="h-px w-full bg-neutral-800"></div>

            <div>
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2 text-red-500">
                <AlertTriangle className="w-5 h-5"/> Danger Zone
              </h2>
              <div className="border border-red-500/30 bg-red-500/5 rounded-2xl p-6 flex items-center justify-between">
                <div>
                  <h3 className="text-red-400 font-bold text-lg mb-1">Emergency Liquidate & Halt</h3>
                  <p className="text-sm text-red-400/70">Close all open positions at market price and disable the AI completely.</p>
                </div>
                <button className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-xl font-bold uppercase tracking-wider shadow-[0_0_15px_rgba(220,38,38,0.5)] transition-all transform hover:scale-105">
                  Panic Button
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TabButton({ active, onClick, icon, label }: any) {
  return (
    <button
      onClick={onClick}
      className={`pb-3 px-2 flex items-center gap-2 text-sm font-medium transition-colors border-b-2 ${
        active 
        ? 'border-emerald-500 text-emerald-500' 
        : 'border-transparent text-neutral-500 hover:text-white hover:border-neutral-700'
      }`}
    >
      {icon} {label}
    </button>
  );
}
