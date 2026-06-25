import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function FleetLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-cream flex">
      {/* Sidebar */}
      <aside className="w-56 bg-green-deep text-white flex flex-col fixed h-full">
        <div className="px-6 py-5 border-b border-white/10">
          <span className="font-bold text-lg" style={{fontFamily: 'serif'}}>
            Smart<span className="text-amber">Transit</span>
          </span>
          <p className="text-xs text-white/50 mt-1">Fleet Dashboard</p>
        </div>

        <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
          {[
            { to: '/fleet', label: 'Overview', end: true },
            { to: '/fleet/live', label: 'Live Map' },
            { to: '/fleet/analytics', label: 'Analytics' },
            { to: '/fleet/parcels', label: 'Parcels' },
          ].map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-amber text-ink'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-white/10">
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2.5 rounded-xl text-sm text-white/60 hover:text-white hover:bg-white/10 text-left transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 ml-56 p-8">
        <Outlet />
      </main>
    </div>
  )
}