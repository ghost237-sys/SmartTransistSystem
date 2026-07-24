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
    <div className="min-h-screen bg-slate-950 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-white/10 text-white flex flex-col fixed h-full z-20">
        <div className="px-6 py-5 border-b border-white/10">
          <span className="font-extrabold text-xl tracking-tight" style={{fontFamily: 'serif'}}>
            Smart<span className="text-amber-400">Transit</span>
          </span>
          <p className="text-xs text-slate-400 mt-0.5">Supermetro Executive Command</p>
        </div>

        <nav className="flex-1 px-4 py-6 flex flex-col gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-3">
            Monitoring & Command
          </span>
          {[
            { to: '/fleet', label: 'Command Overview', end: true, icon: '📊' },
            { to: '/fleet/live', label: 'Live Fleet Tracking', icon: '📍' },
            { to: '/fleet/analytics', label: 'Financial Analytics', icon: '📈' },
          ].map(({ to, label, end, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `px-4 py-3 rounded-xl text-sm font-semibold transition-all flex items-center gap-3 ${
                  isActive
                    ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 shadow-lg font-bold'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <span className="text-base">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-5 border-t border-white/10 bg-slate-950/60">
          <div className="flex items-center gap-3 px-2 mb-3">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center font-bold text-xs">
              SM
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-bold text-white truncate">Supermetro Owner</p>
              <p className="text-[10px] text-slate-400">Executive Account</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 text-left transition-colors flex items-center gap-2"
          >
            <span>🚪</span> Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 ml-64 p-6 bg-slate-950 text-slate-100 min-h-screen">
        <Outlet />
      </main>
    </div>
  )
}