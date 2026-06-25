import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Button from '../components/ui/Button'

const ROLE_HOME = {
  commuter: '/commuter',
  fleet_owner: '/fleet',
  super_admin: '/fleet',
  conductor: '/conductor',
  driver: '/driver',
}

const ROLE_LABELS = {
  commuter: 'Commuter',
  fleet_owner: 'Fleet Owner',
  super_admin: 'Super Admin',
  conductor: 'Conductor',
  driver: 'Driver',
}

export default function UnauthorizedPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const home = user ? (ROLE_HOME[user.role] || '/login') : '/login'
  const roleLabel = user ? (ROLE_LABELS[user.role] || user.role) : null

  const handleSignOut = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold" style={{ fontFamily: 'serif' }}>
            <span className="text-green-deep">Smart</span>
            <span className="text-amber">Transit</span>
          </h1>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <div className="w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            </svg>
          </div>

          <h2 className="text-xl font-bold text-ink mb-2">Access denied</h2>
          <p className="text-ink-light text-sm mb-1">
            You don&apos;t have permission to view that page.
          </p>
          {roleLabel && (
            <p className="text-ink-light text-sm mb-6">
              Signed in as <span className="font-medium text-ink">{roleLabel}</span>.
            </p>
          )}

          <div className="flex flex-col gap-3">
            {user && (
              <Button className="w-full" onClick={() => navigate(home, { replace: true })}>
                Go to my dashboard
              </Button>
            )}
            <Button variant="secondary" className="w-full" onClick={() => navigate('/login', { replace: true })}>
              Sign in as a different user
            </Button>
            <a
              href="/"
              className="text-sm text-ink-light hover:text-ink transition-colors text-center"
            >
              Back to home
            </a>
            {user && (
              <button
                onClick={handleSignOut}
                className="text-sm text-ink-light hover:text-ink transition-colors"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
