import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function CommuterLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      {/* Top nav */}
      <nav className="bg-green-deep text-white px-4 py-3 flex items-center justify-between sticky top-0 z-50">
        <span className="font-bold text-lg" style={{fontFamily: 'serif'}}>
          Smart<span className="text-amber">Transit</span>
        </span>
        <div className="flex items-center gap-4">
          <NavLink
            to="/commuter"
            end
            className={({ isActive }) =>
              `text-sm font-medium transition-colors ${isActive ? 'text-amber' : 'text-white/70 hover:text-white'}`
            }
          >
            Search
          </NavLink>
          <NavLink
            to="/commuter/tickets"
            className={({ isActive }) =>
              `text-sm font-medium transition-colors ${isActive ? 'text-amber' : 'text-white/70 hover:text-white'}`
            }
          >
            My Tickets
          </NavLink>
          <NavLink
            to="/commuter/parcels"
            className={({ isActive }) =>
            `text-sm font-medium transition-colors ${isActive ? 'text-amber' : 'text-white/70 hover:text-white'}`
            }
          >
            Track Parcel
          </NavLink>
          <button
            onClick={handleLogout}
            className="text-sm text-white/60 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Page content */}
      <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}