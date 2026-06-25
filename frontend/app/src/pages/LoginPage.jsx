import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'

const ROLE_REDIRECTS = {
  commuter:    '/commuter',
  fleet_owner: '/fleet',
  conductor:   '/conductor',
  driver:      '/driver',
  super_admin: '/fleet',
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname

  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const user = await login(form.username, form.password)
      
      // If "from" is missing or just the blank root "/", use the specific role dashboard.
      // Otherwise, use "from" (e.g. if they bookmarked a specific inner page like /commuter/tickets)
      const destination = (!from || from === '/') 
        ? (ROLE_REDIRECTS[user.role] || '/') 
        : from

      navigate(destination, { replace: true })
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Invalid username or password. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <a href="/" className="inline-block">
            <h1 className="text-3xl font-bold" style={{ fontFamily: 'serif' }}>
              <span className="text-green-deep">Smart</span>
              <span className="text-amber">Transit</span>
            </h1>
          </a>
          <p className="text-ink-light mt-2 text-sm">Sign in to continue</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <Input
              label="Username"
              type="text"
              placeholder="Enter your username"
              value={form.username}
              onChange={(e) => setForm(f => ({ ...f, username: e.target.value }))}
              required
            />
            <Input
              label="Password"
              type="password"
              placeholder="Enter your password"
              value={form.password}
              onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))}
              required
            />

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
                {error}
              </div>
            )}

            <Button type="submit" loading={loading} className="w-full mt-2">
              Sign in
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-ink-light mt-6">
          SmartTransit — Know your bus is coming.{' '}
          <a href="/" className="text-green-deep hover:underline">Back to home</a>
        </p>
      </div>
    </div>
  )
}