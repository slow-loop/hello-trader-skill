import { Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Briefcase, MessageSquare, Monitor } from 'lucide-react';
import TradingDesk from './pages/TradingDesk';
import Portfolio from './pages/Portfolio';
import Social from './pages/Social';

function Sidebar() {
  return (
    <div className="w-14 h-full bg-[#0a0a0a] border-r border-[#1f2937] flex flex-col items-center py-4 gap-6 shrink-0 z-50">
      <div className="w-8 h-8 flex items-center justify-center bg-emerald-500/10 rounded-lg text-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)] mb-4" title="AI Status: ACTIVE">
        <Activity className="w-5 h-5" />
      </div>
      <NavLink to="/" className={({isActive}) => `p-2.5 rounded-xl transition-colors ${isActive ? 'bg-[#1f2937] text-white shadow-sm' : 'text-neutral-500 hover:text-white hover:bg-[#111111]'}`} title="Trading Terminal">
        <Monitor className="w-5 h-5" />
      </NavLink>
      <NavLink to="/portfolio" className={({isActive}) => `p-2.5 rounded-xl transition-colors ${isActive ? 'bg-[#1f2937] text-white shadow-sm' : 'text-neutral-500 hover:text-white hover:bg-[#111111]'}`} title="Portfolio & History">
        <Briefcase className="w-5 h-5" />
      </NavLink>
      <NavLink to="/social" className={({isActive}) => `p-2.5 rounded-xl transition-colors ${isActive ? 'bg-[#1f2937] text-white shadow-sm' : 'text-neutral-500 hover:text-white hover:bg-[#111111]'}`} title="Social & Review">
        <MessageSquare className="w-5 h-5" />
      </NavLink>
    </div>
  );
}

export default function App() {
  return (
    <div className="h-screen w-screen flex bg-black text-white font-sans overflow-hidden select-none">
      <Sidebar />
      <main className="flex-1 w-full h-full min-w-0 bg-black">
        <Routes>
          <Route path="/" element={<TradingDesk />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/social" element={<Social />} />
        </Routes>
      </main>
    </div>
  );
}
