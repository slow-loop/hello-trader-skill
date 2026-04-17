import { Routes, Route, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar.tsx'
import TradingDesk from './pages/TradingDesk.tsx'
import Portfolio from './pages/Portfolio.tsx'
import Research from './pages/Research.tsx'

export default function App() {
  const location = useLocation()

  if (location.pathname === '/desk-card') {
    return <TradingDesk />
  }

  return (
    <div className="h-screen w-screen flex bg-white overflow-hidden">
      <Sidebar />
      <main className="flex-1 min-w-0 h-full overflow-hidden">
        <Routes>
          <Route path="/" element={<TradingDesk />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/research" element={<Research />} />
        </Routes>
      </main>
    </div>
  )
}
