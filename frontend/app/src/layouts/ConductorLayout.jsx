import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function ConductorLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-ink flex flex-col">
      {/* Top bar — high contrast for bright sunlight */}
      <nav className="bg-black text-white px-4 py-3 flex items-center justify-between sticky top-0 z-50">
        <span className="font-bold text-amber text-lg">CONDUCTOR</span>
        <div className="flex items-center gap-4">
          <NavLink
            to="/conductor"
            end
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-amber' : 'text-white/60 hover:text-white'}`
            }
          >
            MANIFEST
          </NavLink>
          <NavLink
            to="/conductor/scan"
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-amber' : 'text-white/60 hover:text-white'}`
            }
          >
            SCAN
          </NavLink>
          <NavLink
            to="/conductor/cash"
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-amber' : 'text-white/60 hover:text-white'}`
            }
          >
            CASH
          </NavLink>
          <button
            onClick={handleLogout}
            className="text-xs text-white/40 hover:text-white"
          >
            OUT
          </button>
        </div>
      </nav>

      <main className="flex-1 max-w-lg w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}