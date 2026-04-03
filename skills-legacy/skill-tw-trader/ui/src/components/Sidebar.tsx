import { NavLink } from 'react-router-dom';
import { Briefcase, List, LineChart, History, Bot, MessageSquare } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { name: 'Portfolio', path: '/', icon: Briefcase },
  { name: 'Watchlist', path: '/watchlist', icon: List },
  { name: 'Ticker', path: '/ticker/2330', icon: LineChart },
  { name: 'Trades', path: '/trades', icon: History },
  { name: 'Agent', path: '/agent', icon: Bot },
  { name: 'Threads', path: '/threads', icon: MessageSquare },
];

export default function Sidebar() {
  return (
    <aside className="w-16 md:w-64 border-r border-neutral-800 bg-[#12141c] flex flex-col transition-all duration-300">
      <div className="h-16 flex items-center justify-center md:justify-start md:px-6 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <Bot className="w-8 h-8 text-emerald-500" />
          <span className="hidden md:block font-bold text-lg text-white tracking-wide">
            TW Trader<span className="text-emerald-500">.</span>
          </span>
        </div>
      </div>
      
      <nav className="flex-1 py-6 flex flex-col gap-2 px-2 md:px-4">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group text-sm font-medium",
                isActive 
                  ? "bg-emerald-500/10 text-emerald-400 shadow-[inset_2px_0_0_0_#10b981]" 
                  : "text-neutral-400 hover:bg-neutral-800/50 hover:text-white"
              )
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            <span className="hidden md:block">{item.name}</span>
          </NavLink>
        ))}
      </nav>
      
      <div className="p-4 border-t border-neutral-800 hidden md:block">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <span className="text-emerald-500 font-bold text-xs">AI</span>
          </div>
          <div>
            <p className="text-sm font-medium text-white">Agent Active</p>
            <p className="text-xs text-emerald-500">Monitoring Market</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
