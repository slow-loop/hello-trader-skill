import { NavLink } from 'react-router-dom'
import { Monitor, Briefcase, Search } from 'lucide-react'

const links = [
  { to: '/', icon: Monitor, label: 'Desk' },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio' },
  { to: '/research', icon: Search, label: 'Research' },
]

export default function Sidebar() {
  return (
    <nav className="w-12 h-full bg-white border-r border-gray-200 flex flex-col items-center py-4 gap-1 shrink-0">
      <div className="w-6 h-6 rounded bg-gray-900 mb-6" title="Trader" />
      {links.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          title={label}
          className={({ isActive }) =>
            `w-9 h-9 flex items-center justify-center rounded transition-colors ${
              isActive ? 'bg-gray-100 text-gray-900' : 'text-gray-400 hover:text-gray-700 hover:bg-gray-50'
            }`
          }
        >
          <Icon size={18} />
        </NavLink>
      ))}
    </nav>
  )
}
