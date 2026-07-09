import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function StageLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-purple-deep flex flex-col">
      <nav className="bg-black/30 text-white px-4 py-3 flex items-center justify-between sticky top-0 z-50 backdrop-blur-sm">
        <span className="font-bold text-purple-pale text-lg tracking-wide">STAGE MANAGER</span>
        <div className="flex items-center gap-4">
          <NavLink
            to="/stage"
            end
            className={({ isActive }) =>
              `text-sm font-bold transition-colors ${isActive ? 'text-amber' : 'text-white/60 hover:text-white'}`
            }
          >
            DASHBOARD
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
