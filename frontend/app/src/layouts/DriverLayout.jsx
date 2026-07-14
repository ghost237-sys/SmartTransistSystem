import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function DriverLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  // Dashboard route uses its own full-screen layout — skip the wrapper chrome
  const isDashboard = location.pathname === '/driver' || location.pathname === '/driver/'

  if (isDashboard) {
    return <Outlet />
  }

  return (
    <div className="min-h-screen bg-[#090d16] flex flex-col">
      <nav className="bg-black/40 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-50 backdrop-blur-sm border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <NavLink
            to="/driver"
            className="font-black text-[#f1a81f] text-lg tracking-wide"
          >
            ◉ DRIVER
          </NavLink>
        </div>
        <div className="flex items-center gap-4">
          <NavLink
            to="/driver/manifest"
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-[#f1a81f]' : 'text-white/40 hover:text-white'}`
            }
          >
            MANIFEST
          </NavLink>
          <NavLink
            to="/driver/trips"
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-[#f1a81f]' : 'text-white/40 hover:text-white'}`
            }
          >
            TRIPS
          </NavLink>
          <button
            onClick={handleLogout}
            className="text-xs text-white/20 hover:text-red-400 font-bold uppercase tracking-wider transition-colors cursor-pointer"
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
