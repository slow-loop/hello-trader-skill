import { Link, NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Trades from './pages/Trades'
import Watchlist from './pages/Watchlist'
import Ticker from './pages/Ticker'
import ResearchDoc from './pages/ResearchDoc'

const navCls = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 text-sm rounded ${isActive ? 'bg-neutral-900 text-white' : 'text-neutral-700 hover:bg-neutral-200'}`

export default function App() {
  return (
    <div className="min-h-full bg-neutral-50 text-neutral-900">
      <header className="bg-white border-b border-neutral-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-4">
          <Link to="/" className="font-bold tracking-wider text-sm">TWTRADER · LOG</Link>
          <nav className="flex gap-1 ml-auto">
            <NavLink to="/" end className={navCls}>Timeline</NavLink>
            <NavLink to="/trades" className={navCls}>Trades</NavLink>
            <NavLink to="/watchlist" className={navCls}>Watchlist</NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/ticker/:symbol" element={<Ticker />} />
          <Route path="/research/:filename" element={<ResearchDoc />} />
        </Routes>
      </main>
    </div>
  )
}
